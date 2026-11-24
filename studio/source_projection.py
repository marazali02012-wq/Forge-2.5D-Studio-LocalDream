"""Optional conservative front-reference texture projection. No new geometry or unseen-view claim."""
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from cpu_bake import rasterize
from color_qa import front_samples
from quality import source_mask, compare


def project_front(mesh,source):
    """Return diagnostics, modifying only visible covered front-facing atlas texels on improvement."""
    report={'applied':False,'method':'visible_front_reference_blend','unseen_surfaces_verified':False}
    tex=mesh.visual.material.baseColorTexture
    original=np.array(tex.convert('RGBA'))
    n=original.shape[0]
    if original.shape!=(n,n,4) or n not in (512,1024) or len(mesh.faces)>100000:
        return dict(report,reason='atlas_or_mesh_limit')
    v=np.asarray(mesh.vertices,dtype=np.float64); f=np.asarray(mesh.faces); uv=np.asarray(mesh.visual.uv)
    qa=compare(source_mask(source),v,f)
    report['silhouette']=qa['iou']
    if qa['warning'] or qa['iou']<.90:return dict(report,reason='front_alignment_insufficient')
    # Shared normalization matches front_samples and quality.compare.
    p=v[:,:2].copy();p[:,1]*=-1;lo=p.min(0);hi=p.max(0);scale=(n-12)/max(hi-lo)
    p=(p-(lo+hi)/2)*scale+n/2
    zbuf=np.full((n,n),-np.inf)
    for ids in f:
        a,b,c=p[ids];x0,y0=np.maximum(0,np.floor(np.min([a,b,c],axis=0)).astype(int));x1,y1=np.minimum(n-1,np.ceil(np.max([a,b,c],axis=0)).astype(int))
        if x1<x0 or y1<y0:continue
        X,Y=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(det)<1e-8:continue
        A=((b[1]-c[1])*(X-c[0])+(c[0]-b[0])*(Y-c[1]))/det;B=((c[1]-a[1])*(X-c[0])+(a[0]-c[0])*(Y-c[1]))/det;C=1-A-B
        z=A*v[ids[0],2]+B*v[ids[1],2]+C*v[ids[2],2]
        block=zbuf[y0:y1+1,x0:x1+1];hit=(A>=-1e-7)&(B>=-1e-7)&(C>=-1e-7)
        np.maximum(block,np.where(hit,z,-np.inf),out=block)
    src=np.asarray(source.convert('RGBA'));ys,xs=np.where(src[:,:,3]>=96)
    if not len(xs):return dict(report,reason='empty_source')
    crop=Image.fromarray(src[ys.min():ys.max()+1,xs.min():xs.max()+1]);w,h=crop.size;r=(n-12)/max(w,h);w,h=max(1,round(w*r)),max(1,round(h*r))
    fit=Image.new('RGBA',(n,n));fit.paste(crop.resize((w,h),Image.Resampling.BILINEAR),((n-w)//2,(n-h)//2));ref=np.asarray(fit)
    # UV rasterizer uses bottom-up UV rows; GLB image rows are top-down.
    pos,covered=rasterize(v,f,uv,n);norm,ncovered=rasterize(np.asarray(mesh.vertex_normals),f,uv,n)
    pos=pos[::-1];norm=norm[::-1];covered=covered[::-1]&ncovered[::-1]
    norm=norm/np.maximum(np.linalg.norm(norm,axis=2,keepdims=True),1e-8)
    u=pos[:,:,:2].copy();u[:,:,1]*=-1;u=(u-(lo+hi)/2)*scale+n/2
    x=np.clip(np.floor(u[:,:,0]).astype(int),0,n-1);y=np.clip(np.floor(u[:,:,1]).astype(int),0,n-1)
    delta=zbuf[y,x]-pos[:,:,2]
    valid=covered&(original[:,:,3]==255)&np.isfinite(delta)&(np.abs(delta)<=2.5/scale)&(norm[:,:,2]>.50)&(ref[y,x,3]>=250)
    dist=distance_transform_edt(ref[:,:,3]>=250)[y,x]
    weight=np.where(valid,np.clip((norm[:,:,2]-.50)/.40,0,1)*np.clip((dist-3)/8,0,1)*.85,0.)
    touched=weight>0
    report['changed_texels']=int(touched.sum());report['atlas_coverage']=round(float(touched.mean()),5)
    if touched.sum()<250:return dict(report,reason='insufficient_visible_texels')
    before,reference,check,_=front_samples(mesh,source)
    if check.sum()<300:return dict(report,reason='insufficient_front_samples')
    candidate=original.copy();candidate[:,:,:3]=np.rint(original[:,:,:3]*(1-weight[:,:,None])+ref[y,x,:3]*weight[:,:,None]).astype(np.uint8)
    mesh.visual.material.baseColorTexture=Image.fromarray(candidate)
    try:
        after,_,check2,_=front_samples(mesh,source);common=check&check2
        if common.sum()<300:raise ValueError('insufficient validation samples')
        old=float(np.abs(before[common]-reference[common]).mean());new=float(np.abs(after[common]-reference[common]).mean())
        report.update(mae_before=round(old,3),mae_after=round(new,3),samples=int(common.sum()),unchanged_outside_mask=bool(np.array_equal(candidate[~touched],original[~touched])))
        if new>old*.95 or not report['unchanged_outside_mask']:
            mesh.visual.material.baseColorTexture=tex;return dict(report,reason='no_measured_improvement')
    except Exception:
        mesh.visual.material.baseColorTexture=tex;raise
    report['applied']=True
    return report
