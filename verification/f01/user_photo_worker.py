"""F01 experimental user-photo pipeline. No calibration-file or model template input.
Supports 12-48 overlapping views from same camera/size, isolated subject on
a controlled plain backdrop or explicit PNG alpha. OpenMVS is external AGPL.
"""
import argparse,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
import numpy as np,cv2,pycolmap,trimesh
from scipy.ndimage import binary_erosion,binary_dilation
from skimage.measure import label
from PIL import Image,ImageOps,ImageDraw
from colmap_photo_probe import solve,estimated_views
from forge_dense_color import colorize_dense
from forge_sfm_orientation import alignment
from openmvs_mobile_lod import topo
from perspective_photo_probe import silhouette
Image.MAX_IMAGE_PIXELS=12_000_000

def foreground(im):
    # Estimate actual studio background from perimeter pixels; do not
    # use a fixed black threshold. Keep the largest non-border component
    # only if it represents the dominant foreground, otherwise reject.
    rgb=im.astype(np.float32)
    border=np.concatenate([rgb[:4].reshape(-1,3),rgb[-4:].reshape(-1,3),rgb[:,:4].reshape(-1,3),rgb[:,-4:].reshape(-1,3)])
    bg=np.median(border,axis=0)
    delta=np.linalg.norm(rgb-bg,axis=2)
    border_delta=np.linalg.norm(border-bg,axis=1)
    # Actual dinoSR0002 is genuinely cropped at the top: the main
    # subject touches the sensor boundary. Keep that observed silhouette,
    # but treat pixels outside the camera image as unknown during carving.
    threshold=max(40.,float(np.quantile(border_delta,.90))+8.)
    fg=delta>threshold
    cc=label(fg);counts=np.bincount(cc.ravel());counts[0]=0
    best=int(counts.argmax())
    mask=(cc==best) if best else np.zeros(delta.shape,bool)
    edges=set(np.unique(np.concatenate([cc[0],cc[-1],cc[:,0],cc[:,-1]])).tolist())
    # Refine the coarse silhouette with foreground/background GMMs.
    # Locally validated on all 16 diagnostic photo copies, not fixed
    # per-object templates. Leave clipped sensor pixels observable.
    sure_fg=binary_erosion(mask&(delta>max(85.,threshold+30.)),iterations=3)
    sure_bg=(delta<max(24.,threshold*.6))&~binary_dilation(mask,iterations=4)
    if sure_fg.any() and sure_bg.any():
        gc=np.full(mask.shape,cv2.GC_PR_BGD,np.uint8)
        gc[mask]=cv2.GC_PR_FGD;gc[sure_fg]=cv2.GC_FGD;gc[sure_bg]=cv2.GC_BGD
        cv2.grabCut(im,gc,None,np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),3,cv2.GC_INIT_WITH_MASK)
        refined=(gc==cv2.GC_FGD)|(gc==cv2.GC_PR_FGD)
        cc=label(refined);counts=np.bincount(cc.ravel());counts[0]=0
        best=int(counts.argmax());candidate=(cc==best)
        # Refuse substantial accidental foreground loss/growth.
        if best and .8*mask.sum()<=candidate.sum()<=1.2*mask.sum():mask=candidate

    return mask

def prepare(src,out):
    files=sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in (".png",".jpg",".jpeg",".webp"))
    if not 12<=len(files)<=48:raise ValueError("12–48 photos required")
    images=out/"images";masks=out/"masks";images.mkdir();masks.mkdir()
    data={};hashes=set();shape=None
    for i,p in enumerate(files):
        if p.stat().st_size>5*1024*1024:raise ValueError("photo exceeds 5 MiB")
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest in hashes:raise ValueError("duplicate photo")
        hashes.add(digest)
        with Image.open(p) as f:
            if f.format not in ("PNG","JPEG","WEBP") or f.width*f.height>12_000_000:raise ValueError("invalid photo")
            rgba=ImageOps.exif_transpose(f).convert("RGBA");rgba.thumbnail((1280,1280))
        arr=np.asarray(rgba);rgb=arr[:,:,:3].copy();alpha=arr[:,:,3]
        if shape is None:shape=rgb.shape
        if rgb.shape!=shape:raise ValueError("same image dimensions and camera orientation required")
        if np.any(alpha<255):
            mask=alpha>=128
            rgb[~mask]=0
        else:mask=foreground(rgb)
        if not .002<mask.mean()<.8:raise ValueError("invalid foreground; use plain background or transparent PNG")
        # Reject bit-identical processed RGB photos even when file metadata differs.
        phash=hashlib.sha256(rgb.tobytes()).hexdigest()
        if any(row["pixel_hash"]==phash for row in data.values()):raise ValueError("duplicate processed photo")
        name=f"view{i:02d}.png";Image.fromarray(rgb).save(images/name)
        Image.fromarray(mask.astype(np.uint8)*255).save(masks/(name+".png"))
        data[name]=dict(name=name,im=rgb,mask=mask,hash=digest,pixel_hash=phash)
    return data

