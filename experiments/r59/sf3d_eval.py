"""Independent SF3D ONNX research benchmark, not a production engine.
Public derivative checkpoint jc-builds/sf3d-ios; Stability AI Community License.
No training, no paid API, no original gated checkpoint access.
Only diagnostic vertex-color mesh, not official SF3D UV/PBR output.
"""
import argparse, json, time, resource, hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from skimage.measure import marching_cubes
import trimesh

def sample_planes(planes, points):
    planes=np.asarray(planes);points=np.asarray(points,dtype=np.float32)
    if planes.ndim!=4 or planes.shape[0]!=3 or points.ndim!=2 or points.shape[1]!=3:
        raise ValueError("Invalid tensor")
    if not np.isfinite(points).all() or np.abs(points).max()>1.00001:
        raise ValueError("Points outside normalized volume")
    _,c,h,w=planes.shape
    features=[]
    for p,(a,b) in zip(planes,[(0,1),(0,2),(1,2)]):
        x=np.clip((points[:,a]+1)*(w-1)/2,0,w-1);y=np.clip((points[:,b]+1)*(h-1)/2,0,h-1)
        x0=x.astype(np.int32);y0=y.astype(np.int32);x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1)
        u=(x-x0).astype(np.float32);v=(y-y0).astype(np.float32)
        features.append(((p[:,y0,x0]*(1-u)*(1-v)+p[:,y0,x1]*u*(1-v)+p[:,y1,x0]*(1-u)*v+p[:,y1,x1]*u*v).T).astype(np.float32))
    return np.ascontiguousarray(np.concatenate(features,axis=1)[None])

def prep(path):
    im=Image.open(path).convert("RGBA")
    a=np.array(im)[:,:,3];ys,xs=np.where(a>=128)
    if len(xs)<100 or not (a<=16).any():raise ValueError("Pre-matted image required")
    crop=im.crop((int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)))
    size=max(crop.size);side=int(np.ceil(size/.85));canvas=Image.new("RGBA",(side,side))
    canvas.paste(crop,((side-crop.width)//2,(side-crop.height)//2))
    bg=Image.new("RGBA",canvas.size,(128,128,128,255));bg.alpha_composite(canvas)
    return np.asarray(bg.convert("RGB").resize((512,512),Image.Resampling.LANCZOS),dtype=np.float32).transpose(2,0,1)[None]/255

def decode(dec,planes,pts):
    f=sample_planes(planes,pts)
    y=dec.run(None,{dec.get_inputs()[0].name:f})[0]
    if y.shape!=(1,len(pts),4) or not np.isfinite(y).all():raise ValueError("Invalid decoder output")
    return y[0]

def main():
    import onnxruntime as ort
    p=argparse.ArgumentParser();p.add_argument("models",type=Path);p.add_argument("output",type=Path);p.add_argument("images",nargs="+",type=Path);p.add_argument("--res",type=int,default=96);a=p.parse_args()
    if not 48<=a.res<=128:raise ValueError("Resolution budget")
    a.output.mkdir(parents=True,exist_ok=True)
    opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1
    opt.enable_cpu_mem_arena=False;opt.enable_mem_pattern=False
    opt.add_session_config_entry('session.disable_prepacking','1')
    opt.log_severity_level=3
    opt.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    t=time.monotonic();enc=ort.InferenceSession(str(a.models/"sf3d_encoder.onnx"),opt,providers=["CPUExecutionProvider"]);dec=ort.InferenceSession(str(a.models/"sf3d_decoder.onnx"),opt,providers=["CPUExecutionProvider"])
    print("loaded",time.monotonic()-t,[(x.name,x.shape,x.type) for x in enc.get_inputs()],[(x.name,x.shape,x.type) for x in enc.get_outputs()],flush=True)
    assert len(enc.get_inputs())==1 and len(dec.get_inputs())==1
    reports={}
    for path in a.images:
        t=time.monotonic();x=prep(path);planes=enc.run(None,{enc.get_inputs()[0].name:x})[0];enc_seconds=time.monotonic()-t
        assert planes.shape==(1,3,40,384,384) and np.isfinite(planes).all()
        print('encoder finished',enc_seconds,'RSS KiB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
        np.save(a.output/'triplane.npy',planes)
        del enc
        import gc;gc.collect()
        planes=planes[0].astype(np.float32,copy=False);n=a.res
        q=np.linspace(-1,1,n,dtype=np.float32);field=np.empty(n**3,np.float32)
        for k in range(0,len(field),8192):
            i=np.arange(k,min(k+8192,len(field)));pts=np.column_stack([q[i//(n*n)],q[i//n%n],q[i%n]])
            field[k:k+len(i)]=decode(dec,planes,pts)[:,0]
        field=field.reshape((n,n,n));assert field.min()<10<field.max()
        boundary=max(np.take(field,k,axis=d).max() for d in range(3) for k in (0,n-1))
        if boundary>=10:raise ValueError("Surface crosses extraction bounds")
        v,f,_,_=marching_cubes(field,10,spacing=(2/(n-1),)*3,allow_degenerate=False)
        v-=1;colors=np.concatenate([decode(dec,planes,v[k:k+8192])[:,1:] for k in range(0,len(v),8192)])
        if np.min(colors)<-.001 or np.max(colors)>1.001:raise ValueError("Unexpected RGB range")
        m=trimesh.Trimesh(vertices=v*.87,faces=f,vertex_colors=np.rint(np.clip(colors,0,1)*255).astype(np.uint8),process=False)
        if m.volume<0:m.invert()
        assert m.is_watertight and m.is_winding_consistent
        out=a.output/path.stem;out.mkdir(exist_ok=True);m.export(out/"diagnostic.glb")
        Image.fromarray(np.uint8(x[0].transpose(1,2,0)*255)).save(out/"input.png")
        r=dict(real_onnx_inference=True,engine="SF3D ONNX derivative (research)",providers=['CPUExecutionProvider'],seconds=time.monotonic()-t,encoder_seconds=enc_seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,resolution=n,vertices=len(v),triangles=len(f),watertight=bool(m.is_watertight),components=len(m.split(only_watertight=False,repair=False)),field_min=float(field.min()),field_max=float(field.max()),boundary=float(boundary),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),quality_verified=False,scope="Diagnostic vertex colors only; no official UV/PBR or calibrated quality acceptance.")
        (out/"report.json").write_text(json.dumps(r,indent=2));reports[path.stem]=r;print(json.dumps(r),flush=True)
    (a.output/"report.json").write_text(json.dumps(reports,indent=2))
if __name__=="__main__":main()
