"""F01: genuine TripoSR outputs, independent of rigs and subject class."""
import hashlib,json,os,pathlib,subprocess,sys
import numpy as np
from PIL import Image,ImageDraw
import trimesh

OUT=pathlib.Path("f01-evidence")
UPSTREAM=pathlib.Path("/tmp/triposr/examples")
ENGINE=pathlib.Path("studio/cloud-ai/cpu_probe.py")
OUT.mkdir(exist_ok=True)

def scene_input(path):
    # New original drawing used ONLY as input to the actual AI engine.
    # A seated person, table, chair, cup; never used as output geometry.
    im=Image.new("RGBA",(512,512),(0,0,0,0));d=ImageDraw.Draw(im)
    d.polygon([(75,190),(143,172),(147,339),(82,360)],fill="#77513d")
    d.polygon([(82,337),(187,311),(225,342),(116,374)],fill="#986b4e")
    d.polygon([(91,354),(105,351),(105,441),(91,448)],fill="#63432f")
    d.polygon([(202,339),(215,344),(215,424),(202,430)],fill="#63432f")
    d.ellipse((124,74,205,169),fill="#d69b70",outline="#69402b",width=3)
    d.pieslice((117,62,207,155),180,360,fill="#392d27")
    d.polygon([(133,157),(198,154),(231,287),(147,321),(107,241)],fill="#276b83")
    d.line([(147,293),(223,313),(259,395)],fill="#354457",width=42,joint="curve")
    d.line([(188,285),(265,292),(298,373)],fill="#48586a",width=36,joint="curve")
    d.ellipse((243,382,302,413),fill="#26282c")
    d.ellipse((279,361,332,393),fill="#272a2d")
    d.line([(180,181),(220,232),(270,181)],fill="#d69b70",width=23,joint="curve")
    d.polygon([(270,168),(286,168),(282,200),(274,200)],fill="#b85c25",outline="#e9d4a9",width=2)
    d.polygon([(262,250),(400,220),(474,265),(331,304)],fill="#a76c3d",outline="#60422d",width=3)
    for x,y in [(276,255),(323,295),(456,263),(390,237)]:
        d.polygon([(x,y),(x+11,y-3),(x+11,y+125),(x,y+131)],fill="#755035")
    d.ellipse((337,255,381,266),fill="#e9e6d7")
    d.polygon([(347,224),(370,224),(366,257),(350,257)],fill="#b85d27",outline="#e2d9b8",width=2)
    im.save(path)

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

scene_input(OUT/"seated_scene.png")
# Pinned upstream examples are not new training data; they are diverse QA
# inputs not covered by the earlier project robot test.
cases=[("chair",UPSTREAM/"chair.png",128),("horse",UPSTREAM/"horse.png",128),
       ("teapot",UPSTREAM/"teapot.png",128),("house",UPSTREAM/"iso_house.png",128),
       ("seated_scene",OUT/"seated_scene.png",128),("robot_regression",UPSTREAM/"robot.png",128),
       ("chair_hd",UPSTREAM/"chair.png",192)]
summary={}
for name,src,res in cases:
    dest=OUT/name;dest.mkdir(exist_ok=True)
    row={"input_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"resolution":res}
    try:
        env=dict(os.environ,FORGE_IMAGE=str(src.resolve()),FORGE_OUTPUT=str(dest.resolve()),FORGE_RESOLUTION=str(res))
        env.pop("FORGE_RELAX",None)
        proc=subprocess.run([sys.executable,str(ENGINE)],env=env,timeout=420,check=False,capture_output=True,text=True)
        (dest/"inference.log").write_text(proc.stdout+"\n"+proc.stderr)
        assert proc.returncode==0,"inference failed"
        report=json.loads((dest/"report.json").read_text())
        assert report["real_generation"] and report["input_sha256"]==row["input_sha256"]
        mesh=trimesh.load(dest/"generated.glb",force="mesh",process=False)
        extent=np.asarray(mesh.extents)
        assert np.isfinite(mesh.vertices).all() and np.all(extent>1e-5)
        assert len(mesh.faces)>100 and mesh.visual.kind=="vertex"
        area=np.asarray(mesh.area_faces)
        row.update(report,extents=extent.tolist(),volume=float(mesh.volume),degenerate_faces=int(np.count_nonzero(area<=1e-12)),editor_budget_ok=len(mesh.vertices)<=30000 and len(mesh.faces)<=60000 and report["bytes"]<=8000000)
        render(mesh,src,dest/"visual.png")
        row["numeric_pass"]=True
    except Exception as exc:
        row["numeric_pass"]=False;row["failure"]=repr(exc)
    summary[name]=row
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
    print(name,json.dumps(row),flush=True)
if not all(x["numeric_pass"] for x in summary.values()):
    raise SystemExit(1)
