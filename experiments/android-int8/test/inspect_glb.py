import json, pathlib, sys
import trimesh, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
p=pathlib.Path(sys.argv[1])
m=trimesh.load(p/"java-robot.glb",force="mesh",process=False)
assert len(m.faces)>100 and np.isfinite(m.vertices).all() and np.min(m.extents)>.05
assert np.isfinite(m.vertex_normals).all()
r=json.loads((p/"java-report.json").read_text())
r.update(watertight=bool(m.is_watertight),winding_consistent=bool(m.is_winding_consistent),components=len(m.split(only_watertight=False)),glb_bytes=(p/"java-robot.glb").stat().st_size)
(p/"java-report.json").write_text(json.dumps(r,indent=2));print(json.dumps(r))
fig,axes=plt.subplots(1,3,figsize=(10,4),facecolor="#181d24")
rgb=np.asarray(m.visual.vertex_colors)[:,:3]/255.
for ax,a,label in zip(axes,[0,np.pi/2,np.pi],["Front","Side","Back"]):
 c,s=np.cos(a),np.sin(a);q=m.vertices@np.array([[c,0,s],[0,1,0],[-s,0,c]]);tri=q[m.faces];order=np.argsort(tri[:,:,2].mean(axis=1))
 n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
 light=.35+.65*np.maximum(0,n@np.array([.35,.6,.72]));cols=np.clip(rgb[m.faces].mean(axis=1)*light[:,None],0,1)
 ax.add_collection(PolyCollection(tri[order,:,:2],facecolors=cols[order],edgecolors="none"));ax.autoscale();ax.set_aspect("equal");ax.axis("off");ax.set_title(label,color="white")
fig.savefig(p/"java-visual.png",dpi=120,bbox_inches="tight")
