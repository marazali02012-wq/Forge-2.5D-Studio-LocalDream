"""Compare two conservative rear-surface edits on the real healer mesh."""
from pathlib import Path
import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from PIL import Image,ImageDraw
m=trimesh.load('results/healer/generated.glb',force='mesh',process=False)
v=m.vertices[:,[1,2,0]].copy();v-=(v.max(0)+v.min(0))/2
n=m.vertex_normals[:,[1,2,0]]
rgb=m.visual.vertex_colors[:,:3].astype(float)
edges=m.edges_unique
a,b=edges.T
w=np.maximum(np.einsum('ij,ij->i',n[a],n[b]),0)**2
weights=coo_matrix((np.r_[w,w],(np.r_[a,b],np.r_[b,a])),shape=(len(v),len(v))).tocsr()
div=np.asarray(weights.sum(1)).clip(1e-9)
smoothed=rgb.copy()
for _ in range(20):smoothed=.5*smoothed+.5*(weights@smoothed)/div
z=v[:,2];yr=v[:,1]
rear=np.clip(-n[:,2]*2,0,1)*np.clip(-z/(np.ptp(z)*.12),0,1)
edited=rgb+(smoothed-rgb)*rear[:,None]
expanded=v.copy();expanded[:,2]*=1.15
sheet=Image.new('RGB',(720,460),'#172433');draw=ImageDraw.Draw(sheet)
for i,(angle,label) in enumerate([(180,'Arka'),(90,'Yan')]):
 for k,(verts,colors,name) in enumerate([(v,rgb,'Kaynak'),(v,edited,'Yerel renk yumusatma'),(expanded,rgb,'+%15 derinlik')]):
  a=np.deg2rad(angle);x=verts[:,0]*np.cos(a)-verts[:,2]*np.sin(a);z=verts[:,0]*np.sin(a)+verts[:,2]*np.cos(a)
  pts=np.stack([x*95+k*240+120,230*i+110-verts[:,1]*95],axis=1);faces=m.faces;order=np.argsort(z[faces].mean(1));facec=colors[faces].mean(1)
  for f in order:draw.polygon([tuple(p) for p in pts[faces[f]]],fill=tuple(facec[f].astype(int)))
  draw.text((k*240+15,230*i+210),label+' / '+name,fill='white')
sheet.save('evidence34/healer_quality_probe.jpg',quality=90)
