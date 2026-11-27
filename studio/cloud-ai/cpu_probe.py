import json,pathlib,struct,time,os
import torch
from PIL import Image,ImageDraw
from huggingface_hub import hf_hub_download
from tsr.system import TSR
from skimage.measure import marching_cubes
import tsr.models.isosurface as iso
# CPU-only MC replacement. skimage returns axes in array order; upstream helper
# reverses torchmcubes axes, so reverse here before its existing conversion.
def mc(level,threshold):
    v,f,_,_=marching_cubes(level.detach().cpu().numpy(),level=threshold,allow_degenerate=False,gradient_direction="descent")
    return torch.from_numpy(v[:,::-1].copy()).float(),torch.from_numpy(f.copy()).long()
iso.marching_cubes=mc
out=pathlib.Path(os.getenv("FORGE_OUTPUT","cloud-cpu-qa")).resolve();out.mkdir(exist_ok=True)
report={"device":"cpu","real_generation":False,"model":"stabilityai/TripoSR","resolution":128}
try:
    torch.set_num_threads(4)
    im=Image.new("RGB",(384,384),(128,128,128));d=ImageDraw.Draw(im)
    d.polygon([(88,150),(204,85),(310,146),(196,211)],fill=(100,175,220))
    d.polygon([(88,150),(196,211),(196,322),(88,262)],fill=(42,99,166))
    d.polygon([(196,211),(310,146),(310,258),(196,322)],fill=(32,63,118))
    sample=os.getenv("FORGE_IMAGE")
    if sample:
        # Real independent humanoid test image from pinned upstream examples.
        # Not a game asset and no commercial license assumed for the example.
        from tsr.utils import resize_foreground,remove_background
        import rembg
        from PIL import ImageOps
        raw=Image.open(sample).convert("RGBA")
        raw.thumbnail((768,768))
        if raw.getchannel("A").getextrema()==(255,255):
            raw=remove_background(raw,rembg.new_session("u2netp"))
        raw=resize_foreground(raw,0.85)
        bg=Image.new("RGBA",raw.size,(128,128,128,255))
        bg.alpha_composite(raw)
        im=bg.convert("RGB")
        report["input"]="upstream robot sample (QA only)"
    else:
        report["input"]="synthetic blue cube"
    im.save(out/"input.png")
    start=time.monotonic()
    model=TSR.from_pretrained("stabilityai/TripoSR",config_name="config.yaml",weight_name="model.ckpt").eval().to("cpu")
    model.renderer.set_chunk_size(4096)
    report["load_seconds"]=time.monotonic()-start
    with torch.inference_mode():
        z=model([im],device="cpu")
        assert torch.isfinite(z).all()
        mesh=model.extract_mesh(z,True,resolution=128)[0]
    assert len(mesh.vertices)>100 and len(mesh.faces)>100
    # Correct winding if closed component volume indicates inversion.
    if mesh.is_watertight and mesh.volume<0:mesh.invert()
    mesh.export(out/"generated.glb")
    # A real mesh and its color attributes must survive export/import.
    import trimesh,numpy as np
    restored=trimesh.load(out/"generated.glb",force="mesh")
    assert len(restored.vertices)==len(mesh.vertices) and len(restored.faces)==len(mesh.faces)
    assert np.isfinite(restored.vertices).all()
    report["components"]=len(restored.split(only_watertight=False))
    report["vertex_color"]=restored.visual.kind=="vertex"
    assert report["vertex_color"]
    data=(out/"generated.glb").read_bytes()
    assert struct.unpack_from("<4sII",data)==(b"glTF",2,len(data))
    report.update(real_generation=True,vertices=len(mesh.vertices),faces=len(mesh.faces),watertight=bool(mesh.is_watertight),bytes=len(data),seconds=time.monotonic()-start)
except Exception as e:
    report["error"]=repr(e)
finally:
    (out/"report.json").write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if not report["real_generation"]:raise SystemExit(1)
