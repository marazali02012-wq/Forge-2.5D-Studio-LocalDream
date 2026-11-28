"""F01 calibrated perspective visual hull: real photographs + camera matrices.
No templates or neural novel-view hallucination. Occluded concavities are not recoverable.
"""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt,map_coordinates,gaussian_filter,binary_fill_holes
from skimage.measure import marching_cubes,label
from PIL import Image,ImageDraw
import trimesh

def read_middlebury(root,diagnostics):
    diagnostics.mkdir(parents=True,exist_ok=True)
    file=next(root.rglob("*_par.txt"))
    rows=file.read_text().splitlines();data=[]
    for row in rows:
        q=row.split()
        if len(q)!=22:continue
        name=q[0];x=np.array(q[1:],float)
        K=x[:9].reshape(3,3);R=x[9:18].reshape(3,3);t=x[18:]
        if not np.isfinite(x).all() or not np.allclose(R@R.T,np.eye(3),atol=.003):raise ValueError("invalid camera")
        P=K@np.column_stack([R,t]);im=np.asarray(Image.open(file.parent/name).convert("RGB"))
        # Estimate actual studio background from perimeter pixels; do not
        # use a fixed black threshold. Keep the largest non-border component
        # only if it represents the dominant foreground, otherwise reject.
        rgb=im.astype(np.float32)
        border=np.concatenate([rgb[:4].reshape(-1,3),rgb[-4:].reshape(-1,3),rgb[:,:4].reshape(-1,3),rgb[:,-4:].reshape(-1,3)])
        bg=np.median(border,axis=0)
        delta=np.linalg.norm(rgb-bg,axis=2)
        border_delta=np.linalg.norm(border-bg,axis=1)
        # Actual diagnostic dinoSR0001 shows a dim brown support strip
        # joining the border to the object below RGB distance 40.
        # Prefer the lowest threshold that separates a dominant component.
        base=max(40.,float(np.quantile(border_delta,.90))+8.)
        mask=np.zeros(delta.shape,bool);best=0;counts=np.array([0]);edges=set()
        threshold=base
        for threshold in (base,base+10,base+20,base+30):
            fg=delta>threshold
            cc=label(fg);counts=np.bincount(cc.ravel());counts[0]=0
            edges=set(np.unique(np.concatenate([cc[0],cc[-1],cc[:,0],cc[:,-1]])).tolist())
            valid=[k for k in range(1,len(counts)) if k not in edges]
            best=max(valid,key=lambda k:counts[k],default=0)
            mask=(cc==best) if best else np.zeros(cc.shape,bool)
            if .002<mask.mean()<.8 and counts[best]>=.85*counts.max():break
        # Preserve silhouette holes and record all rejected border material.
        preview=Image.new("RGB",(im.shape[1]*2,im.shape[0]))
        preview.paste(Image.fromarray(im),(0,0))
        overlay=im.copy();overlay[~mask]=(overlay[~mask].astype(np.float32)*.35).astype(np.uint8)
        preview.paste(Image.fromarray(overlay),(im.shape[1],0))
        preview.save(diagnostics/(Path(name).stem+".jpg"))
        print(json.dumps(dict(view=name,background=bg.tolist(),threshold=threshold,area=float(mask.mean()),largest=int(counts.max()),selected=int(counts[best]),excluded_border_pixels=int(sum(counts[k] for k in edges if k>0)))),flush=True)
        if not .002<mask.mean()<.8 or counts[best]<.85*counts.max():raise ValueError("bad/clipped foreground "+name)
        ys,xs=np.where(mask);uv=np.array([xs.mean(),ys.mean(),1.])
        C=-R.T@t;ray=R.T@np.linalg.solve(K,uv);ray/=np.linalg.norm(ray)
        data.append(dict(name=name,P=P,C=C,ray=ray,mask=mask,im=im,hash=hashlib.sha256((file.parent/name).read_bytes()).hexdigest()))
    if not 6<=len(data)<=64:raise ValueError("invalid number of cameras")
    return data

def project(P,v):
    q=v@P[:,:3].T+P[:,3];z=q[:,2]
    safe=np.where(z>1e-9,z,1.)
    return q[:,0]/safe,q[:,1]/safe,z

