"""Real INT8 TripoSR CPU feasibility test. No mock geometry."""
import hashlib, json, pathlib, resource, time, urllib.request, gc
import numpy as np
import onnxruntime as ort
from PIL import Image
from skimage.measure import marching_cubes
import trimesh
ROOT=pathlib.Path("ai-proof-output");ROOT.mkdir(exist_ok=True)
MODELS=ROOT/"models";MODELS.mkdir(exist_ok=True)
BASE="https://huggingface.co/alegauss/modelado-models/resolve/e2a71ca284483bcfd16426ae830cfbd1dfeb16c4/"
FILES={
"triposr-encoder-int8.onnx":(433359857,"8a94284bc2c914323e17774a247e47de0dd5b3a6843d026c68b2765c68a67cbd"),
"triposr-decoder-fp32.onnx":(173374,"1604a0dc1903eee485d5a388dd2b4bcac8fad484a96010a797d7c1f40583d985"),
"triposr-encoder-meta.json":(1654,"3666c04a8454d7d8712e517a04f0927900412e81a7199a22fc280bd7fb34bbad"),
"triposr-decoder-meta.json":(1243,"4a318ad9c4ae0ca3b7b4c35f405c34ae3ac2e683191812de538ceadcb9261158")}
for name,(size,sha) in FILES.items():
 p=MODELS/name
 with urllib.request.urlopen(BASE+name,timeout=120) as r,p.open("wb") as f:
  while b:=r.read(1024*1024):f.write(b)
 with p.open("rb") as f: digest=hashlib.file_digest(f,"sha256").hexdigest()
 assert p.stat().st_size==size and digest==sha,name
# Use a pinned upstream example (downloaded by CI before inference).
photo=Image.open(ROOT/"robot.png").convert("RGBA")
if photo.getextrema()[3][0]<255:
 box=photo.getchannel("A").getbbox()
 assert box is not None
 photo=photo.crop(box)
 side=int(np.ceil(max(photo.size)/.85))
 canvas=Image.new("RGBA",(side,side),(128,128,128,255))
 canvas.alpha_composite(photo,((side-photo.width)//2,(side-photo.height)//2))
 photo=canvas
else:
 canvas=Image.new("RGBA",photo.size,(128,128,128,255));canvas.alpha_composite(photo);photo=canvas
img=photo.convert("RGB").resize((512,512),Image.Resampling.BICUBIC)
img.save(ROOT/"input.png")
x=np.asarray(img,dtype=np.float32).transpose(2,0,1)[None]/255.
def opts():
 s=ort.SessionOptions();s.intra_op_num_threads=2;s.inter_op_num_threads=1;s.enable_cpu_mem_arena=False;s.enable_mem_pattern=False
 return s
start=time.monotonic()
enc=ort.InferenceSession(str(MODELS/"triposr-encoder-int8.onnx"),sess_options=opts(),providers=["CPUExecutionProvider"])
planes=enc.run(None,{enc.get_inputs()[0].name:x})[0]
assert np.isfinite(planes).all()
enc_seconds=time.monotonic()-start
del enc;gc.collect()
dec=ort.InferenceSession(str(MODELS/"triposr-decoder-fp32.onnx"),sess_options=opts(),providers=["CPUExecutionProvider"])
meta=json.loads((MODELS/"triposr-decoder-meta.json").read_text())
radius=float(meta["params"]["radius"]);threshold=float(meta["params"]["density_threshold"])
print("decoder",[(i.name,i.shape) for i in dec.get_inputs()],[(i.name,i.shape) for i in dec.get_outputs()],flush=True)
planes=np.ascontiguousarray(planes.reshape(tuple(int(k) for k in dec.get_inputs()[0].shape)),dtype=np.float32)
names=[i.name for i in dec.get_inputs()];outs=[o.name for o in dec.get_outputs()]
def evaluate(points,output):
 return dec.run([outs[output]],{names[0]:planes,names[1]:np.ascontiguousarray(points,np.float32)})[0]
N=64
axis=np.linspace(-radius,radius,N,dtype=np.float32)
grid=np.stack(np.meshgrid(axis,axis,axis,indexing="ij"),axis=-1).reshape(-1,3)
density=np.concatenate([evaluate(grid[i:i+8192],0).reshape(-1) for i in range(0,len(grid),8192)]).reshape(N,N,N)
assert np.isfinite(density).all() and density.min()<threshold<density.max()
verts,faces,_,_=marching_cubes(density,level=threshold,spacing=(2*radius/(N-1),)*3)
verts-=radius
rgb=np.concatenate([evaluate(verts[i:i+8192],1).reshape(-1,3) for i in range(0,len(verts),8192)])
assert np.isfinite(rgb).all()
mesh=trimesh.Trimesh(vertices=verts[:,[1,2,0]],faces=faces,vertex_colors=np.uint8(np.clip(rgb,0,1)*255),process=False)
mesh.fix_normals()
assert len(mesh.faces)>100 and np.all(mesh.extents>0.05)
mesh.export(ROOT/"robot.glb")
# Actual mesh visualization: orthographic front, side, back. CPU painter preview.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
fig,axs=plt.subplots(1,3,figsize=(10,4),facecolor="#181d24")
for ax,angle,label in zip(axs,[0,np.pi/2,np.pi],["Front","Side","Back"]):
 c,s=np.cos(angle),np.sin(angle)
 q=mesh.vertices@np.array([[c,0,s],[0,1,0],[-s,0,c]])
 tri=q[mesh.faces]
 order=np.argsort(tri[:,:,2].mean(axis=1))
 n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-9)
 light=.35+.65*np.maximum(0,n@np.array([.35,.6,.72]))
 colors=np.clip(rgb[mesh.faces].mean(axis=1)*light[:,None],0,1)
 ax.add_collection(PolyCollection(tri[order,:,:2],facecolors=colors[order],edgecolors="none"))
 ax.autoscale();ax.set_aspect("equal");ax.axis("off");ax.set_title(label,color="white");ax.set_facecolor("#181d24")
fig.savefig(ROOT/"visual.png",dpi=120,bbox_inches="tight");plt.close(fig)
report={"backend":"ONNX Runtime CPU x86_64, 2 threads; not Android","encoder_seconds":enc_seconds,"elapsed_seconds":time.monotonic()-start,"peak_rss_mib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,"vertices":len(mesh.vertices),"triangles":len(mesh.faces),"watertight":bool(mesh.is_watertight),"glb_bytes":(ROOT/"robot.glb").stat().st_size,"grid_resolution":N,"bounds":mesh.bounds.tolist(),"models_verified_sha256":True}
(ROOT/"report.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
