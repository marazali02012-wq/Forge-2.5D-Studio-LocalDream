"""CPU UV rasterization fallback for TripoSR. Samples the neural field, not source-image colors."""
import numpy as np

def rasterize(vertices, faces, uv, resolution):
    n=int(resolution)
    v=np.asarray(vertices,dtype=np.float32); f=np.asarray(faces,dtype=np.int64).reshape(-1,3); u=np.asarray(uv,dtype=np.float64)
    if n not in (512,1024,2048) or len(f)>250000 or len(v)!=len(u) or not len(f) or not np.isfinite(v).all() or not np.isfinite(u).all() or u.min() < -1e-5 or u.max()>1+1e-5 or f.min()<0 or f.max()>=len(v):
        raise ValueError('CPU UV geometry out of limits')
    pos=np.zeros((n,n,3),np.float32); mask=np.zeros((n,n),bool)
    # Pixel centres, bottom-up UV coordinates, matching upstream FBO orientation.
    for ids in f:
        a,b,c=u[ids]*n-.5; e=b-a; g=c-a; det=e[0]*g[1]-e[1]*g[0]
        if abs(det)<1e-10:continue
        x0=max(0,int(np.ceil(min(a[0],b[0],c[0])))); x1=min(n-1,int(np.floor(max(a[0],b[0],c[0])))); y0=max(0,int(np.ceil(min(a[1],b[1],c[1])))); y1=min(n-1,int(np.floor(max(a[1],b[1],c[1]))))
        if x1<x0 or y1<y0:continue
        x=np.arange(x0,x1+1)[None,:]-a[0]; y=np.arange(y0,y1+1)[:,None]-a[1]
        s=(x*g[1]-y*g[0])/det; t=(e[0]*y-e[1]*x)/det
        inside=(s>=-1e-8)&(t>=-1e-8)&(s+t<=1+1e-8)
        if not inside.any():continue
        p,q,r=v[ids]; block=pos[y0:y1+1,x0:x1+1]; block[inside]=(p+s[inside,None]*(q-p)+t[inside,None]*(r-p)); mask[y0:y1+1,x0:x1+1]|=inside
    if not mask.any():raise ValueError('CPU atlas has no covered texels')
    return pos,mask

def sample_atlas(vertices, faces, uv, resolution, query):
    pos,mask=rasterize(vertices,faces,uv,resolution); ids=np.flatnonzero(mask); rgba=np.zeros((resolution,resolution,4),np.float32); flat=rgba.reshape(-1,4); p=pos.reshape(-1,3)
    for start in range(0,len(ids),4096):
        ix=ids[start:start+4096]; color=np.asarray(query(p[ix]),np.float32)
        if color.shape!=(len(ix),3) or not np.isfinite(color).all():raise ValueError('Invalid neural texture samples')
        flat[ix,:3]=np.clip(color,0,1); flat[ix,3]=1
    return rgba

def bake_cpu(mesh, model, scene_code, resolution):
    import torch
    import xatlas
    if scene_code.ndim!=4 or scene_code.shape[0]!=3:raise ValueError('Expected single triplane')
    atlas=xatlas.Atlas(); atlas.add_mesh(np.asarray(mesh.vertices),np.asarray(mesh.faces)); options=xatlas.PackOptions(); options.resolution=resolution; options.padding=max(2,round(resolution/256)); options.bilinear=True; atlas.generate(pack_options=options)
    vm,faces,uv=atlas[0]
    def query(points):
        with torch.inference_mode():
            p=torch.as_tensor(points,dtype=torch.float32,device=scene_code.device)
            return model.renderer.query_triplane(model.decoder,p,scene_code)['color'].detach().cpu().numpy()
    rgba=sample_atlas(np.asarray(mesh.vertices)[vm],faces,uv,resolution,query)
    return dict(vmapping=vm,indices=faces,uvs=uv,colors=rgba)
