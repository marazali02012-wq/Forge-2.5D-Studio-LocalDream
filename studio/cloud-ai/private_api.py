"""Private single-worker image-to-GLB API. Requires adequate CPU RAM."""
import hmac,io,os,pathlib,subprocess,sys,tempfile,threading,struct,json
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from PIL import Image,ImageOps
ROOT=pathlib.Path(__file__).resolve().parent
TOKEN=os.environ.get("FORGE_API_TOKEN","")
assert len(TOKEN)>=32,"Set a strong FORGE_API_TOKEN"
ORIGINS=set(os.environ.get("FORGE_ALLOWED_ORIGINS","").split(","))-{""}
LOCK=threading.Lock()
LIMIT=5*1024*1024
Image.MAX_IMAGE_PIXELS=12_000_000
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def cors(self):
        origin=self.headers.get("Origin")
        if origin in ORIGINS:
            self.send_header("Access-Control-Allow-Origin",origin);self.send_header("Vary","Origin")
    def respond(self,status,body,typ="application/json"):
        if isinstance(body,dict):body=json.dumps(body).encode()
        self.send_response(status);self.cors();self.send_header("Content-Type",typ);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_OPTIONS(self):
        if self.headers.get("Origin") not in ORIGINS:self.respond(403,{"error":"origin not permitted"});return
        self.send_response(204);self.cors();self.send_header("Access-Control-Allow-Methods","POST, GET, OPTIONS");self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type");self.send_header("Content-Length","0");self.end_headers()
    def do_GET(self):
        if self.path=="/health":self.respond(200,{"service":"forge-triposr-cpu","busy":LOCK.locked()})
        else:self.respond(404,{"error":"not found"})
    def do_POST(self):
        self.connection.settimeout(20)
        if self.path!="/v1/generate":self.respond(404,{"error":"not found"});return
        if self.headers.get("Origin") and self.headers.get("Origin") not in ORIGINS:self.respond(403,{"error":"origin not permitted"});return
        if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+TOKEN):self.respond(401,{"error":"unauthorized"});return
        if self.headers.get("Content-Type","").split(";")[0] not in ("image/png","image/jpeg","image/webp"):self.respond(415,{"error":"PNG/JPEG/WebP required"});return
        try:n=int(self.headers.get("Content-Length","0"))
        except ValueError:n=0
        if not 0<n<=LIMIT:self.respond(413,{"error":"image exceeds 5 MB or invalid length"});return
        if not LOCK.acquire(blocking=False):self.respond(429,{"error":"one generation at a time"});return
        try:
            raw=self.rfile.read(n)
            if len(raw)!=n:raise ValueError("incomplete upload")
            with tempfile.TemporaryDirectory(prefix="forge-ai-") as td:
                path=pathlib.Path(td)
                with Image.open(io.BytesIO(raw)) as src:
                    if src.format not in ("PNG","JPEG","WEBP") or src.width*src.height>12_000_000:raise ValueError("invalid image")
                    im=ImageOps.exif_transpose(src).convert("RGBA");im.thumbnail((768,768));im.save(path/"input.png")
                env=dict(os.environ,FORGE_IMAGE=str(path/"input.png"),FORGE_OUTPUT=str(path/"result"),FORGE_RESOLUTION="128")
                env.pop("FORGE_API_TOKEN",None)
                r=subprocess.run([sys.executable,str(ROOT/"cpu_probe.py")],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)
                if r.returncode:raise RuntimeError("generation failed")
                data=(path/"result/generated.glb").read_bytes()
                if len(data)>8_000_000 or struct.unpack_from("<4sII",data)!=(b"glTF",2,len(data)):raise RuntimeError("invalid model")
                jl=struct.unpack_from("<I",data,12)[0];g=json.loads(data[20:20+jl]);p=g["meshes"][0]["primitives"][0]
                if g["accessors"][p["attributes"]["POSITION"]]["count"]>30000 or g["accessors"][p["indices"]]["count"]>180000:
                    self.respond(422,{"error":"model exceeds editor budget"});return
                self.respond(200,data,"model/gltf-binary")
        except (ValueError,OSError,Image.DecompressionBombError):self.respond(400,{"error":"invalid image or upload"})
        except subprocess.TimeoutExpired:self.respond(504,{"error":"generation timed out"})
        except Exception:self.respond(500,{"error":"generation failed"})
        finally:LOCK.release()
if __name__=="__main__":ThreadingHTTPServer((os.getenv("FORGE_BIND","127.0.0.1"),int(os.getenv("PORT","8765"))),Handler).serve_forever()
