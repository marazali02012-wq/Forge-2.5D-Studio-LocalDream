"""F01 external CC0 real mechanical photo inputs, no prebuilt geometry."""
import hashlib,json,os,pathlib,subprocess,sys,time
import numpy as np
from PIL import Image,ImageOps,ImageDraw
import trimesh

def render(mesh,source,dest):
    v=np.asarray(mesh.vertices)[:,[1,2,0]].copy()
    v-=(v.max(0)+v.min(0))/2
    scale=2/np.ptp(v,axis=0).max();v*=scale
    faces=np.asarray(mesh.faces)
    rgb=np.asarray(mesh.visual.vertex_colors)[faces,:3].mean(1).astype(np.uint8)
    canvas=Image.new("RGB",(1500,330),(32,38,48));d=ImageDraw.Draw(canvas)
    original=Image.open(source).convert("RGBA");original.thumbnail((275,275))
    canvas.paste(original,(int((300-original.width)/2),25),original)
    d.text((12,308),"INPUT",fill="white")
    for i,(label,angle) in enumerate([("FRONT",0),("RIGHT",90),("BACK",180),("THREE QUARTER",45)],1):
        theta=np.deg2rad(angle);c,s=np.cos(theta),np.sin(theta)
        x=v[:,0]*c-v[:,2]*s;z=v[:,0]*s+v[:,2]*c;y=v[:,1]
        p=np.stack([i*300+150+x*117,151-y*117],1)
        for fi in np.argsort(z[faces].mean(1)):
            d.polygon([tuple(p[k]) for k in faces[fi]],fill=tuple(int(x) for x in rgb[fi]))
        d.text((i*300+12,308),label,fill="white")
    canvas.save(dest)

def main():
    root=pathlib.Path("f01-mechanical-evidence");root.mkdir(exist_ok=False)
    cases=[
      ("vise",pathlib.Path("/tmp/forge-vise.png"),"ff16773c83a717dc6e7eb9edbe09c87dbd5f5d2d","https://commons.wikimedia.org/wiki/File:Tornillo_banco.png","MdeVicente"),
      ("gears",pathlib.Path("/tmp/forge-gears.jpg"),"6d46803aa77f2369bb27ed7efb2c5706eabd13b3","https://commons.wikimedia.org/wiki/File:Double-helical_gear.jpg","Parchaco")
    ]
    summary={}
    for name,source,sha,url,author in cases:
        dest=root/name;dest.mkdir()
        row=dict(source=url,author=author,license="CC0-1.0",source_sha1=sha)
        try:
            assert hashlib.sha1(source.read_bytes()).hexdigest()==sha,"source checksum mismatch"
            with Image.open(source) as im:
                im=ImageOps.exif_transpose(im).convert("RGBA");im.thumbnail((768,768));im.save(dest/"source.png")
            src=dest/"source.png";env=dict(os.environ,FORGE_IMAGE=str(src.resolve()),FORGE_OUTPUT=str(dest.resolve()),FORGE_RESOLUTION="128")
            env.pop("FORGE_RELAX",None)
            t=time.monotonic()
            proc=subprocess.run([sys.executable,"studio/cloud-ai/cpu_probe.py"],env=env,timeout=420,capture_output=True,text=True)
            (dest/"inference.log").write_text(proc.stdout+"\n"+proc.stderr);assert proc.returncode==0
            report=json.loads((dest/"report.json").read_text());assert report["real_generation"] and report["input_sha256"]==hashlib.sha256(src.read_bytes()).hexdigest()
            m=trimesh.load(dest/"generated.glb",force="mesh",process=False)
            assert len(m.faces)>100 and np.isfinite(m.vertices).all() and np.all(m.extents>1e-5) and m.visual.kind=="vertex"
            render(m,src,dest/"visual.png")
            row.update(faces=len(m.faces),vertices=len(m.vertices),extents=m.extents.tolist(),watertight=bool(m.is_watertight),editor_budget_ok=len(m.vertices)<=30000 and len(m.faces)<=60000,seconds=time.monotonic()-t,numeric_pass=True)
        except Exception as exc:row.update(numeric_pass=False,error=repr(exc))
        summary[name]=row;(root/"summary.json").write_text(json.dumps(summary,indent=2));print(name,row,flush=True)
    if not all(row["numeric_pass"] and row["editor_budget_ok"] for row in summary.values()):raise SystemExit(1)
if __name__=="__main__":main()
