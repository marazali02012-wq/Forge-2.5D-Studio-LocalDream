"""F01 same-input mechanical resolution ablation; never accepts quality by triangle count."""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image
from scipy.spatial import cKDTree
from mechanical_photo_qa import render

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def metrics(m):
    a=np.asarray(m.area_faces)
    if not np.isfinite(m.vertices).all() or not np.isfinite(a).all():
        raise ValueError("nonfinite geometry")
    return dict(faces=len(m.faces),vertices=len(m.vertices),
        components=len(m.split(only_watertight=False)),watertight=bool(m.is_watertight),
        consistent_winding=bool(m.is_winding_consistent),degenerate_faces=int((a<=1e-12).sum()),
        surface_area=float(a.sum()),extents=m.extents.tolist(),
        editor_budget_ok=len(m.faces)<=60000 and len(m.vertices)<=30000)

def surface_samples(m,n=20000):
    rng=np.random.default_rng(20261128)
    areas=np.asarray(m.area_faces)
    idx=rng.choice(len(areas),size=n,p=areas/areas.sum())
    uv=rng.random((n,2));uv[uv.sum(1)>1]=1-uv[uv.sum(1)>1]
    tri=m.triangles[idx]
    return tri[:,0]+uv[:,0,None]*(tri[:,1]-tri[:,0])+uv[:,1,None]*(tri[:,2]-tri[:,0])

def compare(a,b):
    # Sampled symmetric distance is a change metric, NOT ground-truth accuracy.
    x,y=surface_samples(a),surface_samples(b)
    d=np.r_[cKDTree(x).query(y)[0],cKDTree(y).query(x)[0]]
    return dict(sample_distance_p95_pct=float(np.quantile(d,.95)/np.linalg.norm(a.extents)*100),
        sample_distance_mean_pct=float(d.mean()/np.linalg.norm(a.extents)*100))

def main():
    p=argparse.ArgumentParser();p.add_argument("baseline",type=Path);p.add_argument("out",type=Path);a=p.parse_args()
    a.out.mkdir(exist_ok=False);report={}
    # QA-only worker: reuse the exact RGB tensor source saved by the baseline,
    # instead of running potentially variable background removal a second time.
    worker_source=Path("studio/cloud-ai/cpu_probe.py").read_text()
    anchor='    if sample:\n'
    assert worker_source.count(anchor)==1,"upstream worker changed"
    worker_source=worker_source.replace(anchor,'''    if os.getenv("FORGE_QA_FROZEN_RGB"):
        frozen=pathlib.Path(os.environ["FORGE_QA_FROZEN_RGB"])
        with Image.open(frozen) as saved:
            assert saved.mode=="RGB" and saved.format=="PNG"
            im=saved.copy()
        report["input_sha256"]=hashlib.sha256(frozen.read_bytes()).hexdigest()
        report["qa_frozen_rgb"]=True
    elif sample:
''',1)
    compile(worker_source,"frozen_worker.py","exec")
    worker=a.out/"frozen_worker.py";worker.write_text(worker_source)
    for name,resolutions in [("vise",[192]),("gears",[192,256])]:
        base=a.baseline/name;source=base/"source.png";base_glb=base/"generated.glb"
        original=trimesh.load(base_glb,force="mesh",process=False)
        old=json.loads((base/"report.json").read_text())
        assert old["real_generation"] and old["input_sha256"]==sha(source)
        frozen=base/"input.png"
        with Image.open(frozen) as im:assert im.mode=="RGB" and im.format=="PNG"
        folder=a.out/name;folder.mkdir()
        render(original,source,folder/"128.png")
        report[name]={"input_sha256":sha(source),"baseline_sha256":sha(base_glb),"frozen_rgb_sha256":sha(frozen),"128":metrics(original)}
        for res in resolutions:
            dest=folder/str(res);dest.mkdir()
            row={"resolution":res}
            try:
                env=dict(os.environ,FORGE_QA_FROZEN_RGB=str(frozen.resolve()),FORGE_OUTPUT=str(dest.resolve()),FORGE_RESOLUTION=str(res))
                env.pop("FORGE_IMAGE",None)
                env.pop("FORGE_RELAX",None)
                t=time.monotonic()
                r=subprocess.run([sys.executable,str(worker.resolve())],env=env,timeout=480,capture_output=True,text=True)
                (dest/"inference.log").write_text(r.stdout+"\n"+r.stderr)
                if r.returncode:raise RuntimeError("real inference failed")
                raw=json.loads((dest/"report.json").read_text())
                assert raw["real_generation"] and raw["qa_frozen_rgb"] and raw["input_sha256"]==sha(frozen) and raw["resolution"]==res
                with Image.open(dest/"input.png") as actual,Image.open(frozen) as expected:
                    assert actual.mode==expected.mode and actual.size==expected.size and np.array_equal(np.asarray(actual),np.asarray(expected)),"frozen RGB pixels changed"
                glb=dest/"generated.glb";m=trimesh.load(glb,force="mesh",process=False)
                assert m.visual.kind=="vertex" and len(m.faces)>100
                render(m,source,dest/"visual.png")
                row.update(metrics(m),**compare(original,m),seconds=time.monotonic()-t,actual_inference=True,sha256=sha(glb),bytes=glb.stat().st_size)
                row["editor_budget_ok"]=row["editor_budget_ok"] and glb.stat().st_size<=8000000
                row["visual_accepted"]=False
            except Exception as e:row.update(actual_inference=False,error=repr(e))
            report[name][str(res)]=row
            (a.out/"report.json").write_text(json.dumps(report,indent=2));print(name,row,flush=True)
    if not all(report[n][str(r)]["actual_inference"] for n,rs in [("vise",[192]),("gears",[192,256])] for r in rs):raise SystemExit(1)
if __name__=="__main__":main()
