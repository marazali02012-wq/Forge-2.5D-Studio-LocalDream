"""Offline proxy tests; mocked Gradio output is NOT a live TRELLIS.2 generation."""
import io, json, os, struct, time
from pathlib import Path
os.environ["FORGE_ACCESS_TOKEN"] = "test-secret-" + "x"*24
from fastapi.testclient import TestClient
from PIL import Image
from trellis2 import server as srv
client = TestClient(srv.app)
HEADERS={"X-Forge-Token":os.environ["FORGE_ACCESS_TOKEN"]}
def png():
    b=io.BytesIO();Image.new("RGB",(32,32),(10,50,100)).save(b,"PNG");return b.getvalue()
from trellis2.test_fixture import glb
def wait(id):
    for _ in range(100):
        state=client.get("/api/jobs/"+id,headers=HEADERS).json()
        if state["status"] not in ("queued","running"): return state
        time.sleep(.05)
    raise AssertionError("job stuck")
def test_auth():
    image=png()
    assert client.post("/api/jobs",files={"image":("a.png",image,"image/png")}).status_code==401
    assert client.post("/api/jobs",headers={"X-Forge-Token":"invalid"},files={"image":("a.png",image,"image/png")}).status_code==401
    assert client.post("/api/jobs",headers=HEADERS,files={"image":("f.png",b"invalid"*10,"image/png")}).status_code==415
    assert client.get("/health").json()["paid_gpu_started"] is False
def test_mock_success(monkeypatch,tmp_path):
    p=tmp_path/"mock.glb";p.write_bytes(glb())
    class Mock:
        def __init__(self,space,token=None,verbose=False):assert space=="microsoft/TRELLIS.2"
        def predict(self,*args,api_name):
            if api_name == "/start_session": return None
            if api_name == "/preprocess_image": return args[0]["path"]
            if api_name == "/image_to_3d": return "mock preview"
            if api_name == "/extract_glb": return str(p),str(p)
            raise AssertionError(api_name)
    monkeypatch.setattr(srv,"Client",Mock)
    resp=client.post("/api/jobs",headers=HEADERS,files={"image":("fighter.png",png(),"image/png")})
    assert resp.status_code==202,resp.text
    id=resp.json()["id"]; result=wait(id)
    assert result["status"]=="done",result
    assert client.get(f"/api/jobs/{id}/glb",headers=HEADERS).content==glb()
def test_mock_gpu_unavailable(monkeypatch):
    class Offline:
        def __init__(self,*a,**kw): raise RuntimeError("GPU unavailable")
    monkeypatch.setattr(srv,"Client",Offline)
    id=client.post("/api/jobs",headers=HEADERS,files={"image":("fighter.png",png(),"image/png")}).json()["id"]
    assert wait(id)["status"]=="failed"
    assert client.get(f"/api/jobs/{id}/glb",headers=HEADERS).status_code==409
def test_webp_glb_accepted(tmp_path):
    p=tmp_path/"webp.glb"
    p.write_bytes(glb(webp=True))
    assert srv.validate_glb(p),"Official TRELLIS WebP extension must be accepted"

def test_truncated_glb_rejected(tmp_path):
    p=tmp_path/"a.glb";p.write_bytes(glb());assert srv.validate_glb(p)
    p.write_bytes(glb()[:-4]);assert not srv.validate_glb(p)

def test_expired_glb_private_files_removed(tmp_path):
    folder = tmp_path / "user_private_glb"
    folder.mkdir()
    (folder / "output.glb").write_bytes(glb())
    job_id = "expiry_test_quality"
    with srv.lock:
        srv.jobs[job_id] = {"status":"done","message":"ok","glb":str(folder / "output.glb"),
                            "folder":str(folder),"completed_at":100.}
    assert srv.cleanup_expired_jobs(now=100.+srv.RESULT_TTL_SECONDS-1)==0
    assert folder.exists()
    assert srv.cleanup_expired_jobs(now=100.+srv.RESULT_TTL_SECONDS+1)>=1
    assert not folder.exists() and job_id not in srv.jobs

def test_parallel_generation_rejected(monkeypatch):
    monkeypatch.setattr(srv.pool, "submit", lambda *args, **kwargs: None)
    image = png()
    a = client.post("/api/jobs",headers=HEADERS,files={"image":("one.png",image,"image/png")})
    assert a.status_code==202
    ident=a.json()["id"]
    try:
        b=client.post("/api/jobs",headers=HEADERS,files={"image":("two.png",image,"image/png")})
        assert b.status_code==429
    finally:
        with srv.lock:
            folder=srv.jobs.pop(ident)["folder"]
        import shutil
        shutil.rmtree(folder,ignore_errors=True)

def test_quality_defaults_match_balanced_preset():
    assert srv.MODEL_RESOLUTION == "1024"
    assert srv.OUTPUT_FACES == 200000
    assert srv.OUTPUT_TEXTURE_SIZE == 2048

def test_unbound_pbr_texture_does_not_pass_as_textured_mesh(tmp_path):
    source = glb()
    old_size = struct.unpack_from("<I", source, 12)[0]
    j = json.loads(source[20:20+old_size])
    j["materials"].append({"pbrMetallicRoughness":{"baseColorFactor":[1,1,1,1]}})
    for mesh in j["meshes"]:
        for prim in mesh["primitives"]:
            prim["material"] = len(j["materials"]) - 1
    encoded = json.dumps(j,separators=(",",":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    bin_chunk = source[20+old_size:]
    modified = (struct.pack("<III",0x46546c67,2,20+len(encoded)+len(bin_chunk))
                + struct.pack("<II",len(encoded),0x4e4f534a)+encoded+bin_chunk)
    target = tmp_path / "texture_present_but_unused.glb"
    target.write_bytes(modified)
    assert not srv.validate_glb(target)
