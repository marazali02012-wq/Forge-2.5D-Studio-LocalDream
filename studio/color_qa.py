"""Conservative global albedo calibration; no invented texture detail or geometry.
Source/modeled front comparison uses visible texels and spatial hold-out samples.
Does not certify rear surfaces or correct view-dependent source lighting.
"""
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion

def front_samples(mesh, source, n=192):
    v=np.asarray(mesh.vertices,dtype=float); uv=np.asarray(mesh.visual.uv,dtype=float)
    f=np.asarray(mesh.faces,dtype=int)
    p=v[:,:2].copy(); p[:,1]*=-1
    lo=p.min(0);hi=p.max(0);p=(p-(lo+hi)/2)*((n-12)/max(hi-lo))+n/2
    z=np.full((n,n),-np.inf);u=np.zeros((n,n,2)); facing=np.zeros((n,n))
    normals=np.asarray(mesh.face_normals)
    for ids,normal in zip(f,normals):
        a,b,c=p[ids]; x0,y0=np.maximum(0,np.floor(np.min([a,b,c],axis=0)).astype(int));x1,y1=np.minimum(n-1,np.ceil(np.max([a,b,c],axis=0)).astype(int))
        if x1<x0 or y1<y0:continue
        X,Y=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(det)<1e-8:continue
        A=((b[1]-c[1])*(X-c[0])+(c[0]-b[0])*(Y-c[1]))/det
        B=((c[1]-a[1])*(X-c[0])+(a[0]-c[0])*(Y-c[1]))/det;C=1-A-B
        zs=A*v[ids[0],2]+B*v[ids[1],2]+C*v[ids[2],2]
        sl=np.s_[y0:y1+1,x0:x1+1];hit=(A>=-1e-7)&(B>=-1e-7)&(C>=-1e-7)&(zs>z[sl]);z[sl][hit]=zs[hit]
        u[sl][hit]=(A[...,None]*uv[ids[0]]+B[...,None]*uv[ids[1]]+C[...,None]*uv[ids[2]])[hit];facing[sl][hit]=normal[2]
    src=source.convert('RGBA'); a=np.asarray(src);ys,xs=np.where(a[:,:,3]>=96)
    if not len(xs):raise ValueError('Empty source')
    src=src.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1));w,h=src.size;ratio=(n-12)/max(w,h);w,h=max(1,round(w*ratio)),max(1,round(h*ratio))
    fit=Image.new('RGBA',(n,n));fit.paste(src.resize((w,h),Image.Resampling.BILINEAR),((n-w)//2,(n-h)//2));ref=np.asarray(fit)
    tex=np.asarray(mesh.visual.material.baseColorTexture.convert('RGBA'));H,W=tex.shape[:2];x=np.clip(np.rint(u[:,:,0]*(W-1)).astype(int),0,W-1);y=np.clip(np.rint((1-u[:,:,1])*(H-1)).astype(int),0,H-1);col=tex[y,x]
    valid=binary_erosion(np.isfinite(z)&(ref[:,:,3]>235)&(col[:,:,3]>235),iterations=2)&(facing>.35)
    # Spatial block split prevents adjacent individual texels from dominating both sets.
    yy,xx=np.indices((n,n));hold=((yy//12+xx//12)%3)==0
    return col[:,:,:3].astype(np.float32),ref[:,:,:3].astype(np.float32),valid,hold

def calibrate(mesh,source):
    c,r,valid,hold=front_samples(mesh,source);train=valid&~hold;test=valid&hold
    report={'applied':False,'method':'bounded_global_color_gain','train_pixels':int(train.sum()),'holdout_pixels':int(test.sum())}
    if train.sum()<250 or test.sum()<150:return report
    # A single bounded gain avoids reprojecting mismatched facial features/edges.
    def error(mask,g):return float(np.mean(np.abs(np.clip(c[mask]*g,0,255)-r[mask])))
    gains=np.arange(.85,1.201,.025);g=float(min(gains,key=lambda x:error(train,x)));before=error(test,1.);after=error(test,g)
    report.update(gain=round(g,3),mae_before=round(before,3),mae_after=round(after,3))
    if abs(g-1)<.024 or after>before*.97:return report
    # Reject corrections that materially worsen any channel or blow highlights.
    old=np.mean(np.abs(c[test]-r[test]),axis=0);new=np.mean(np.abs(np.clip(c[test]*g,0,255)-r[test]),axis=0)
    clip_before=float((c[test]>=252).mean());clip_after=float((c[test]*g>=252).mean())
    if np.any(new>old+2) or clip_after-clip_before>.035:return report
    tex=np.array(mesh.visual.material.baseColorTexture.convert('RGBA'));tex[:,:,:3]=np.rint(np.clip(tex[:,:,:3].astype(float)*g,0,255)).astype(np.uint8)
    mesh.visual.material.baseColorTexture=Image.fromarray(tex);report['applied']=True
    return report