def reconstruct(data,n=96):
    # Least squares intersection of mask centroid rays estimates scene center;
    # conservative extent from actual camera distances and mask angular sizes.
    A=np.zeros((3,3));b=np.zeros(3)
    for r in data:
        a=np.eye(3)-np.outer(r["ray"],r["ray"]);A+=a;b+=a@r["C"]
    if np.linalg.cond(A)>100:raise ValueError("camera coverage insufficient")
    center=np.linalg.solve(A,b)
    sizes=[]
    for r in data:
        y,x=np.where(r["mask"]);f=np.linalg.norm(r["P"][0,:3]-r["P"][2,:3]*((r["mask"].shape[1]-1)/2))
        sizes.append(max(np.ptp(x),np.ptp(y))*np.linalg.norm(center-r["C"])/max(f,1.))
    extent=max(sizes)*1.8
    if not np.isfinite(extent) or extent<=0:raise ValueError("invalid extent")
    for retry in range(3):
        axis=np.linspace(-extent/2,extent/2,n);field=np.full(n**3,np.inf,dtype=np.float32)
        for r in data:
            mask=r["mask"];d=(distance_transform_edt(mask)-distance_transform_edt(~mask)).astype(np.float32)
            for start in range(0,len(field),65536):
                i=np.arange(start,min(start+65536,len(field)));v=np.column_stack([axis[i//(n*n)],axis[i//n%n],axis[i%n]])+center
                u,w,z=project(r["P"],v)
                q=map_coordinates(d,[w,u],order=1,mode="constant",cval=-1e3,prefilter=False)
                field[i]=np.minimum(field[i],np.where(z>0,q,-1e3))
        field=field.reshape((n,)*3)
        if field.max()<=0:raise ValueError("empty intersection")
        if any(np.take(field,k,axis=i).max()>=0 for i in range(3) for k in (0,n-1)):
            extent*=1.5;continue
        pitch=extent/(n-1);field=gaussian_filter(np.clip(field,-8,8),.42)
        v,f,_,_=marching_cubes(field,0,spacing=(pitch,)*3,allow_degenerate=False)
        m=trimesh.Trimesh(v+center-extent/2,f,process=False)
        if m.volume<0:m.invert()
        if not m.is_watertight or not m.is_winding_consistent:raise ValueError("invalid topology")
        return m
    raise ValueError("clipped reconstruction")

def colorize(m,data):
    v=np.asarray(m.vertices);norm=np.asarray(m.vertex_normals);total=np.zeros_like(v);weight=np.zeros(len(v))
    for r in data:
        u,w,z=project(r["P"],v);h,k=r["mask"].shape;ix=np.rint(u).astype(int);iy=np.rint(w).astype(int)
        valid=(z>0)&(ix>=0)&(ix<k)&(iy>=0)&(iy<h)
        ix=np.clip(ix,0,k-1);iy=np.clip(iy,0,h-1)
        direction=r["C"]-v;direction/=np.maximum(np.linalg.norm(direction,axis=1,keepdims=True),1e-12)
        facing=np.clip((norm*direction).sum(1),0,1)
        # Sparse vertex depth visibility; no hidden-surface color claims.
        depth=np.full(h*k,np.inf);np.minimum.at(depth,(iy*k+ix)[valid],z[valid])
        visible=z<=depth[iy*k+ix]+np.linalg.norm(m.extents)*.015
        a=np.where(valid&visible&r["mask"][iy,ix],facing**4,0.)
        rgb=r["im"][iy,ix]/255.
        linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
        total+=a[:,None]*linear;weight+=a
    rgb=np.where(weight[:,None]>0,total/np.maximum(weight[:,None],1e-12),.35)
    m.visual.vertex_colors=np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
    return float((weight>0).mean())

def silhouette(m,r):
    u,w,z=project(r["P"],np.asarray(m.vertices));h,k=r["mask"].shape
    im=Image.new("1",(k,h));d=ImageDraw.Draw(im)
    for f in m.faces:
        if np.all(z[f]>0):d.polygon(list(zip(u[f],w[f])),fill=1)
    return np.asarray(im,dtype=bool)

def main():
    p=argparse.ArgumentParser();p.add_argument("dataset",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);data=read_middlebury(a.dataset,a.output/'masks')
    test=data[::4];train=[r for i,r in enumerate(data) if i%4!=0]
    t=time.monotonic();m=reconstruct(train);coverage=colorize(m,train)
    iou=[];h,w=test[0]["mask"].shape;sheet=Image.new("RGB",(w*2,h*len(test)),(30,35,45))
    for i,r in enumerate(test):
        pred=silhouette(m,r);truth=r["mask"];iou.append(float((pred&truth).sum()/max(1,(pred|truth).sum())))
        im=r["im"].copy();im[truth&~pred]=[240,50,50];im[pred&~truth]=[20,190,240]
        sheet.paste(Image.fromarray(r["im"]),(0,h*i));sheet.paste(Image.fromarray(im),(w,h*i))
    sheet.save(a.output/"heldout-views.jpg")
    # Four independent camera-angle mesh previews, no use of input pixels as geometry.
    v=np.asarray(m.vertices).copy();v-=(v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max()
    f=np.asarray(m.faces);rgb=np.asarray(m.visual.vertex_colors)[f,:3].mean(1)/255.
    rgb=np.rint(np.where(rgb<=.0031308,12.92*rgb,1.055*np.maximum(rgb,0)**(1/2.4)-.055)*255).astype(np.uint8)
    sheet=Image.new("RGB",(1200,320),(32,38,48));d=ImageDraw.Draw(sheet)
    for i,angle in enumerate([0,90,180,45]):
        q=np.deg2rad(angle);x=v[:,0]*np.cos(q)-v[:,2]*np.sin(q);z=v[:,0]*np.sin(q)+v[:,2]*np.cos(q)
        pp=np.stack([i*300+150+x*125,150-v[:,1]*125],1)
        for k in np.argsort(z[f].mean(1)):d.polygon([tuple(pp[j]) for j in f[k]],fill=tuple(map(int,rgb[k])))
        d.text((i*300+10,298),str(angle)+" deg",fill="white")
    sheet.save(a.output/"mesh-views.png")
    m.export(a.output/"model.glb",include_normals=True);reload=trimesh.load(a.output/"model.glb",force="mesh",process=False)
    assert len(reload.faces)==len(m.faces) and reload.visual.kind=="vertex" and np.isfinite(reload.vertices).all()
    report=dict(scope="real calibrated perspective visual hull; controlled dark backdrop; not arbitrary-photo AI",train=len(train),heldout=len(test),heldout_iou=iou,mean_iou=float(np.mean(iou)),vertices=len(m.vertices),faces=len(m.faces),watertight=bool(m.is_watertight),vertex_color_coverage=coverage,seconds=time.monotonic()-t,input_hashes=[r["hash"] for r in data])
    (a.output/"report.json").write_text(json.dumps(report,indent=2));print(report)
    if np.mean(iou)<.85:raise SystemExit("held-out silhouette acceptance failed")
if __name__=="__main__":main()
