"""Recover R2 on the SAME Colab runtime. Official TripoSG non-flash path.
Never changes the R2 source, weights, environment or production API.
"""
import pathlib, sys, json, subprocess, os, shutil
root=pathlib.Path("/content/forge-f01-triposg-r2")
original=root/"forge_actual_inference.py"
assert original.is_file(), "R2 setup and runner must exist in the current Colab session"
assert pathlib.Path(sys.executable).parent==pathlib.Path("/content/forge-f01-py310/bin"), "Use the existing Python 3.10 environment"
source=original.read_text()
old="m=run_triposg(pipe,str(src),rmbg,seed=42,num_inference_steps=50,faces=-1)"
new="""from scripts.inference_triposg import prepare_image
img=prepare_image(str(src),bg_color=np.array([1.,1.,1.]),rmbg_net=rmbg)
print("Official hierarchical decoder; dense depth 8, final depth 9; DISO not called",flush=True)
result=pipe(image=img,generator=torch.Generator(device=pipe.device).manual_seed(42),num_inference_steps=50,guidance_scale=7.0,use_flash_decoder=False,dense_octree_depth=8,hierarchical_octree_depth=9)
m=result.meshes[0]
assert len(m.faces)>100 and np.isfinite(m.vertices).all()
print("Actual hierarchical mesh:",len(m.faces),len(m.vertices),flush=True)"""
assert source.count(old)==1, "R2 source changed; refusing ambiguous patch"
source=source.replace(old,new).replace("/content/forge-f01-gpu-evidence-r2","/content/forge-f01-gpu-evidence-r3").replace("visual_accepted=False,","decoder=\"official_hierarchical_lewiner\",dense_octree_depth=8,hierarchical_octree_depth=9,visual_accepted=False,")
compile(source,"forge_hierarchical_inference.py","exec")
script=root/"forge_hierarchical_inference.py";script.write_text(source)
out=pathlib.Path("/content/forge-f01-gpu-evidence-r3");out.mkdir(exist_ok=True)
# Avoid stale success files.
for name in ("report.json","actual_triposg_demo.glb"):
    (out/name).unlink(missing_ok=True)
env=dict(os.environ,PYTHONUNBUFFERED="1",HF_HUB_DISABLE_XET="1",PYTHONNOUSERSITE="1")
env.pop("PYTHONPATH",None)
with (out/"inference.log").open("w") as log:
    p=subprocess.Popen([sys.executable,"-u",str(script)],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    for line in p.stdout:
        log.write(line);log.flush();print(line,end="",flush=True)
    status=p.wait()
if status:raise SystemExit(status)
assert (out/"report.json").is_file() and (out/"actual_triposg_demo.glb").is_file()
report=json.loads((out/"report.json").read_text())
assert report["actual_inference"] and report["decoder"]=="official_hierarchical_lewiner"
print("Actual GLB saved. Visual quality and mobile budget remain unverified.",flush=True)
shutil.make_archive("/content/Forge_F01_GPU_Evidence_R3","zip",out)