def run_mvs(bin_dir,out):
    undist=out/"undistorted";pycolmap.undistort_images(str(undist),str(out/"colmap/sparse"),str(out/"images"))
    dm=out/"dense_masks";dm.mkdir()
    for p in sorted((undist/"images").glob("*.png")):
        orig=np.asarray(Image.open(out/"images"/p.name).convert("RGB"))
        fixed=np.asarray(Image.open(p).convert("RGB"))
        if orig.shape!=fixed.shape or np.mean(np.abs(orig.astype(float)-fixed))>=1:raise ValueError("undistortion changed mask grid")
        m=Image.open(out/"masks"/(p.name+".png")).convert("L");m.save(dm/(p.stem+".mask.png"))
    def run(tool,args,timeout):
        exe=bin_dir/tool
        if not exe.is_file() or not os.access(exe,os.X_OK):raise RuntimeError("OpenMVS executable unavailable")
        subprocess.run([str(exe),*map(str,args)],cwd=out,check=True,timeout=timeout)
    run("InterfaceCOLMAP",["-i",undist,"-o",out/"scene.mvs","--image-folder",undist/"images"],90)
    run("DensifyPointCloud",["scene.mvs","--resolution-level","0","--max-threads","4","--mask-path",dm,"--ignore-mask-label","0"],720)
    run("ReconstructMesh",["scene_dense.mvs","-p","scene_dense.ply","--max-threads","4"],180)
    m=trimesh.load(out/"scene_dense_mesh.ply",force="mesh",process=False)
    if len(m.faces)<=100 or not np.isfinite(m.vertices).all() or np.any(m.extents<=0):raise RuntimeError("invalid dense mesh")
    return m

