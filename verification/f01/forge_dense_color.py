"""Camera RGB projection with triangle z-buffer, without changing mesh geometry."""
import numpy as np
from numba import njit
@njit(cache=True)
def depth_buffer(uv,z,faces,h,w):
    buf=np.full((h,w),np.inf)
    for a,b,c in faces:
        if min(z[a],z[b],z[c])<=1e-9:continue
        x0,y0=uv[a];x1,y1=uv[b];x2,y2=uv[c]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-10:continue
        for y in range(max(0,int(np.floor(min(y0,y1,y2)))),min(h-1,int(np.ceil(max(y0,y1,y2))))+1):
            for x in range(max(0,int(np.floor(min(x0,x1,x2)))),min(w-1,int(np.ceil(max(x0,x1,x2))))+1):
                a0=((y1-y2)*(x-x2)+(x2-x1)*(y-y2))/den
                b0=((y2-y0)*(x-x2)+(x0-x2)*(y-y2))/den
                c0=1-a0-b0
                if min(a0,b0,c0)>=-1e-7:
                    zz=1/(a0/z[a]+b0/z[b]+c0/z[c])
                    if zz<buf[y,x]:buf[y,x]=zz
    return buf

def colorize_dense(mesh,views,depth_tolerance=.003):
    v=np.asarray(mesh.vertices);f=np.asarray(mesh.faces,dtype=np.int64);norm=np.asarray(mesh.vertex_normals)
    total=np.zeros_like(v);weights=np.zeros(len(v));counts=np.zeros(len(v),np.int32);extent=np.linalg.norm(mesh.extents)
    for r in views:
        im=np.asarray(r['im']);h,w=im.shape[:2];P=r['P'];C=r['C']
        q=v@P[:,:3].T+P[:,3];z=q[:,2];uv=q[:,:2]/np.where(z>1e-9,z,1)[:,None]
        depth=depth_buffer(uv,z,f,h,w)
        ix=np.rint(uv[:,0]).astype(int);iy=np.rint(uv[:,1]).astype(int)
        inside=(z>0)&(ix>=1)&(ix<w-1)&(iy>=1)&(iy<h-1);ix=np.clip(ix,1,w-2);iy=np.clip(iy,1,h-2)
        near=np.abs(depth[iy,ix]-z)
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            near=np.minimum(near,np.abs(depth[iy+dy,ix+dx]-z))
        d=C-v;d/=np.maximum(np.linalg.norm(d,axis=1,keepdims=True),1e-12);facing=np.clip(np.sum(norm*d,axis=1),0,1)
        valid=inside&(near<=extent*depth_tolerance)&(facing>.12)
        if 'mask' in r:valid &= np.asarray(r['mask'],bool)[iy,ix]
        weight=np.where(valid,facing**4,0.);rgb=im[iy,ix,:3]/255.;linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
        total+=weight[:,None]*linear;weights+=weight;counts+=valid
    colors=np.rint(np.clip(np.where(weights[:,None]>0,total/np.maximum(weights[:,None],1e-12),.35),0,1)*255).astype(np.uint8)
    return colors,{'coverage':float((counts>0).mean()),'two_view_coverage':float((counts>=2).mean()),'camera_count':len(views),'depth_tolerance_ratio':depth_tolerance}
