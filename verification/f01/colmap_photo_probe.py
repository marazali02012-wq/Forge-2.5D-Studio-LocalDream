"""F01 real camera calibration with COLMAP 3.12.1.
No ground-truth camera poses are passed into the solver.
The existing perspective reconstruction receives estimated camera matrices.
"""
import argparse,json,math,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import pycolmap
from perspective_photo_probe import read_middlebury,reconstruct,colorize
import trimesh

def solve(images,masks,out):
    images=Path(images);masks=Path(masks);out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    db=str(out/"features.db")
    models=out/"sparse";models.mkdir()
    reader=pycolmap.ImageReaderOptions(mask_path=str(masks))
    pycolmap.extract_features(db,str(images),camera_mode=pycolmap.CameraMode.SINGLE,camera_model="PINHOLE",reader_options=reader,sift_options=pycolmap.SiftExtractionOptions(num_threads=4,peak_threshold=0.003,max_num_features=8192,estimate_affine_shape=True,domain_size_pooling=True),device=pycolmap.Device.cpu)
    pycolmap.match_exhaustive(db,sift_options=pycolmap.SiftMatchingOptions(num_threads=4,guided_matching=True),device=pycolmap.Device.cpu)
    opts=pycolmap.IncrementalPipelineOptions(num_threads=4)
    reconstructions=pycolmap.incremental_mapping(db,str(images),str(models),options=opts)
    if not reconstructions:raise RuntimeError("COLMAP recovered no camera model")
    r=max(reconstructions.values(),key=lambda r:r.num_reg_images())
    r.write_text(str(models))
    return r

def estimated_views(r,source):
    rows=[]
    for im in r.images.values():
        if not im.has_pose:continue
        row=source[im.name]
        K=r.cameras[im.camera_id].calibration_matrix()
        rt=im.cam_from_world().matrix()
        R,t=rt[:,:3],rt[:,3]
        C=-R.T@t
        y,x=np.where(row["mask"]);ray=R.T@np.linalg.solve(K,[x.mean(),y.mean(),1.]);ray/=np.linalg.norm(ray)
        rows.append(dict(row,P=K@rt,C=C,ray=ray))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument("dataset",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    # Only the RGB + generated foreground masks enter the SfM solver.
    source=read_middlebury(a.dataset,a.output/"mask_previews")
    images=a.output/"images";masks=a.output/"masks";images.mkdir();masks.mkdir()
    for row in source:
        Image.fromarray(row["im"]).save(images/row["name"])
        Image.fromarray(row["mask"].astype(np.uint8)*255).save(masks/(row["name"]+".png"))
    t=time.monotonic();r=solve(images,masks,a.output/"colmap")
    rows=estimated_views(r,{x["name"]:x for x in source})
    error=float(r.compute_mean_reprojection_error())
    report=dict(engine="pycolmap 3.12.1 CPU",input_photos=len(source),registered=len(rows),points=r.num_points3D(),mean_reprojection_error_px=error,seconds=time.monotonic()-t,scope="unknown camera pose recovery; no metric scale")
    (a.output/"report.json").write_text(json.dumps(report,indent=2));print(report,flush=True)
    if len(rows)<max(6,math.ceil(.75*len(source))) or r.num_points3D()<100 or not np.isfinite(error) or error>2:raise ValueError("camera recovery acceptance failed")
    # Compare estimated camera centers to reference only AFTER solving.
    known={x["name"]:x["C"] for x in source}
    x=np.array([q["C"] for q in rows]);y=np.array([known[q["name"]] for q in rows])
    xc=x-x.mean(0);yc=y-y.mean(0);u,sv,vt=np.linalg.svd(xc.T@yc)
    sign=np.ones(3);sign[-1]=np.linalg.det(u@vt);rot=u@np.diag(sign)@vt
    scale=(sv*sign).sum()/(xc*xc).sum();aligned=scale*xc@rot+y.mean(0)
    report["aligned_camera_rmse_pct"]=float(np.sqrt(np.mean(np.sum((aligned-y)**2,axis=1)))/np.linalg.norm(np.ptp(y,axis=0))*100)
    (a.output/"report.json").write_text(json.dumps(report,indent=2))
    # Never substitute sparse point clouds for a surface.
    m=reconstruct(rows);coverage=colorize(m,rows)
    dst=a.output/"model.glb";m.export(dst,include_normals=True)
    q=trimesh.load(dst,force="mesh",process=False);assert len(q.faces)==len(m.faces) and q.visual.kind=="vertex"
    report.update(faces=len(q.faces),vertices=len(q.vertices),watertight=bool(q.is_watertight),color_coverage=coverage)
    (a.output/"report.json").write_text(json.dumps(report,indent=2));print(report,flush=True)
    # Actual model rendered from 4 angles.
    v=np.asarray(q.vertices).copy();v-=(v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max()
    f=np.asarray(q.faces);c=np.asarray(q.visual.vertex_colors)[f,:3].mean(1)/255.
    c=np.rint(np.where(c<=.0031308,12.92*c,1.055*np.maximum(c,0)**(1/2.4)-.055)*255).astype(np.uint8)
    img=Image.new("RGB",(1200,320),(32,38,48));d=ImageDraw.Draw(img)
    for i,angle in enumerate([0,90,180,45]):
        a1=np.deg2rad(angle);xx=v[:,0]*np.cos(a1)-v[:,2]*np.sin(a1);zz=v[:,0]*np.sin(a1)+v[:,2]*np.cos(a1)
        p=np.stack([i*300+150+125*xx,150-125*v[:,1]],1)
        for k in np.argsort(zz[f].mean(1)):d.polygon([tuple(p[j]) for j in f[k]],fill=tuple(map(int,c[k])))
        d.text((i*300+10,298),str(angle)+" deg",fill="white")
    img.save(a.output/"mesh-views.png")
if __name__=="__main__":main()
