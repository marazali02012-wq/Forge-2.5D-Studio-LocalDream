"""Pair adjacent faces; re-pack existing UV texture without changing geometry."""
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import trimesh

def repack(target,old,tile=12):
 v=np.asarray(target.vertices);f=np.asarray(target.faces);n=len(f)
 if not 4<=n<=65536 or tile not in (10,12,14) or not np.isfinite(v).all() or np.any(target.area_faces<=0):raise ValueError('Mesh budget or degenerate face')
 if not np.allclose(old.vertices[old.faces],v[f],atol=1e-6):raise ValueError('Source geometry mismatch')
 mat=old.visual.material;im=np.array((getattr(mat,'baseColorTexture',None) or getattr(mat,'image',None)).convert('RGB'));uv=np.asarray(old.visual.uv)[old.faces]
 if not np.isfinite(uv).all() or np.any(uv<0) or np.any(uv>1):raise ValueError('Invalid UV')
 adj=target.face_adjacency;norm=target.face_normals;dots=np.einsum('ij,ij->i',norm[adj[:,0]],norm[adj[:,1]])
 used=np.zeros(n,bool);charts=[]
 yy,xx=np.indices((tile,tile));xy=np.column_stack((xx.ravel(),yy.ravel()))
 def normalize(c):
  c=c-c.min(0);span=c.max(0);return c*(tile-3)/span.max()+1+(tile-3)*(1-span/span.max())/2
 def inside_count(c):
  a,b,k=c;st=(xy-a)@np.linalg.inv(np.column_stack((b-a,k-a))).T;return int(((st[:,0]>1e-8)&(st[:,1]>1e-8)&(st.sum(1)<1-1e-8)).sum())
 for j in np.argsort(-dots,kind='stable'):
  a,b=adj[j]
  if used[a] or used[b] or dots[j]<.35:continue
  common=np.intersect1d(f[a],f[b]);
  if len(common)!=2:continue
  u,w=common;others=[next(x for x in f[k] if x not in common) for k in (a,b)]
  if others[0]==others[1]:continue
  edge=v[w]-v[u];l=np.linalg.norm(edge);axis=edge/l;d=v[others]-v[u];x=d@axis;h=np.linalg.norm(d-x[:,None]*axis,axis=1)
  if min(h)<l*.06:continue
  coords=np.array([[0,0],[l,0],[x[0],h[0]],[x[1],-h[1]]]);q=normalize(coords)
  if min(inside_count(q[[0,1,2]]),inside_count(q[[0,1,3]]))<3:continue
  charts.append(([a,b],np.array([u,w,*others]),coords));used[[a,b]]=True
 for a in np.flatnonzero(~used):
  ids=f[a];charts.append(([a],ids,np.array([[0.,0.],[1.,0.],[0.,1.]])))
 side=int(np.ceil(np.sqrt(len(charts))));width=side*tile;atlas=np.full((width,width,3),128,np.uint8);outv=[];outuv=[];outn=[];outf=np.empty_like(f);yy,xx=np.indices((tile,tile));xy=np.column_stack((xx.ravel(),yy.ravel()));unsampled=0
 for i,(fs,ids,c) in enumerate(charts):
  c=c-c.min(0);span=c.max(0);c=c*(tile-3)/span.max()+1+(tile-3)*(1-span/span.max())/2
  offset=len(outv);outv.extend(v[ids]);outn.extend(target.vertex_normals[ids]);lookup={x:j for j,x in enumerate(ids)};local=np.array([[lookup[x] for x in f[k]] for k in fs]);outf[fs]=local+offset
  corner=np.array([(i%side)*tile,(i//side)*tile]);q=(c+corner+.5)/width;q[:,1]=1-q[:,1];outuv.extend(q)
  patch=np.zeros((tile*tile,3),np.uint8);mask=np.zeros(tile*tile,bool)
  for face,idx in zip(fs,local):
   a,b,k=c[idx];st=(xy-a)@np.linalg.inv(np.column_stack((b-a,k-a))).T;inside=(st[:,0]>=-1e-8)&(st[:,1]>=-1e-8)&(st.sum(1)<=1+1e-8)&(~mask)
   if not inside.any():unsampled+=1;continue
   u=uv[face,0]+st[inside,0,None]*(uv[face,1]-uv[face,0])+st[inside,1,None]*(uv[face,2]-uv[face,0]);px=np.clip((u[:,0]*im.shape[1]).astype(int),0,im.shape[1]-1);py=np.clip(((1-u[:,1])*im.shape[0]).astype(int),0,im.shape[0]-1);patch[inside]=im[py,px];mask|=inside
  if mask.any():
   near=distance_transform_edt(~mask.reshape(tile,tile),return_distances=False,return_indices=True);patch=patch[(near[0]*tile+near[1]).ravel()]
  else:
   u=uv[fs[0]].mean(0);patch[:]=im[min(im.shape[0]-1,int((1-u[1])*im.shape[0])),min(im.shape[1]-1,int(u[0]*im.shape[1]))]
  x,y=corner;atlas[y:y+tile,x:x+tile]=patch.reshape(tile,tile,3)
 out=trimesh.Trimesh(vertices=np.array(outv),faces=outf,visual=trimesh.visual.texture.TextureVisuals(uv=np.array(outuv),image=Image.fromarray(atlas)),process=False);out.vertex_normals=np.array(outn)
 return out,dict(charts=len(charts),paired=n-len(charts),faces=n,vertices=len(out.vertices),atlas=width,unsampled_faces=unsampled)
