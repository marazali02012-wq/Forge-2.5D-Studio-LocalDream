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
def glb():
    j=json.dumps({"asset":{"version":"2.0"},"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],"buffers":[{"byteLength":0}],"accessors":[{"componentType":5126,"count":0,"type":"VEC3"}]}).encode()
    j+=b" "*(-len(j)%4)
    return struct.pack("<III",0x46546C67,2,12+8+len(j)+8)+struct.pack("<II",len(j),0x4E4F534A)+j+struct.pack("<II",0,0x004E4942)
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
            return {"/start_session":None,"/preprocess_image":args[0]["path"] if args else None,"/image_to_3d":"mock preview","/extract_glb":(str(p),str(p))}[api_name]
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
def test_truncated_glb_rejected(tmp_path):
    p=tmp_path/"a.glb";p.write_bytes(glb());assert srv.validate_glb(p)
    p.write_bytes(glb()[:-4]);assert not srv.validate_glb(p)
