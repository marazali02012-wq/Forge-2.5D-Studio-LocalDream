"""Kaggle isolated TripoSG R3 reproduction, one T4, no paid service.
Based on actual Colab R2 setup and R3 hierarchical fix; Kaggle execution pending.
Research-only RMBG weights: verify commercial rights before production use.
"""
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

# The R2 runner is written only, not executed (flash decoder failed on T4).
runner="import json, hashlib, time, pathlib, shutil, sys\nimport torch, numpy as np, trimesh\nfrom huggingface_hub import snapshot_download\nfrom safetensors.torch import load_file\nfrom scripts.inference_triposg import run_triposg, BriaRMBG, TripoSGPipeline\nroot=pathlib.Path.cwd()\nout=pathlib.Path(\"/kaggle/working/forge-f01-gpu-evidence-r2\");out.mkdir(exist_ok=True)\nsrc=root/\"assets/example_data/hjswed.png\"\nassert src.is_file() and torch.cuda.is_available()\nt=time.monotonic()\ntripo_rev=\"2c1c516d22d58db486a058d98d31bb6177344e06\"\nbria_rev=\"9921b8c152a4b24e3f559592d800f42ed7e06aeb\"\ntripo=snapshot_download(\"VAST-AI/TripoSG\",revision=tripo_rev,allow_patterns=[\"*.json\",\"*.safetensors\",\"*.safetensors.index.json\",\"*.txt\"],local_dir=str(root/\"pretrained_weights/TripoSG-safe\"))\nbria=snapshot_download(\"briaai/RMBG-1.4\",revision=bria_rev,allow_patterns=[\"model.safetensors\",\"config.json\",\"README.md\"],local_dir=str(root/\"pretrained_weights/RMBG-safe\"))\n# Only safetensors weights; no pickle fallback or remote Python code.\nrmbg=BriaRMBG()\nrmbg.load_state_dict(load_file(str(pathlib.Path(bria)/\"model.safetensors\")),strict=True)\nrmbg=rmbg.eval().to(\"cuda\")\npipe=TripoSGPipeline.from_pretrained(tripo,use_safetensors=True,local_files_only=True,torch_dtype=torch.float16).to(\"cuda\")\nm=run_triposg(pipe,str(src),rmbg,seed=42,num_inference_steps=50,faces=-1)\nassert len(m.faces)>100 and np.isfinite(m.vertices).all() and np.all(m.extents>0)\ndest=out/\"actual_triposg_demo.glb\";m.export(dest,include_normals=True)\nq=trimesh.load(dest,force=\"mesh\",process=False);assert len(q.faces)==len(m.faces)\nshutil.copy2(src,out/\"source.png\")\nsha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()\nreport=dict(actual_inference=True,engine=\"TripoSG\",model_revision=tripo_rev,background_revision=bria_rev,gpu=torch.cuda.get_device_name(0),python=sys.version,torch=torch.__version__,source_sha256=sha(src),glb_sha256=sha(dest),faces=len(m.faces),vertices=len(m.vertices),watertight=bool(m.is_watertight),seconds=time.monotonic()-t,visual_accepted=False,editor_accepted=False,benchmark_10_completed=False)\n(out/\"report.json\").write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))\n"
compile(runner,"forge_actual_inference.py","exec")
(root/"forge_actual_inference.py").write_text(runner)
fix="\"\"\"Recover R2 on the SAME Colab runtime. Official TripoSG non-flash path.\nNever changes the R2 source, weights, environment or production API.\n\"\"\"\nimport pathlib, sys, json, subprocess, os, shutil\nroot=pathlib.Path(\"/tmp/forge-f01-kaggle/forge-f01-triposg-r2\")\noriginal=root/\"forge_actual_inference.py\"\nassert original.is_file(), \"R2 setup and runner must exist in the current Colab session\"\nassert pathlib.Path(sys.executable).parent==pathlib.Path(\"/tmp/forge-f01-kaggle/forge-f01-py310/bin\"), \"Use the existing Python 3.10 environment\"\nsource=original.read_text()\nold=\"m=run_triposg(pipe,str(src),rmbg,seed=42,num_inference_steps=50,faces=-1)\"\nnew=\"\"\"from scripts.inference_triposg import prepare_image\nimg=prepare_image(str(src),bg_color=np.array([1.,1.,1.]),rmbg_net=rmbg)\nprint(\"Official hierarchical decoder; dense depth 8, final depth 9; DISO not called\",flush=True)\nresult=pipe(image=img,generator=torch.Generator(device=pipe.device).manual_seed(42),num_inference_steps=50,guidance_scale=7.0,use_flash_decoder=False,dense_octree_depth=8,hierarchical_octree_depth=9)\nm=result.meshes[0]\nassert len(m.faces)>100 and np.isfinite(m.vertices).all()\nprint(\"Actual hierarchical mesh:\",len(m.faces),len(m.vertices),flush=True)\"\"\"\nassert source.count(old)==1, \"R2 source changed; refusing ambiguous patch\"\nsource=source.replace(old,new).replace(\"/kaggle/working/forge-f01-gpu-evidence-r2\",\"/kaggle/working/forge-f01-gpu-evidence-r3\").replace(\"visual_accepted=False,\",\"decoder=\\\"official_hierarchical_lewiner\\\",dense_octree_depth=8,hierarchical_octree_depth=9,visual_accepted=False,\")\ncompile(source,\"forge_hierarchical_inference.py\",\"exec\")\nscript=root/\"forge_hierarchical_inference.py\";script.write_text(source)\nout=pathlib.Path(\"/kaggle/working/forge-f01-gpu-evidence-r3\");out.mkdir(exist_ok=True)\n# Avoid stale success files.\nfor name in (\"report.json\",\"actual_triposg_demo.glb\"):\n    (out/name).unlink(missing_ok=True)\nenv=dict(os.environ,PYTHONUNBUFFERED=\"1\",HF_HUB_DISABLE_XET=\"1\",PYTHONNOUSERSITE=\"1\")\nenv.pop(\"PYTHONPATH\",None)\nwith (out/\"inference.log\").open(\"w\") as log:\n    p=subprocess.Popen([sys.executable,\"-u\",str(script)],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)\n    for line in p.stdout:\n        log.write(line);log.flush();print(line,end=\"\",flush=True)\n    status=p.wait()\nif status:raise SystemExit(status)\nassert (out/\"report.json\").is_file() and (out/\"actual_triposg_demo.glb\").is_file()\nreport=json.loads((out/\"report.json\").read_text())\nassert report[\"actual_inference\"] and report[\"decoder\"]==\"official_hierarchical_lewiner\"\nprint(\"Actual GLB saved. Visual quality and mobile budget remain unverified.\",flush=True)\nshutil.make_archive(\"/kaggle/working/Forge_F01_Kaggle_Evidence_R1\",\"zip\",out)\n"
compile(fix,"kaggle_hierarchical_fix.py","exec")
fixpath=base/"kaggle_hierarchical_fix.py"
fixpath.write_text(fix)
run([py,"-u",fixpath],cwd=root,timeout=1800)
assert pathlib.Path("/kaggle/working/Forge_F01_Kaggle_Evidence_R1.zip").is_file()
print("KAGGLE REAL GLB EVIDENCE READY; visual approval pending",flush=True)
