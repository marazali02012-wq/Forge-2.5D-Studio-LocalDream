"""F01 alternate text -> actual generated RGB image -> actual TripoSR mesh.
This is NOT direct text-to-3D, and never substitutes a template. Both learned
stages must succeed. SD v1.5 CreativeML OpenRAIL-M use restrictions apply.
"""
import argparse,hashlib,json,os,pathlib,subprocess,sys,time
import numpy as np
from PIL import Image,ImageDraw
import trimesh
MODEL="stable-diffusion-v1-5/stable-diffusion-v1-5"
CASES=["a red ceramic teapot with a curved handle and spout","a green turtle with four legs and a brown shell"]
def images(out):
    import torch
    from diffusers import StableDiffusionPipeline
    from huggingface_hub import HfApi
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    revision=HfApi().model_info(MODEL).sha
    pipe=StableDiffusionPipeline.from_pretrained(MODEL,revision=revision,variant="fp16",use_safetensors=True,torch_dtype=torch.float32).to("cpu")
    pipe.enable_attention_slicing()
    assert pipe.safety_checker is not None
    rows=[]
    for i,prompt in enumerate(CASES):
        t=time.monotonic()
        full=prompt+", isolated single object, three-quarter view, entire object visible, plain light gray studio background, product photograph"
        result=pipe(full,negative_prompt="cropped, multiple objects, text, watermark, busy background",height=512,width=512,num_inference_steps=24,guidance_scale=7.5,generator=torch.Generator("cpu").manual_seed(923+i))
        if result.nsfw_content_detected is None or any(result.nsfw_content_detected):raise RuntimeError("image safety check failed")
        p=out/f"image-{i:02d}.png";result.images[0].save(p)
        rows.append(dict(prompt=prompt,expanded_prompt=full,seed=923+i,image_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),image_seconds=time.monotonic()-t))
        print(rows[-1],flush=True)
    (out/"images.json").write_text(json.dumps(dict(model=MODEL,revision=revision,license="CreativeML OpenRAIL-M",results=rows),indent=2))
def mesh(out):
    report=json.loads((out/"images.json").read_text())
    for i,row in enumerate(report["results"]):
        src=out/f"image-{i:02d}.png";assert hashlib.sha256(src.read_bytes()).hexdigest()==row["image_sha256"]
        dst=out/f"mesh-{i:02d}";env=dict(os.environ,FORGE_IMAGE=str(src.resolve()),FORGE_OUTPUT=str(dst.resolve()),FORGE_RESOLUTION="128")
        env.pop("FORGE_RELAX",None)
        subprocess.run([sys.executable,"studio/cloud-ai/cpu_probe.py"],env=env,check=True,timeout=420)
        data=json.loads((dst/"report.json").read_text())
        assert data["real_generation"] and data["input_sha256"]==row["image_sha256"]
        m=trimesh.load(dst/"generated.glb",force="mesh",process=False)
        assert m.visual.kind=="vertex" and np.isfinite(m.vertices).all() and len(m.faces)>100 and np.all(m.extents>0)
        # TripoSR source axes -> conventional Y-up, as existing editor does.
        m.apply_transform(np.array([[0.,1.,0.,0.],[0.,0.,1.,0.],[1.,0.,0.,0.],[0.,0.,0.,1.]]))
        path=out/f"candidate-{i:02d}.glb";m.export(path,include_normals=True)
        re=trimesh.load(path,force="mesh",process=False)
        assert len(re.faces)==len(m.faces) and re.visual.kind=="vertex"
        row.update(mesh=data,editor_budget_ok=len(re.faces)<=60000 and len(re.vertices)<=30000 and path.stat().st_size<=8000000,mesh_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        v=np.asarray(re.vertices).copy();v-=(v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max()
        f=re.faces;rgb=np.asarray(re.visual.vertex_colors)[f,:3].mean(1).astype(np.uint8)
        sheet=Image.new("RGB",(1500,330),(32,38,48));d=ImageDraw.Draw(sheet)
        ref=Image.open(src);ref.thumbnail((280,280));sheet.paste(ref,((300-ref.width)//2,10));d.text((12,309),"ACTUAL AI IMAGE",fill="white")
        for j,angle in enumerate([0,90,180,45],1):
            a=np.deg2rad(angle);x=v[:,0]*np.cos(a)-v[:,2]*np.sin(a);z=v[:,0]*np.sin(a)+v[:,2]*np.cos(a)
            pp=np.stack([j*300+150+125*x,150-125*v[:,1]],1)
            for k in np.argsort(z[f].mean(1)):d.polygon([tuple(pp[q]) for q in f[k]],fill=tuple(map(int,rgb[k])))
            d.text((j*300+12,309),str(angle)+" DEG",fill="white")
        sheet.save(out/f"candidate-{i:02d}.png")
        (out/"report.json").write_text(json.dumps(report,indent=2))
    assert len({x["mesh_sha256"] for x in report["results"]})==len(CASES)
    if not all(r["editor_budget_ok"] for r in report["results"]):raise SystemExit("editor budget exceeded")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("stage",choices=["images","mesh"]);p.add_argument("out",type=pathlib.Path);a=p.parse_args();a.out.mkdir(exist_ok=True)
    (images if a.stage=="images" else mesh)(a.out)
