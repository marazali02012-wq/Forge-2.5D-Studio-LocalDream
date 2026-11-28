"""Experimental authenticated Shap-E extension. Base image/rig API stays intact.
Explicit opt-in, single shared worker, no paid inference or substitute GLB.
Run from full checkout with the pinned F01 text dependencies installed.
"""
import hmac,json,os,pathlib,struct,subprocess,sys,tempfile
from private_api import Handler,BoundedServer,TOKEN,ORIGINS,LOCK,ROOT
PROBE=ROOT.parent.parent/"verification/f01/shap_e_text_probe.py"
ENABLED=os.getenv("FORGE_TEXT_ENABLED")=="1"
MAX_BODY=4096
def fits_static(data):
    if not 28<=len(data)<=8_000_000 or struct.unpack_from("<4sII",data)!=(b"glTF",2,len(data)):return False
    size,tag=struct.unpack_from("<I4s",data,12)
    if tag!=b"JSON" or 20+size>len(data):return False
    doc=json.loads(data[20:20+size])
    if doc.get("skins") or doc.get("animations") or len(doc["meshes"])!=1:return False
    ps=doc["meshes"][0]["primitives"]
    if len(ps)!=1:return False
    p=ps[0];a=doc["accessors"];attrs=p["attributes"]
    return "COLOR_0" in attrs and "NORMAL" in attrs and 0<a[attrs["POSITION"]]["count"]<=30000 and 0<a[p["indices"]]["count"]<=180000
class ExtendedHandler(Handler):
    def do_GET(self):
        if self.path=="/health":
            self.respond(200,{"service":"forge-triposr-cpu","version":"R70.34","busy":LOCK.locked(),"text_experimental_enabled":ENABLED and PROBE.is_file()})
        else:super().do_GET()
    def do_POST(self):
        if self.path!="/v1/generate-text":return super().do_POST()
        if self.headers.get("Origin") and self.headers.get("Origin") not in ORIGINS:self.respond(403,{"error":"origin not permitted"});return
        if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+TOKEN):self.respond(401,{"error":"unauthorized"});return
        if not ENABLED or not PROBE.is_file():self.respond(503,{"error":"Deneysel yazı motoru etkin değil."});return
        if self.headers.get("Content-Type","").split(";")[0]!="application/json":self.respond(415,{"error":"JSON required"});return
        try:n=int(self.headers.get("Content-Length","0"))
        except ValueError:n=0
        if not 0<n<=MAX_BODY:self.respond(413,{"error":"invalid length"});return
        try:
            raw=self.rfile.read(n)
            if len(raw)!=n:raise ValueError()
            body=json.loads(raw.decode("utf-8"))
            if not isinstance(body,dict) or set(body)!={"prompt"} or not isinstance(body["prompt"],str):raise ValueError()
            prompt=body["prompt"].strip()
            if not 1<=len(prompt)<=300 or any(ord(c)<32 for c in prompt):raise ValueError()
        except (ValueError,UnicodeError,OSError):
            self.respond(400,{"error":"1–300 karakterlik metin gerekli."});return
        if not LOCK.acquire(blocking=False):self.respond(429,{"error":"Tek seferde bir üretim."});return
        try:
            with tempfile.TemporaryDirectory(prefix="forge-text-") as td:
                path=pathlib.Path(td)/"result"
                env=dict(os.environ);env.pop("FORGE_API_TOKEN",None);env.pop("HF_TOKEN",None);env.pop("HUGGING_FACE_HUB_TOKEN",None)
                # '--' prevents a user prompt from becoming command-line flags.
                proc=subprocess.run([sys.executable,str(PROBE),"--steps","24","--grid","96",str(path),"--",prompt],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=420)
                if proc.returncode:raise RuntimeError("real inference failed")
                meta=json.loads((path/"report.json").read_text())
                if meta.get("engine")!="openai/shap-e" or len(meta["results"])!=1 or meta["results"][0]["prompt"]!=prompt:raise RuntimeError("invalid engine output")
                src=path/"text-00.glb"
                if src.stat().st_size>8_000_000:self.respond(422,{"error":"Model telefon editörü sınırını aştı."});return
                data=src.read_bytes()
                if not fits_static(data):self.respond(422,{"error":"Model telefon editörü sınırını aştı."});return
                self.respond(200,data,"model/gltf-binary")
        except subprocess.TimeoutExpired:self.respond(504,{"error":"Üretim zaman aşımına uğradı."})
        except Exception:self.respond(500,{"error":"Gerçek Shap-E üretimi başarısız."})
        finally:LOCK.release()
if __name__=="__main__":BoundedServer((os.getenv("FORGE_BIND","127.0.0.1"),int(os.getenv("PORT","8765"))),ExtendedHandler).serve_forever()
