"""F01 private automatic GPU reproduction; research evaluation only, no commercial rights asserted."""
import pathlib, torch
base=pathlib.Path("/tmp/forge-f01-kaggle")
base.mkdir(exist_ok=True)
assert pathlib.Path("/kaggle/working").is_dir(),"Use Kaggle"
assert torch.cuda.is_available(),"Enable GPU"
print("Detected GPUs:",torch.cuda.device_count(),flush=True)
import os, sys, subprocess, pathlib, hashlib, urllib.request, shutil
root=pathlib.Path("/tmp/forge-f01-kaggle/forge-f01-triposg-r2")
venv=pathlib.Path("/tmp/forge-f01-kaggle/forge-f01-py310")
rev="fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c"
env=dict(os.environ,HF_HUB_DISABLE_XET="1",PYTHONNOUSERSITE="1",PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
env.pop("PYTHONPATH",None)
env["CUDA_VISIBLE_DEVICES"]="0"
def run(args,cwd=None,timeout=1800):
    print("RUN:", " ".join(map(str,args)), flush=True)
    subprocess.run(list(map(str,args)),cwd=cwd,env=env,check=True,timeout=timeout)
assert torch.cuda.is_available()
assert shutil.disk_usage("/tmp/forge-f01-kaggle").free>12*2**30, "12 GiB boş disk gerekli"
# Keep Colab kernel Python untouched; create an independent Python 3.10 process.
run([sys.executable,"-m","pip","install","uv==0.9.26"])
run([sys.executable,"-m","uv","python","install","3.10"])
if not (venv/"bin/python").exists():
    run([sys.executable,"-m","uv","venv","--python","3.10","--seed",venv])
py=venv/"bin/python"
run([py,"-c","import sys; assert sys.version_info[:2]==(3,10); print(sys.version)"])
run([py,"-m","pip","install","torch==2.5.1","torchvision==0.20.1","--index-url","https://download.pytorch.org/whl/cu124"])
run([py,"-m","pip","install","numpy==1.26.4","scipy==1.11.4","diffusers==0.32.2","transformers==4.49.0","huggingface-hub==0.28.1","safetensors==0.5.3","accelerate==1.4.0","peft==0.14.0","einops==0.8.1","opencv-python-headless==4.10.0.84","trimesh==4.5.3","omegaconf==2.3.0","scikit-image==0.24.0","jaxtyping==0.2.38","typeguard==2.13.3","pymeshlab==2022.2.post4","Pillow==11.1.0"])
if not root.exists():
    run(["git","clone","https://github.com/VAST-AI-Research/TripoSG.git",root])
run(["git","-C",root,"checkout","--detach",rev])
assert subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()==rev
# Publisher-provided CPython 3.10 binary; verify its published SHA256.
wheel=pathlib.Path("/tmp/forge-f01-kaggle/diso-0.1.4-cp310-cp310-linux_x86_64.whl")
urllib.request.urlretrieve("https://huggingface.co/spaces/VAST-AI/TripoSG/resolve/d51c5f2f4d5182f925a403b286d1e9faf519aaa2/"+wheel.name,wheel)
assert hashlib.sha256(wheel.read_bytes()).hexdigest()=="8814512bb12ef32fe2aa8572db76cf73ee5e7f604764a37337bfd087e667dce8", "DISO wheel checksum mismatch"
run([py,"-m","pip","install","--no-deps",wheel])
run([py,"-m","pip","check"])
# Verify real CUDA and compiled extension, not only import.
run([py,"-c","import torch; from diso import DiffDMC; assert torch.cuda.is_available(); x=torch.arange(1024,device='cuda'); assert x.sum().item()==523776; d=DiffDMC(dtype=torch.float32).cuda(); print('PY310 CUDA OK',torch.__version__,torch.version.cuda,torch.cuda.get_device_name(0))"])
run([py,"-c","from scripts.inference_triposg import run_triposg; print('TripoSG import OK')"],cwd=root)
print("AYRI PYTHON 3.10 KURULUMU VE CUDA KONTROLÜ GEÇTİ")


runner = f'FORGE_JOB_ID={FORGE_JOB_ID!r}\nFORGE_IMAGE_SHA256={FORGE_IMAGE_SHA256!r}\n' + '''
import json,hashlib,time,pathlib
import numpy as np, torch,trimesh
from PIL import Image,ImageOps
from huggingface_hub import snapshot_download
from safetensors.torch import load_file
from scripts.inference_triposg import prepare_image,BriaRMBG,TripoSGPipeline
root=pathlib.Path.cwd()
out=pathlib.Path("/kaggle/working/forge-f01-auto")
out.mkdir(exist_ok=False)
inputs=[p for p in pathlib.Path("/kaggle/input").rglob("*") if p.is_file() and p.suffix.lower() in (".png",".jpg",".jpeg",".webp")]
assert len(inputs)==1,"Expected exactly one private image"
raw=inputs[0]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(raw)==FORGE_IMAGE_SHA256,"Unexpected input bytes"
Image.MAX_IMAGE_PIXELS=12_000_000
src=out/"source.png"
with Image.open(raw) as im:
    assert im.format in ("PNG","JPEG","WEBP")
    ImageOps.exif_transpose(im).convert("RGBA").save(src)
assert torch.cuda.is_available()
t=time.monotonic()
tripo_rev="2c1c516d22d58db486a058d98d31bb6177344e06"
bria_rev="9921b8c152a4b24e3f559592d800f42ed7e06aeb"
tripo=snapshot_download("VAST-AI/TripoSG",revision=tripo_rev,allow_patterns=["*.json","*.safetensors","*.safetensors.index.json","*.txt"],local_dir=str(root/"pretrained_weights/TripoSG-safe"))
bria=snapshot_download("briaai/RMBG-1.4",revision=bria_rev,allow_patterns=["model.safetensors","config.json","README.md"],local_dir=str(root/"pretrained_weights/RMBG-safe"))
rmbg=BriaRMBG()
rmbg.load_state_dict(load_file(str(pathlib.Path(bria)/"model.safetensors")),strict=True)
rmbg=rmbg.eval().to("cuda")
pipe=TripoSGPipeline.from_pretrained(tripo,use_safetensors=True,local_files_only=True,torch_dtype=torch.float16).to("cuda")
img=prepare_image(str(src),bg_color=np.array([1.,1.,1.]),rmbg_net=rmbg)
result=pipe(image=img,generator=torch.Generator(device=pipe.device).manual_seed(42),num_inference_steps=50,guidance_scale=7.0,use_flash_decoder=False,dense_octree_depth=8,hierarchical_octree_depth=9)
m=result.meshes[0]
assert len(m.faces)>100 and np.isfinite(m.vertices).all() and np.all(m.extents>0)
dest=out/"model.glb";m.export(dest,include_normals=True)
q=trimesh.load(dest,force="mesh",process=False)
assert len(q.faces)==len(m.faces) and np.isfinite(q.vertices).all()
report=dict(job_id=FORGE_JOB_ID,actual_inference=True,engine="TripoSG",model_revision=tripo_rev,background_revision=bria_rev,decoder="official_hierarchical_lewiner",gpu=torch.cuda.get_device_name(0),original_sha256=sha(raw),source_sha256=sha(src),glb_sha256=sha(dest),bytes=dest.stat().st_size,faces=len(q.faces),vertices=len(q.vertices),watertight=bool(q.is_watertight),seconds=time.monotonic()-t,visual_accepted=False,editor_accepted=False)
(out/"report.json").write_text(json.dumps(report,indent=2))
print("FORGE_AUTO_MODEL_READY",flush=True)
'''
compile(runner,"forge_auto_inference.py","exec")
script=root/"forge_auto_inference.py"
script.write_text(runner)
run([py,"-u",script],cwd=root,timeout=1800)
assert pathlib.Path("/kaggle/working/forge-f01-auto/report.json").is_file()
