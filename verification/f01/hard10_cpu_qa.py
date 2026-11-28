"""Hard public inputs; actual TripoSR only, no template/ground-truth substitution."""
import hashlib,json,os,sys,subprocess,time,urllib.request,urllib.parse,io
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageOps
import trimesh
HERE=Path(__file__).resolve().parent
MAN=json.loads((HERE/"hard10_manifest.json").read_text())
ROOT=Path("f01-hard10-evidence")
Image.MAX_IMAGE_PIXELS=50_000_000

def acquire(case,out):
    # Commons original media path is keyed by the MD5 of its canonical filename.
    # Source description and exact filename remain in the evidence.
    name=case["file"].replace(" ","_")
    h=hashlib.md5(name.encode()).hexdigest()
    url="https://upload.wikimedia.org/wikipedia/commons/"+h[0]+"/"+h[:2]+"/"+urllib.parse.quote(name,safe="")
    req=urllib.request.Request(url,headers={"User-Agent":"ForgeStudioResearch/1.0 (public benchmark; github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                raw=r.read(40_000_001)
            if len(raw)>40_000_000:raise ValueError("source too large")
            break
        except Exception:
            if attempt==2:raise
            time.sleep(3*(attempt+1))
    original_sha=hashlib.sha256(raw).hexdigest()
    with Image.open(io.BytesIO(raw)) as img:
        img=ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        img.save(out/"source.png")
    (out/"source.json").write_text(json.dumps(dict(case,source_url=url,description_url="https://commons.wikimedia.org/wiki/File:"+urllib.parse.quote(name),original_sha256=original_sha,processed_sha256=hashlib.sha256((out/"source.png").read_bytes()).hexdigest(),preprocessing="EXIF orientation and aspect-ratio-preserving thumbnail only; no manual mask or crop"),indent=2))
    return out/"source.png"

def render(mesh,src,dest):
    # Actual mesh faces, source input and four fixed directions.
    v=np.asarray(mesh.vertices)[:,[1,2,0]].copy()
    v-=(v.max(0)+v.min(0))/2;v*=2/np.ptp(v,axis=0).max()
    f=np.asarray(mesh.faces);rgb=np.asarray(mesh.visual.vertex_colors)[f,:3].mean(1).astype(np.uint8)
    canvas=Image.new("RGB",(1500,330),(32,38,48));d=ImageDraw.Draw(canvas)
    im=Image.open(src).convert("RGB");im.thumbnail((280,280));canvas.paste(im,((300-im.width)//2,10));d.text((12,310),"SOURCE",fill="white")
    for i,(label,deg) in enumerate([("0 DEG",0),("90 DEG",90),("180 DEG",180),("45 DEG",45)],1):
        a=np.deg2rad(deg);x=v[:,0]*np.cos(a)-v[:,2]*np.sin(a);z=v[:,0]*np.sin(a)+v[:,2]*np.cos(a)
        p=np.stack([i*300+150+x*125,151-v[:,1]*125],1)
        for k in np.argsort(z[f].mean(1)):d.polygon([tuple(p[j]) for j in f[k]],fill=tuple(map(int,rgb[k])))
        d.text((i*300+12,310),label,fill="white")
    canvas.save(dest)

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,choices=[0,1,2],required=True);a=p.parse_args()
    ROOT.mkdir(exist_ok=True);summary={}
    for case in MAN["public_cases"][a.shard::3]:
        out=ROOT/case["id"];out.mkdir(exist_ok=False);row=dict(case,actual_inference=False,visual_accepted=False)
        try:
            src=acquire(case,out)
            env=dict(os.environ,FORGE_IMAGE=str(src.resolve()),FORGE_OUTPUT=str(out.resolve()),FORGE_RESOLUTION="128")
            env.pop("FORGE_RELAX",None)
            proc=subprocess.run([sys.executable,"studio/cloud-ai/cpu_probe.py"],env=env,capture_output=True,text=True,timeout=480)
            (out/"inference.log").write_text(proc.stdout+"\n"+proc.stderr)
            if proc.returncode:raise RuntimeError("real inference failed")
            q=json.loads((out/"report.json").read_text());assert q["real_generation"] and q["input_sha256"]==hashlib.sha256(src.read_bytes()).hexdigest()
            m=trimesh.load(out/"generated.glb",force="mesh",process=False)
            assert len(m.faces)>100 and np.isfinite(m.vertices).all() and np.all(m.extents>0) and m.visual.kind=="vertex"
            row.update(actual_inference=True,faces=len(m.faces),vertices=len(m.vertices),watertight=bool(m.is_watertight),winding=bool(m.is_winding_consistent),components=len(m.split(only_watertight=False)),degenerate_faces=int((m.area_faces<=1e-12).sum()),editor_budget_ok=len(m.faces)<=60000 and len(m.vertices)<=30000 and (out/"generated.glb").stat().st_size<=8000000,seconds=q["seconds"],input_sha256=q["input_sha256"])
            render(m,src,out/"visual.png")
        except Exception as e:row["error"]=repr(e)
        summary[case["id"]]=row;(ROOT/"summary.json").write_text(json.dumps(summary,indent=2));print(json.dumps(row),flush=True)
    if not all(r["actual_inference"] and r["editor_budget_ok"] and not r.get("error") for r in summary.values()):raise SystemExit(1)
if __name__=="__main__":main()
