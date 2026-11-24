"""CPU visual hull from calibrated orthographic binary masks; no inferred depth."""
import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates, gaussian_filter
from skimage.measure import marching_cubes
import trimesh

def reconstruct(masks, axes, center, pixel_size, extent, n=96):
    masks=np.asarray(masks);axes=np.asarray(axes,dtype=float);center=np.asarray(center,dtype=float)
    if masks.ndim!=3 or not 3<=len(masks)<=32 or axes.shape!=(len(masks),2,3):raise ValueError('Invalid mask/camera count')
    if type(n)!=int or not 48<=n<=160 or not 64<=min(masks.shape[1:])<=max(masks.shape[1:])<=1024:raise ValueError('Resolution limit')
    if center.shape!=(3,) or not np.isfinite(center).all() or not np.isfinite(axes).all() or not np.isfinite(pixel_size) or pixel_size<=0 or not np.isfinite(extent) or extent<=0:raise ValueError('Invalid calibration')
    if not np.allclose(axes@axes.transpose(0,2,1),np.eye(2),atol=1e-6):raise ValueError('Camera axes not orthonormal')
    normals=np.cross(axes[:,0],axes[:,1]);eig=np.linalg.eigvalsh(normals.T@normals/len(normals))
    if eig[0]<.07:raise ValueError('Insufficient view coverage')
    if not np.all(np.isin(masks,[0,1])):raise ValueError('Masks must be binary')
    masks=masks.astype(bool);h,w=masks.shape[1:];half=extent/2;pitch=extent/(n-1)
    if min(h,w)*pixel_size<extent*1.02:raise ValueError('Camera crop insufficient')
    grid=np.linspace(-half,half,n,dtype=np.float32);field=np.full(n**3,np.inf,dtype=np.float32)
    for mask,cam in zip(masks,axes):
        if not .002<mask.mean()<.8 or mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any():raise ValueError('Empty, excessive or clipped mask')
        d=np.where(mask,distance_transform_edt(mask)-.5,-distance_transform_edt(~mask)+.5).astype(np.float32)*pixel_size
        for start in range(0,len(field),65536):
            ids=np.arange(start,min(start+65536,len(field)));x=grid[ids//(n*n)];y=grid[ids//n%n];z=grid[ids%n]
            u=(cam[0,0]*x+cam[0,1]*y+cam[0,2]*z)/pixel_size+(w-1)/2
            v=(cam[1,0]*x+cam[1,1]*y+cam[1,2]*z)/pixel_size+(h-1)/2
            q=map_coordinates(d,[v,u],order=1,mode='constant',cval=-extent,prefilter=False)
            field[ids]=np.minimum(field[ids],q)
    field=field.reshape((n,n,n))
    if field.max()<=0 or any(np.take(field,k,axis=i).max()>=0 for i in range(3) for k in (0,n-1)):raise ValueError('Empty or clipped volume')
    field=gaussian_filter(np.clip(field,-3*pitch,3*pitch),.42)
    if field.max()<=0:raise ValueError('Empty smoothed volume')
    v,f,_,_=marching_cubes(field,0,spacing=(pitch,)*3,allow_degenerate=False)
    m=trimesh.Trimesh(vertices=v+center-half,faces=f,process=False)
    if m.volume<0:m.invert()
    if not m.is_watertight or not m.is_winding_consistent:raise ValueError('Invalid output topology')
    return m
