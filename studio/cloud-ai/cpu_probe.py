import hashlib,json,pathlib,struct,time,os,resource
from math import ceil as np_ceil
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
resolution=int(os.getenv("FORGE_RESOLUTION","128"))
assert resolution in (128,192,256)
report={"device":"cpu","real_generation":False,"model":"stabilityai/TripoSR","resolution":resolution}
try:
    torch.set_num_threads(max(1,min(4,int(os.getenv("FORGE_CPU_THREADS","4")))))
    im=Image.new("RGB",(384,384),(128,128,128));d=ImageDraw.Draw(im)
    d.polygon([(88,150),(204,85),(310,146),(196,211)],fill=(100,175,220))
    d.polygon([(88,150),(196,211),(196,322),(88,262)],fill=(42,99,166))
    d.polygon([(196,211),(310,146),(310,258),(196,322)],fill=(32,63,118))
    sample=os.getenv("FORGE_IMAGE")
    if sample:
        # Generic foreground preparation, independent of subject category or pose.
        from tsr.utils import remove_background
        import rembg
        from PIL import ImageOps
        with Image.open(sample) as source:
            raw=ImageOps.exif_transpose(source).convert("RGBA")
        raw.thumbnail((768,768))
        if raw.getchannel("A").getextrema()==(0,0):
            raise ValueError("empty transparent image")
        if raw.getchannel("A").getextrema()==(255,255):
            raw=remove_background(raw,rembg.new_session("u2netp"))
        # Pillow bbox uses exclusive upper bounds, preserving the last
        # occupied row/column unlike upstream resize_foreground.
        alpha=raw.getchannel("A")
        bounds=alpha.point(lambda a:255 if a>=8 else 0).getbbox()
        if bounds is None:
            raise ValueError("foreground not found")
        fg=raw.crop(bounds)
        if min(fg.size)<2:
            raise ValueError("foreground too small")
        size=max(fg.size)
        canvas=max(size,int(np_ceil(size/0.85)))
        padded=Image.new("RGBA",(canvas,canvas),(0,0,0,0))
        padded.alpha_composite(fg,((canvas-fg.width)//2,(canvas-fg.height)//2))
        bg=Image.new("RGBA",padded.size,(128,128,128,255))
        bg.alpha_composite(padded)
        im=bg.convert("RGB")
        report["input_sha256"]=hashlib.sha256(pathlib.Path(sample).read_bytes()).hexdigest()
        report["foreground_bbox"]=list(bounds)
        report["foreground_size"]=list(fg.size)
    else:
        report["input"]="synthetic blue cube"
    im.save(out/"input.png")
    start=time.monotonic()
    model=TSR.from_pretrained(os.getenv("FORGE_MODEL_PATH","stabilityai/TripoSR"),config_name="config.yaml",weight_name="model.ckpt").eval().to("cpu")
    model.renderer.set_chunk_size(4096)
    report["load_seconds"]=time.monotonic()-start
    with torch.inference_mode():
        z=model([im],device="cpu")
        assert torch.isfinite(z).all()
        mesh=model.extract_mesh(z,True,resolution=resolution)[0]
    assert len(mesh.vertices)>100 and len(mesh.faces)>100
    # Correct winding if closed component volume indicates inversion.
    if mesh.is_watertight and mesh.volume<0:mesh.invert()
    import numpy as np,trimesh
    # Preserve actual AI geometry and per-vertex colors; test a conservative
    # surface relaxation with explicit orientation and topology gates.
    mesh.export(out/"generated.glb",include_normals=True)
    if resolution>128 or os.getenv("FORGE_RELAX")=="1":
        from trimesh.smoothing import filter_taubin
        original=mesh.copy()
        extent=float(np.linalg.norm(original.extents))
        base_v=original.vertices.copy()
        base_n=original.face_normals.copy()
        base_area=original.area_faces.copy()
        candidate=original.copy()
        filter_taubin(candidate,lamb=.35,nu=.37,iterations=4)
        delta=np.asarray(candidate.vertices)-base_v
        maxdisp=float(np.max(np.linalg.norm(delta,axis=1))/extent)
        flips=int(np.count_nonzero(np.einsum("ij,ij->i",base_n,candidate.face_normals)<=0))
        min_area_ratio=float(np.min(candidate.area_faces/np.maximum(base_area,1e-15)))
        safe=bool(candidate.is_watertight==original.is_watertight and flips==0 and maxdisp<.003 and min_area_ratio>.15 and np.array_equal(original.faces,candidate.faces) and np.array_equal(original.visual.vertex_colors,candidate.visual.vertex_colors))
        report["relaxation"]={"accepted":safe,"max_displacement_over_extent":maxdisp,"flipped_faces":flips,"minimum_area_ratio":min_area_ratio}
        if safe:
            candidate.export(out/"relaxed.glb",include_normals=True)
            # Preserve the untouched reconstruction as the reference.
            check=trimesh.load(out/"relaxed.glb",force="mesh",process=False)
            assert len(check.faces)==len(original.faces)
            assert np.isfinite(check.vertex_normals).all() and check.visual.kind=="vertex"

    # A real mesh and its color attributes must survive export/import.
    import trimesh,numpy as np
    restored=trimesh.load(out/"generated.glb",force="mesh")
    assert len(restored.vertices)==len(mesh.vertices) and len(restored.faces)==len(mesh.faces)
    assert np.isfinite(restored.vertices).all()
    report["components"]=len(restored.split(only_watertight=False))
    report["vertex_color"]=restored.visual.kind=="vertex"
    raw=(out/"generated.glb").read_bytes();jlen=struct.unpack_from("<I",raw,12)[0];gltf=json.loads(raw[20:20+jlen]);report["normals_exported"]=all("NORMAL" in pr["attributes"] for me in gltf["meshes"] for pr in me["primitives"]);assert report["normals_exported"]
    assert report["vertex_color"]
    data=(out/"generated.glb").read_bytes()
    assert struct.unpack_from("<4sII",data)==(b"glTF",2,len(data))
    report.update(real_generation=True,vertices=len(mesh.vertices),faces=len(mesh.faces),watertight=bool(mesh.is_watertight),bytes=len(data),seconds=time.monotonic()-start)
except Exception as e:
    report["error"]=repr(e)
finally:
    report["peak_rss_kib_linux"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (out/"report.json").write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if not report["real_generation"]:raise SystemExit(1)
