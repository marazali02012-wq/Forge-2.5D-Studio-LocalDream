"""F01 experimental direct text-to-real-3D via public OpenAI Shap-E weights.
No templates, no paid inference endpoint, no fallback geometry.
"""
import argparse,gc,hashlib,json,pathlib,resource,time
import numpy as np
import torch,trimesh
from diffusers import ShapEPipeline
from huggingface_hub import HfApi
from PIL import Image,ImageDraw

def views(mesh,path):
    v=np.asarray(mesh.vertices).copy();v-=(v.min(0)+v.max(0))/2
    v*=2/np.ptp(v,axis=0).max();f=np.asarray(mesh.faces)
    # Shap-E returns linear vertex colors; display in sRGB.
    rgb=np.asarray(mesh.visual.vertex_colors)[f,:3].mean(1)/255
    rgb=np.rint(np.where(rgb<=.0031308,12.92*rgb,1.055*np.maximum(rgb,0)**(1/2.4)-.055)*255).astype(np.uint8)
    im=Image.new("RGB",(1200,320),(32,38,48));d=ImageDraw.Draw(im)
    for i,(label,angle) in enumerate([("FRONT",0),("SIDE",90),("BACK",180),("3/4",45)]):
        a=np.deg2rad(angle);x=v[:,0]*np.cos(a)-v[:,2]*np.sin(a);z=v[:,0]*np.sin(a)+v[:,2]*np.cos(a)
        p=np.stack([i*300+150+x*125,150-v[:,1]*125],1)
        for k in np.argsort(z[f].mean(1)):d.polygon([tuple(p[j]) for j in f[k]],fill=tuple(map(int,rgb[k])))
        d.text((i*300+12,298),label,fill="white")
    im.save(path)

def main():
    p=argparse.ArgumentParser();p.add_argument("output",type=pathlib.Path);p.add_argument("prompts",nargs="+");p.add_argument("--steps",type=int,default=24);p.add_argument("--seed",type=int,default=923);p.add_argument("--grid",type=int,choices=[64,96,128],default=96);a=p.parse_args()
    if not 8<=a.steps<=64 or any(not 1<=len(t.strip())<=300 for t in a.prompts):raise ValueError("Invalid prompt/steps")
    a.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    # Resolve and record exact model revision; use only public safetensors.
    revision=HfApi().model_info("openai/shap-e").sha
    t=time.monotonic()
    # The upstream model index has duplicate renderer aliases. Load the
    # actual published safetensors components explicitly; never load pickle.
    from huggingface_hub import snapshot_download
    from diffusers import PriorTransformer,HeunDiscreteScheduler
    from diffusers.pipelines.shap_e.renderer import ShapERenderer
    from transformers import CLIPTextModelWithProjection,CLIPTokenizer
    base=pathlib.Path(snapshot_download("openai/shap-e",revision=revision,allow_patterns=["prior/config.json","prior/*.safetensors","renderer/config.json","renderer/*.safetensors","text_encoder/config.json","text_encoder/*.safetensors","tokenizer/*.json","tokenizer/*.txt","scheduler/*.json"]))
    opts=dict(variant="fp16",use_safetensors=True,torch_dtype=torch.float32,local_files_only=True)
    prior=PriorTransformer.from_pretrained(base/"prior",**opts)
    renderer=ShapERenderer.from_pretrained(base/"renderer",**opts)
    # CI log confirmed the published fp16 safetensors are missing both
    # deterministic marching-cubes buffers. Zero masks mean no triangles.
    from shap_e_mc_lookup import create_mc_lookup_table
    cases,masks=create_mc_lookup_table()
    renderer.mesh_decoder.cases.copy_(cases)
    renderer.mesh_decoder.masks.copy_(masks)
    assert masks.any() and not masks[0].any() and not masks[255].any()
    # Validate the actual decoder BEFORE running the expensive learned prior.
    q=torch.linspace(-1,1,17);x,y,z=torch.meshgrid(q,q,q,indexing="ij")
    check=renderer.mesh_decoder(.55**2-x*x-y*y-z*z,torch.tensor([-1.,-1.,-1.]),torch.tensor([2.,2.,2.]))
    assert len(check.faces)>100 and torch.isfinite(check.verts).all()
    print("Restored official marching-cubes buffers; decoder preflight:",len(check.verts),len(check.faces),flush=True)
    del check
    encoder=CLIPTextModelWithProjection.from_pretrained(base/"text_encoder",**opts)
    tokenizer=CLIPTokenizer.from_pretrained(base/"tokenizer",local_files_only=True)
    scheduler=HeunDiscreteScheduler.from_pretrained(base/"scheduler",local_files_only=True)
    pipe=ShapEPipeline(prior=prior,text_encoder=encoder,tokenizer=tokenizer,scheduler=scheduler,shap_e_renderer=renderer).to("cpu")
    report={"engine":"openai/shap-e","revision":revision,"device":"cpu","load_seconds":time.monotonic()-t,"results":[]}
    for i,prompt in enumerate(a.prompts):
        t=time.monotonic()
        with torch.no_grad():
            lat=pipe(prompt,num_inference_steps=a.steps,guidance_scale=15.0,generator=torch.Generator(device="cpu").manual_seed(a.seed),output_type="latent").images
            assert torch.isfinite(lat).all()
            from safetensors.torch import save_file
            save_file({"latent":lat.detach().cpu().contiguous()},str(a.output/("text-%02d-latent.safetensors"%i)))
            raw=pipe.shap_e_renderer.decode_to_mesh(lat[:1],torch.device("cpu"),grid_size=a.grid,query_batch_size=4096)
        v=raw.verts.detach().cpu().numpy();f=raw.faces.detach().cpu().numpy()
        c=np.stack([raw.vertex_channels[k].detach().cpu().numpy() for k in "RGB"],axis=1)
        assert v.ndim==2 and v.shape[1]==3 and f.ndim==2 and f.shape[1]==3 and c.shape==v.shape
        assert np.isfinite(v).all() and np.isfinite(c).all() and np.all(np.ptp(v,axis=0)>1e-5) and len(f)>100 and f.min()>=0 and f.max()<len(v)
        # Z-up source to conventional glTF Y-up, proper rotation.
        v=v[:,[0,2,1]].copy();v[:,2]*=-1
        mesh=trimesh.Trimesh(v,f,vertex_colors=np.rint(np.clip(c,0,1)*255).astype(np.uint8),process=False)
        if mesh.is_watertight and mesh.volume<0:mesh.invert()
        dst=a.output/("text-%02d.glb"%i);mesh.export(dst,include_normals=True)
        again=trimesh.load(dst,force="mesh",process=False)
        assert len(again.faces)==len(mesh.faces) and again.visual.kind=="vertex" and np.isfinite(again.vertices).all()
        views(mesh,a.output/("text-%02d.png"%i))
        report["results"].append(dict(prompt=prompt,seed=a.seed,steps=a.steps,grid=a.grid,vertices=len(v),faces=len(f),extents=mesh.extents.tolist(),watertight=bool(mesh.is_watertight),seconds=time.monotonic()-t,bytes=dst.stat().st_size,sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        (a.output/"report.json").write_text(json.dumps(report,indent=2));print(json.dumps(report["results"][-1]),flush=True)
        del lat,raw,mesh,again;gc.collect()
    if len(report["results"])>1:assert len({r["sha256"] for r in report["results"]})==len(report["results"])
if __name__=="__main__":main()
