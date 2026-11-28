"""Opt-in photo-set API, sharing existing authenticated worker lock.
Bounded binary request: big-endian u32 JSON length, UTF-8 JSON {sizes,image_up},
then concatenated photo bytes. No client paths, archives or shell commands.
"""
import hashlib,hmac,json,os,pathlib,signal,struct,subprocess,sys,tempfile,time
from PIL import Image
from private_api_extended import ExtendedHandler,BoundedServer,TOKEN,ORIGINS,LOCK,ROOT,ENABLED,PROBE,fits_static
WORKER=ROOT.parent.parent/"verification/f01/user_photo_worker.py"
BIN=pathlib.Path(os.getenv("FORGE_OPENMVS_BIN","/nonexistent")).resolve()
MAX_FILE=5*1024*1024
MAX_TOTAL=60*1024*1024
UP=("top","right","bottom","left")
def available():
    return os.getenv("FORGE_MULTIVIEW_ENABLED")=="1" and WORKER.is_file() and all(os.access(BIN/p,os.X_OK) and (BIN/p).is_file() for p in ("InterfaceCOLMAP","DensifyPointCloud","ReconstructMesh"))
def receive(stream,length,directory):
    def exact(n):
        b=stream.read(n)
        if len(b)!=n:raise ValueError("truncated payload")
        return b
    n=struct.unpack(">I",exact(4))[0]
    if not 1<=n<=4096 or n+4>=length:raise ValueError("invalid metadata")
    meta=json.loads(exact(n).decode("utf8"))
    if not isinstance(meta,dict) or set(meta)!={"sizes","image_up"} or meta["image_up"] not in UP:raise ValueError("invalid metadata")
    sizes=meta["sizes"]
    if not isinstance(sizes,list) or not 12<=len(sizes)<=48 or any(type(s) is not int or not 0<s<=MAX_FILE for s in sizes) or sum(sizes)+4+n!=length:raise ValueError("invalid photo sizes")
    seen=set()
    for i,size in enumerate(sizes):
        data=exact(size);digest=hashlib.sha256(data).digest()
        if digest in seen:raise ValueError("duplicate photo")
        seen.add(digest)
        # Never use client-supplied filenames. Preserve original pixels and EXIF.
        import io
        with Image.open(io.BytesIO(data)) as im:
            ext={"PNG":"png","JPEG":"jpg","WEBP":"webp"}.get(im.format)
            if not ext or im.width*im.height>12_000_000:raise ValueError("invalid photo")
            im.verify()
        (directory/f"photo{i:02d}.{ext}").write_bytes(data)
    return meta["image_up"]
class PhotoHandler(ExtendedHandler):
    def do_GET(self):
        if self.path=="/health":
            self.respond(200,{"service":"forge-cpu","version":"R70.34","busy":LOCK.locked(),"text_experimental_enabled":ENABLED and PROBE.is_file(),"multiview_experimental_enabled":available()})
        else:super().do_GET()
    def do_POST(self):
        if self.path!="/v1/generate-multiview":return super().do_POST()
        if self.headers.get("Origin") and self.headers.get("Origin") not in ORIGINS:self.respond(403,{"error":"origin not permitted"});return
        if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+TOKEN):self.respond(401,{"error":"unauthorized"});return
        if not available():self.respond(503,{"error":"Çok açılı deneysel motor etkin değil."});return
        if self.headers.get("Content-Type","").split(";")[0]!="application/octet-stream":self.respond(415,{"error":"binary photo set required"});return
        try:length=int(self.headers.get("Content-Length","0"))
        except ValueError:length=0
        if not 4<length<=MAX_TOTAL:self.respond(413,{"error":"Fotoğraf grubu en fazla 60 MiB."});return
        if not LOCK.acquire(blocking=False):self.respond(429,{"error":"Tek seferde bir üretim."});return
        try:
            with tempfile.TemporaryDirectory(prefix="forge-photos-") as td:
                root=pathlib.Path(td);photos=root/"photos";photos.mkdir();output=root/"result"
                try:
                    # Only authenticated, bounded uploads reach this point.
                    # Spool completely before semantic validation; an early
                    # duplicate rejection otherwise resets the client's upload.
                    deadline=time.monotonic()+120
                    remaining=length
                    with tempfile.TemporaryFile(dir=root) as payload:
                        while remaining:
                            if time.monotonic()>deadline:raise TimeoutError("upload deadline")
                            chunk=self.rfile.read1(min(65536,remaining))
                            if not chunk:raise ValueError("truncated upload")
                            payload.write(chunk);remaining-=len(chunk)
                        payload.seek(0)
                        up=receive(payload,length,photos)
                except TimeoutError:
                    self.respond(408,{"error":"Fotoğraf yüklemesi zaman aşımına uğradı."});return
                except (ValueError,TypeError,OSError,Image.DecompressionBombError,struct.error):
                    self.respond(400,{"error":"Geçersiz veya tekrarlanan fotoğraf grubu. 12–48 PNG/JPEG/WebP gerekli."});return
                env=dict(os.environ)
                for key in ("FORGE_API_TOKEN","HF_TOKEN","HUGGING_FACE_HUB_TOKEN"):env.pop(key,None)
                cmd=[sys.executable,str(WORKER),str(photos),str(output),"--openmvs-bin",str(BIN),"--image-up",up]
                # Linux process group: timeout terminates nested native executables.
                with subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True) as proc:
                    try:code=proc.wait(timeout=1080)
                    except subprocess.TimeoutExpired:
                        try:os.killpg(proc.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                        proc.wait();self.respond(504,{"error":"Çok açılı üretim zaman aşımı."});return
                if code:
                    self.respond(422,{"error":"Fotoğraflardan güvenli model üretilemedi. Aynı kamera, düz fon ve örtüşen açılar gerekli."});return
                src=output/"model.glb";meta=json.loads((output/"report.json").read_text())
                if src.stat().st_size>8_000_000 or meta["coverage"]<.94 or meta["mean_input_iou"]<.85:raise ValueError("quality gate")
                data=src.read_bytes()
                if not fits_static(data):raise ValueError("editor limit")
                self.respond(200,data,"model/gltf-binary")
        except Exception:self.respond(500,{"error":"Çok açılı üretim sonucu doğrulanamadı."})
        finally:LOCK.release()
if __name__=="__main__":BoundedServer((os.getenv("FORGE_BIND","127.0.0.1"),int(os.getenv("PORT","8765"))),PhotoHandler).serve_forever()