def main():
    p=argparse.ArgumentParser();p.add_argument("photos",type=Path);p.add_argument("output",type=Path);p.add_argument("--openmvs-bin",type=Path,required=True);p.add_argument("--image-up",choices=["top","right","bottom","left"],default="top");a=p.parse_args()
    src=a.photos.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    t=time.monotonic();data=prepare(src,out)
    r=solve(out/"images",out/"masks",out/"colmap");views=estimated_views(r,data)
    error=float(r.compute_mean_reprojection_error())
    report=dict(scope="same-camera overlapping photos; plain backdrop or explicit alpha; no reference calibration",input_photos=len(data),registered=len(views),points=r.num_points3D(),reprojection_px=error,input_hashes=[v["hash"] for v in data.values()])
    (out/"report.json").write_text(json.dumps(report,indent=2))
    if len(views)<max(6,math.ceil(.75*len(data))) or r.num_points3D()<100 or not np.isfinite(error) or error>2:raise ValueError("insufficient real camera recovery")
    m=run_mvs(a.openmvs_bin.resolve(),out);report["dense_faces"]=len(m.faces);report["dense_topology"]=topo(m)
    if not m.is_winding_consistent or report["dense_topology"]["nonmanifold"]:raise ValueError("invalid dense topology")
    m.export(out/"dense.glb",include_normals=True)
    if len(m.faces)>60000 or len(m.vertices)>30000:
        if m.is_watertight:raise ValueError("closed dense LOD not supported by this experimental route")
        lod=out/"lod";subprocess.run([sys.executable,str(Path(__file__).with_name("openmvs_mobile_lod.py")),str(out/"dense.glb"),str(lod)],check=True,timeout=90)
        lr=json.loads((lod/"report.json").read_text())
        if lr["selected"] not in ("preserve","quadric"):raise ValueError("no safe mobile LOD")
        m=trimesh.load(lod/(lr["selected"]+".glb"),force="mesh",process=False);report["lod"]=lr
    colors,stats=colorize_dense(m,views);m.visual.vertex_colors=colors;report.update(stats)
    if stats["coverage"]<.94:raise ValueError("insufficient observed colors")
    # Six distributed input-view silhouettes, not independent held-out evidence.
    ordered_views=sorted(views,key=lambda q:q["name"]);scores=[]
    for i in np.linspace(0,len(ordered_views)-1,6,dtype=int):
        q=ordered_views[i];pred=silhouette(m,q);truth=q["mask"]
        pred=np.asarray(pred,dtype=bool);truth=np.asarray(truth,dtype=bool)
        intersection=int((pred&truth).sum());union=int((pred|truth).sum())
        scores.append(float(intersection/max(1,union)))
        # Preserve the failed result as a diagnostic, never as accepted model.glb.
        overlay=np.zeros((*truth.shape,3),np.uint8)
        overlay[truth&pred]=(70,210,115)
        overlay[truth&~pred]=(245,72,75)
        overlay[pred&~truth]=(70,145,245)
        diag=out/"silhouette_diagnostics";diag.mkdir(exist_ok=True)
        Image.fromarray(overlay).save(diag/(q["name"]+".png"))
        report.setdefault("silhouette_per_view",[]).append(dict(name=q["name"],iou=scores[-1],
            truth_pixels=int(truth.sum()),predicted_pixels=int(pred.sum()),
            missing_pixels=int((truth&~pred).sum()),extra_pixels=int((pred&~truth).sum())))
    report["input_view_iou"]=scores;report["mean_input_iou"]=float(np.mean(scores))
    report["silhouette_accepted"]=report["mean_input_iou"]>=.85
    (out/"report.json").write_text(json.dumps(report,indent=2));print(json.dumps({"silhouette_per_view":report["silhouette_per_view"],"mean_input_iou":report["mean_input_iou"]}),flush=True)
    if not report["silhouette_accepted"]:
        m.export(out/"rejected-silhouette.glb",include_normals=True)
        raise ValueError("silhouette mismatch; see diagnostics, rejected model is not deliverable")
    ordered=sorted((im for im in r.images.values() if im.has_pose),key=lambda im:im.name)
    rt=[im.cam_from_world().matrix() for im in ordered];T,metrics=alignment([q[:,:3] for q in rt],[-q[:,:3].T@q[:,3] for q in rt],a.image_up)
    m.apply_transform(T);dst=out/"model.glb";m.export(dst,include_normals=True)
    q=trimesh.load(dst,force="mesh",process=False)
    assert len(q.faces)==len(m.faces) and q.visual.kind=="vertex" and np.isfinite(q.vertices).all() and len(q.faces)<=60000 and len(q.vertices)<=30000 and dst.stat().st_size<=8000000
    report.update(faces=len(q.faces),vertices=len(q.vertices),watertight=bool(q.is_watertight),orientation=metrics,seconds=time.monotonic()-t)
    (out/"report.json").write_text(json.dumps(report,indent=2));print(report,flush=True)
    v=np.asarray(q.vertices).copy();v-=(v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max()
    f=np.asarray(q.faces);c=np.asarray(q.visual.vertex_colors)[f,:3].mean(1)/255.
    c=np.rint(np.clip(np.where(c<=.0031308,12.92*c,1.055*np.maximum(c,0)**(1/2.4)-.055),0,1)*255).astype(np.uint8)
    im=Image.new("RGB",(1200,320),(32,38,48));d=ImageDraw.Draw(im)
    for i,angle in enumerate([0,90,180,45]):
        rad=np.deg2rad(angle);x=v[:,0]*np.cos(rad)-v[:,2]*np.sin(rad);z=v[:,0]*np.sin(rad)+v[:,2]*np.cos(rad)
        pp=np.stack([i*300+150+125*x,150-125*v[:,1]],1)
        for j in np.argsort(z[f].mean(1)):d.polygon([tuple(pp[k]) for k in f[j]],fill=tuple(map(int,c[j])))
        d.text((i*300+10,298),str(angle)+" deg",fill="white")
    im.save(out/"model-views.png")
if __name__=="__main__":main()
