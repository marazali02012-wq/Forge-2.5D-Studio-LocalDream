"""CPU calibrated view color projection. Unobserved colors stay neutral."""
import numpy as np
from numba import njit
from PIL import Image
import trimesh

@njit(cache=True)
def raster(v,f,uv,tex,h,w):
    depth=np.full((h,w),-np.inf,np.float32);rgb=np.zeros((h,w,4),np.uint8)
    for a,b,c in f:
        x,y,z=v[a];dx,dy,dz=v[b]-v[a];ex,ey,ez=v[c]-v[a];det=dx*ey-dy*ex
        if abs(det)<1e-10:continue
        for yy in range(max(0,int(np.ceil(min(y,y+dy,y+ey)))),min(h-1,int(np.floor(max(y,y+dy,y+ey))))+1):
            for xx in range(max(0,int(np.ceil(min(x,x+dx,x+ex)))),min(w-1,int(np.floor(max(x,x+dx,x+ex))))+1):
                s=((xx-x)*ey-(yy-y)*ex)/det;t=(dx*(yy-y)-dy*(xx-x))/det
                if s< -1e-7 or t< -1e-7 or s+t>1+1e-7:continue
                zz=z+s*dz+t*ez
                if zz<=depth[yy,xx]:continue
                depth[yy,xx]=zz
                u=uv[a,0]+s*(uv[b,0]-uv[a,0])+t*(uv[c,0]-uv[a,0]);q=uv[a,1]+s*(uv[b,1]-uv[a,1])+t*(uv[c,1]-uv[a,1])
                ix=min(tex.shape[1]-1,max(0,int(u*tex.shape[1])));iy=min(tex.shape[0]-1,max(0,int((1-q)*tex.shape[0])))
                rgb[yy,xx,:3]=tex[iy,ix];rgb[yy,xx,3]=255
    return depth,rgb

def project(v,cam,center,pix,h,w):
    normal=-np.cross(cam[0],cam[1]);p=(v-center)@np.vstack([cam,normal]).T;p[:,:2]/=pix;p[:,0]+=(w-1)/2;p[:,1]+=(h-1)/2;return p

def texture_mesh(mesh,views,cams,center,pix,tile=8):
    views=np.asarray(views);cams=np.asarray(cams,dtype=float);center=np.asarray(center,dtype=float)
    if views.ndim!=4 or views.shape[-1]!=4 or views.dtype!=np.uint8 or not 1<=len(views)<=24 or not 64<=min(views.shape[1:3])<=max(views.shape[1:3])<=1024:raise ValueError('Invalid RGBA views')
    if cams.shape!=(len(views),2,3) or not np.isfinite(cams).all() or not np.allclose(cams@cams.transpose(0,2,1),np.eye(2),atol=1e-6) or center.shape!=(3,) or not np.isfinite(center).all() or not np.isfinite(pix) or pix<=0:raise ValueError('Invalid camera calibration')
    if not np.all((views[...,3]==0)|(views[...,3]==255)):raise ValueError('Binary alpha required')
    v=np.asarray(mesh.vertices);f=np.asarray(mesh.faces);n=len(f)
    if tile!=8 or not 4<=n<=65536 or not np.isfinite(v).all() or f.min()<0 or f.max()>=len(v):raise ValueError('Mesh budget')
    h,w=views.shape[1:3];dummy=np.zeros((1,1,3),np.uint8);depths=[];normals=np.asarray(mesh.face_normals)
    for cam in cams:
        pv=project(v,cam,center,pix,h,w)
        if np.any(pv[:,:2]<1) or np.any(pv[:,0]>=w-1) or np.any(pv[:,1]>=h-1):raise ValueError('Clipped target')
        depths.append(raster(pv,f,np.zeros((len(v),2)),dummy,h,w)[0])
    side=int(np.ceil(np.sqrt(n)));width=tile*side;atlas=np.full((width,width,3),128,np.uint8)
    yy,xx=np.indices((tile,tile));s=(xx.ravel()-1)/5;t=(yy.ravel()-1)/5;core=(s>=0)&(t>=0)&(s+t<=1.000001);s=np.maximum(s,0);t=np.maximum(t,0);d=np.maximum(1,s+t);s/=d;t/=d
    covered=np.zeros(n);total=int(core.sum())
    for start in range(0,n,512):
        stop=min(n,start+512);ids=np.arange(start,stop);tri=v[f[ids]];p=(tri[:,0,None,:]+s[None,:,None]*(tri[:,1]-tri[:,0])[:,None,:]+t[None,:,None]*(tri[:,2]-tri[:,0])[:,None,:]).reshape(-1,3)
        col=np.zeros_like(p);ws=np.zeros(len(p));nn=np.repeat(normals[ids],tile*tile,axis=0)
        for view,cam,dep in zip(views,cams,depths):
            normal=-np.cross(cam[0],cam[1]);weight=nn@normal;proj=project(p,cam,center,pix,h,w);x=np.rint(proj[:,0]).astype(int);y=np.rint(proj[:,1]).astype(int);x=np.clip(x,1,w-2);y=np.clip(y,1,h-2)
            ok=(weight>.12)&(np.abs(dep[y,x]-proj[:,2])<=pix*2.5)&(view[y,x,3]==255)&(view[y-1,x,3]==255)&(view[y+1,x,3]==255)&(view[y,x-1,3]==255)&(view[y,x+1,3]==255)
            q=weight[ok]**4;col[ok]+=q[:,None]*view[y[ok],x[ok],:3];ws[ok]+=q
        valid=ws>0;col[valid]/=ws[valid,None];col[~valid]=128;tiles=np.rint(col).astype(np.uint8).reshape(-1,tile,tile,3);covered[ids]=valid.reshape(-1,tile*tile)[:,core].sum(1)
        for i,patch in zip(ids,tiles):
            x=(i%side)*tile;y=(i//side)*tile;atlas[y:y+tile,x:x+tile]=patch
    idx=np.arange(n);xy=np.column_stack([(idx%side)*tile,(idx//side)*tile]);uv=(xy[:,None,:]+np.array([[1.5,1.5],[6.5,1.5],[1.5,6.5]]))/width;uv[:,:,1]=1-uv[:,:,1]
    vv=v[f].reshape(-1,3);ff=np.arange(n*3).reshape(-1,3);vis=trimesh.visual.texture.TextureVisuals(uv=uv.reshape(-1,2),image=Image.fromarray(atlas));out=trimesh.Trimesh(vertices=vv,faces=ff,visual=vis,process=False);out.vertex_normals=np.asarray(mesh.vertex_normals)[f].reshape(-1,3)
    return out,atlas,{'coverage':float(covered.sum()/(total*n)),'area_weighted_coverage':float(np.average(covered/total,weights=mesh.area_faces)),'unobserved_texels':int(total*n-covered.sum()),'core_texels':total*n,'atlas_size':width,'faces':n,'uv_vertices':len(vv),'unobserved_color':'neutral gray, not AI generated'}
