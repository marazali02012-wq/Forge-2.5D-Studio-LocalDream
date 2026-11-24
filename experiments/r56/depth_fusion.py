"""Calibrated six-axis depth fusion (metric coordinates, not monocular AI depth)."""
import numpy as np
from scipy.ndimage import gaussian_filter,distance_transform_edt
from skimage.measure import marching_cubes
import trimesh

def reconstruct(depths,origin,pitch,mode='depth'):
    if len(depths)!=3 or not np.isfinite(pitch) or pitch<=0:raise ValueError('Invalid calibration')
    n=depths[0][0].shape[0];origin=np.asarray(origin,float)
    if not 16<=n<=160 or origin.shape!=(3,) or not np.isfinite(origin).all():raise ValueError('Grid limits')
    field=np.full((n,n,n),np.inf,np.float32)
    for axis,(near,far) in enumerate(depths):
        near,far=np.asarray(near,float),np.asarray(far,float)
        if near.shape!=(n,n) or far.shape!=(n,n) or np.isinf(near).any() or np.isinf(far).any():raise ValueError('Invalid maps')
        mask=np.isfinite(near)&np.isfinite(far)
        if not np.array_equal(np.isfinite(near),np.isfinite(far)) or not mask.any() or np.any(near[mask]<far[mask]):raise ValueError('Inconsistent maps')
        if (far[mask].min()<=origin[axis]+pitch*.5 or near[mask].max()>=origin[axis]+pitch*(n-1.5) or mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any()):raise ValueError('Depth or silhouette outside calibrated volume')
        sil=np.where(mask,distance_transform_edt(mask)-.5,-distance_transform_edt(~mask)+.5)*pitch
        field=np.minimum(field,np.expand_dims(sil,axis))
        if mode=='depth':
            shape=[1,1,1];shape[axis]=n;coords=(origin[axis]+pitch*np.arange(n)).reshape(shape)
            a=np.expand_dims(np.where(mask,near,np.inf),axis)-coords+pitch*.35
            b=coords-np.expand_dims(np.where(mask,far,-np.inf),axis)+pitch*.35
            field=np.minimum(field,np.minimum(a,b))
        elif mode!='silhouette':raise ValueError('Unknown mode')
    if not (field>0).any() or any(np.take(field,i,axis=ax).max()>=0 for ax in range(3) for i in (0,n-1)):raise ValueError('Empty or clipped volume')
    field=gaussian_filter(np.clip(field,-3*pitch,3*pitch),.45)
    v,f,_,_=marching_cubes(field,0,spacing=(pitch,)*3,allow_degenerate=False)
    m=trimesh.Trimesh(vertices=v+origin,faces=f,process=False)
    if m.volume<0:m.invert()
    if not m.is_watertight or not m.is_winding_consistent:raise ValueError('Invalid mesh')
    return m

def raster_depth(vertices,faces,origin,pitch,n,axis):
    perm=[i for i in range(3) if i!=axis];v=(np.asarray(vertices)-origin)/pitch
    near=np.full((n,n),-np.inf,np.float32);far=np.full((n,n),np.inf,np.float32)
    for tri in v[faces]:
        p=tri[:,perm];z=tri[:,axis];u=p[1]-p[0];w=p[2]-p[0];det=u[0]*w[1]-u[1]*w[0]
        if abs(det)<1e-9:continue
        lo=np.maximum(0,np.ceil(p.min(0)).astype(int));hi=np.minimum(n-1,np.floor(p.max(0)).astype(int))
        if np.any(hi<lo):continue
        x,y=np.ogrid[lo[0]:hi[0]+1,lo[1]:hi[1]+1];dx=x-p[0,0];dy=y-p[0,1]
        a=(dx*w[1]-dy*w[0])/det;b=(u[0]*dy-u[1]*dx)/det;ok=(a>=-1e-7)&(b>=-1e-7)&(a+b<=1+1e-7)
        zz=(z[0]+a*(z[1]-z[0])+b*(z[2]-z[0]))*pitch+origin[axis];sl=np.s_[lo[0]:hi[0]+1,lo[1]:hi[1]+1]
        np.maximum(near[sl],np.where(ok,zz,-np.inf),out=near[sl]);np.minimum(far[sl],np.where(ok,zz,np.inf),out=far[sl])
    near[~np.isfinite(near)]=np.nan;far[~np.isfinite(far)]=np.nan;return near,far
