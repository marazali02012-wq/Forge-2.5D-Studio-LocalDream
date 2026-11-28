"""F01 compare extraction grids using genuine saved Shap-E latents.
The learned prior is NOT rerun; no geometry fabrication or shape templates.
"""
import argparse,json,pathlib,time
import numpy as np,torch,trimesh
from safetensors.torch import load_file
from huggingface_hub import snapshot_download
from diffusers.pipelines.shap_e.renderer import ShapERenderer
from shap_e_mc_lookup import create_mc_lookup_table
from shap_e_text_probe import views

def main():
    p=argparse.ArgumentParser();p.add_argument("input",type=pathlib.Path);p.add_argument("output",type=pathlib.Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(4);torch.set_num_interop_threads(1)
    prior=json.loads((a.input/"report.json").read_text());revision=prior["revision"]
    base=pathlib.Path(snapshot_download("openai/shap-e",revision=revision,allow_patterns=["renderer/config.json","renderer/*.safetensors"]))
    renderer=ShapERenderer.from_pretrained(base/"renderer",variant="fp16",use_safetensors=True,torch_dtype=torch.float32,local_files_only=True).to("cpu").eval()
    cases,masks=create_mc_lookup_table();renderer.mesh_decoder.cases.copy_(cases);renderer.mesh_decoder.masks.copy_(masks)
    report={"source_revision":revision,"source_run":46091269501,"results":[]}
    for i,source in enumerate(prior["results"]):
        latent=load_file(str(a.input/("text-%02d-latent.safetensors"%i)))["latent"]
        assert torch.isfinite(latent).all()
        for grid in [96,128]:
            t=time.monotonic()
            with torch.no_grad():raw=renderer.decode_to_mesh(latent[:1],torch.device("cpu"),grid_size=grid,query_batch_size=4096)
            v=raw.verts.cpu().numpy()[:,[0,2,1]].copy();v[:,2]*=-1;f=raw.faces.cpu().numpy()
            c=np.stack([raw.vertex_channels[k].cpu().numpy() for k in "RGB"],1)
            assert len(f)>100 and np.isfinite(v).all() and np.isfinite(c).all() and np.all(np.ptp(v,axis=0)>0)
            m=trimesh.Trimesh(v,f,vertex_colors=np.rint(np.clip(c,0,1)*255).astype(np.uint8),process=False)
            if m.is_watertight and m.volume<0:m.invert()
            name=f"text-{i:02d}-grid{grid}";dst=a.output/(name+".glb")
            m.export(dst,include_normals=True);views(m,a.output/(name+".png"))
            again=trimesh.load(dst,force="mesh",process=False)
            assert len(again.faces)==len(m.faces) and again.visual.kind=="vertex" and np.isfinite(again.vertices).all()
            parts=m.split(only_watertight=False,repair=False);areas=sorted([float(q.area) for q in parts],reverse=True)
            report["results"].append(dict(prompt=source["prompt"],grid=grid,faces=len(m.faces),vertices=len(m.vertices),watertight=bool(m.is_watertight),components=len(parts),largest_component_area_ratio=areas[0]/sum(areas),editor_budget_ok=len(m.vertices)<=30000 and len(m.faces)<=60000,seconds=time.monotonic()-t))
            (a.output/"report.json").write_text(json.dumps(report,indent=2));print(report["results"][-1],flush=True)
if __name__=="__main__":main()
