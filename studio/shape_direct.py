"""Independent Shap-E text-to-3D benchmark; no image conditioning or fake geometry.
Usage: python shape_direct.py LOCAL_MODEL_DIR PROMPT OUTPUT.glb
Model download is an explicit provisioning step, not part of generation.
"""
import argparse, json, time, io, hashlib
from pathlib import Path

def generate(model_dir,prompt,seed=42,steps=32):
    root=Path(model_dir).resolve()
    if not (root/'model_index.json').is_file():raise ValueError('Local Shap-E model missing')
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=500:raise ValueError('Invalid prompt')
    if steps not in (16,32,64):raise ValueError('Unsupported steps')
    import torch, trimesh, numpy as np
    from diffusers import ShapEPipeline
    from diffusers.utils import export_to_ply
    import tempfile
    torch.set_num_threads(2)
    pipe=ShapEPipeline.from_pretrained(str(root),torch_dtype=torch.float32,local_files_only=True,use_safetensors=False).to('cpu')
    start=time.monotonic()
    with torch.inference_mode():
        result=pipe(prompt.strip(),guidance_scale=15.,num_inference_steps=steps,frame_size=256,output_type='mesh',generator=torch.Generator(device='cpu').manual_seed(seed)).images[0]
    with tempfile.TemporaryDirectory() as tmp:
        ply=str(Path(tmp)/'mesh.ply')
        export_to_ply(result,ply)
        mesh=trimesh.load(ply,force='mesh',process=False)
    if len(mesh.vertices)<100 or len(mesh.faces)<100 or not np.isfinite(mesh.vertices).all() or min(mesh.extents)<=1e-5:raise ValueError('Degenerate neural mesh')
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    # Shap-E provides vertex colors, not an authored UV/PBR texture.
    raw=mesh.export(file_type='glb')
    check=trimesh.load(io.BytesIO(raw),file_type='glb',force='mesh',process=True)
    if len(check.faces)!=len(mesh.faces):raise ValueError('GLB faces changed')
    r=np.linalg.norm(check.vertices-check.bounds.mean(axis=0),axis=1)
    report=dict(engine='Shap-E',mock=False,scope='direct neural text to vertex-colored GLB; UV/PBR not generated',prompt=prompt,seed=seed,steps=steps,seconds=round(time.monotonic()-start,2),triangles=len(check.faces),components=len(check.split(only_watertight=False)),watertight=bool(check.is_watertight),hull_fill=round(abs(float(check.volume))/max(float(check.convex_hull.volume),1e-12),5) if check.is_watertight else None,radial_p05_p95=round(float(np.quantile(r,.05)/max(np.quantile(r,.95),1e-12)),5),vertex_colors=mesh.visual.kind=='vertex',sha256=hashlib.sha256(raw).hexdigest(),visual_review_required=True)
    return raw,report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('model_dir');p.add_argument('prompt');p.add_argument('output');p.add_argument('--steps',type=int,default=32)
    a=p.parse_args();raw,report=generate(a.model_dir,a.prompt,steps=a.steps)
    Path(a.output).write_bytes(raw);Path(a.output).with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
