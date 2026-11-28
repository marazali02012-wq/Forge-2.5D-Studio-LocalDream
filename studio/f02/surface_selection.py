"""F02 immutable triangle-label sidecar and surface-connected brush.
No geometry changes; unknown label=0. This is a selection foundation, not AI.
"""
import hashlib,heapq,json
import numpy as np
import trimesh
from numba import njit

def mesh_id(m):
    h=hashlib.sha256()
    h.update(np.asarray(m.vertices,dtype="<f8").tobytes())
    h.update(np.asarray(m.faces,dtype="<i8").tobytes())
    return h.hexdigest()

@njit(cache=True)
def raster(uv,z,faces,size):
    ids=np.full((size,size),-1,np.int32);depth=np.full((size,size),np.inf)
    for i in range(len(faces)):
        a,b,c=faces[i];x0,y0=uv[a];x1,y1=uv[b];x2,y2=uv[c]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-10:continue
        for y in range(max(0,int(np.floor(min(y0,y1,y2)))),min(size-1,int(np.ceil(max(y0,y1,y2))))+1):
            for x in range(max(0,int(np.floor(min(x0,x1,x2)))),min(size-1,int(np.ceil(max(x0,x1,x2))))+1):
                u=((y1-y2)*(x-x2)+(x2-x1)*(y-y2))/den
                v=((y2-y0)*(x-x2)+(x0-x2)*(y-y2))/den
                w=1-u-v
                if min(u,v,w)>=-1e-8:
                    d=u*z[a]+v*z[b]+w*z[c]
                    if d<depth[y,x]:depth[y,x]=d;ids[y,x]=i
    return ids

def render_ids(m,angle,size=512,elevation=12):
    v=np.asarray(m.vertices).copy();v-=(v.min(0)+v.max(0))/2
    v/=max(float(np.ptp(v,axis=0).max()),1e-9)
    a,e=np.deg2rad([angle,elevation]);c,s=np.cos(a),np.sin(a)
    x=v[:,0]*c-v[:,2]*s;z=v[:,0]*s+v[:,2]*c
    y=v[:,1]*np.cos(e)-z*np.sin(e);d=z*np.cos(e)+v[:,1]*np.sin(e)
    uv=np.stack([size/2+x*size*.82,size/2-y*size*.82],1)
    return raster(uv,-d,np.asarray(m.faces,np.int64),size)

def mask_votes(ids,mask,n):
    if ids.shape!=mask.shape or np.any(ids>=n) or np.any(ids< -1):raise ValueError("invalid mask/ID dimensions")
    valid=ids>=0
    return np.bincount(ids[valid&mask.astype(bool)],minlength=n),np.bincount(ids[valid],minlength=n)

class Selection:
    def __init__(self,m):
        self.id=mesh_id(m);self.labels=np.zeros(len(m.faces),np.int32)
        self.centers=np.asarray(m.triangles_center);self.extent=float(np.linalg.norm(m.extents))
        if not np.isfinite(self.centers).all() or self.extent<=0:raise ValueError("invalid mesh")
        self.neighbors=[[] for _ in self.labels];self.history=[]
        for a,b in m.face_adjacency:
            d=float(np.linalg.norm(self.centers[a]-self.centers[b]))
            self.neighbors[a].append((int(b),d));self.neighbors[b].append((int(a),d))
    def brush(self,seed,radius,label):
        if not 0<=seed<len(self.labels) or not 0<radius<=.25 or not 0<=label<=65535:raise ValueError("invalid brush")
        dist={int(seed):0.};q=[(0.,int(seed))];limit=radius*self.extent
        while q:
            d,i=heapq.heappop(q)
            if d!=dist[i]:continue
            for j,w in self.neighbors[i]:
                nd=d+w
                if nd<=limit and nd<dist.get(j,float("inf")):dist[j]=nd;heapq.heappush(q,(nd,j))
        idx=np.array(sorted(dist),np.int64);self.history.append((idx,self.labels[idx].copy()));self.labels[idx]=label
        return idx
    def apply_mask(self,ids,mask,label,threshold=.6):
        if not 1<=label<=65535 or not .5<=threshold<=1:raise ValueError("invalid label")
        hit,seen=mask_votes(ids,mask,len(self.labels))
        idx=np.flatnonzero((seen>0)&(hit>=threshold*seen))
        self.history.append((idx,self.labels[idx].copy()));self.labels[idx]=label
        return idx
    def undo(self):
        if not self.history:return False
        idx,old=self.history.pop();self.labels[idx]=old;return True
    def save(self,path,names):
        path.write_text(json.dumps({"schema":"forge-f02-face-labels-v1","mesh_id":self.id,"face_count":len(self.labels),"labels":self.labels.tolist(),"names":names}))
    def load(self,path):
        data=json.loads(path.read_text());labels=np.asarray(data["labels"])
        if data["schema"]!="forge-f02-face-labels-v1" or data["mesh_id"]!=self.id or data["face_count"]!=len(self.labels) or labels.shape!=self.labels.shape or labels.dtype.kind not in "iu" or np.any(labels<0) or np.any(labels>65535):raise ValueError("sidecar does not match original mesh")
        self.labels[:]=labels;self.history.clear()
