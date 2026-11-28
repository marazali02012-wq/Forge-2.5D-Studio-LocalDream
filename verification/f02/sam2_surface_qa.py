"""Real F01 meshes, independent F02 surface labels + actual SAM2 click.
Input labels describe a user's intent, NOT automatic semantic recognition.
"""
import argparse,hashlib,json,time,sys
from pathlib import Path
import numpy as np,trimesh,torch
from PIL import Image,ImageDraw
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"studio/f02"))
from surface_selection import Selection,render_ids,raster,mesh_id,mask_votes

def rgb_render(m,ids,labels=None):
    # original F01 vertex colors, frontmost triangles only
    c=np.asarray(m.visual.vertex_colors)[m.faces,:3].mean(1)
    c=np.rint(np.clip(np.where(c/255<=.0031308,12.92*c/255,1.055*(c/255)**(1/2.4)-.055),0,1)*255).astype(np.uint8)
    pic=np.full((*ids.shape,3),[29,35,43],np.uint8);ok=ids>=0;pic[ok]=c[ids[ok]]
    if labels is not None:
        b=ok&(labels[np.maximum(ids,0)]==1);pic[b]=(pic[b]*.25+np.array([255,164,52])*.75).astype(np.uint8)
    return pic

def main():
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);p.add_argument("checkpoint",type=Path);p.add_argument("out",type=Path);a=p.parse_args();a.out.mkdir(exist_ok=False)
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    predictor=SAM2ImagePredictor(build_sam2("configs/sam2.1/sam2.1_hiera_t.yaml",str(a.checkpoint),device="cpu",apply_postprocessing=False))
    # User-like explicit point prompts on the actual rendered mesh; no GT.
    cases=[("chair","chair back",(.50,.28)),("robot_regression","robot head",(.50,.31)),("seated_scene","seated person",(.36,.39))]
    rows=[]
    for name,intent,point in cases:
        t=time.monotonic();path=a.source/name/"generated.glb";raw=path.read_bytes()
        m=trimesh.load(path,force="mesh",process=False)
        # existing TripoSR proper Y-up rotation; source file unchanged
        m.apply_transform(np.array([[0.,1,0,0],[0,0,1,0],[1,0,0,0],[0,0,0,1]]))
        original=mesh_id(m);s=Selection(m);ids=render_ids(m,0);im=rgb_render(m,ids)
        ys,xs=np.where(ids>=0);target=np.array(point)*ids.shape[0];k=np.argmin((xs-target[0])**2+(ys-target[1])**2);x,y=int(xs[k]),int(ys[k]);seed=int(ids[y,x])
        # Exercise brush and full undo before the learned mask.
        brush=s.brush(seed,.08,2);assert len(brush)>0 and s.undo() and not s.labels.any()
        with torch.inference_mode():
            predictor.set_image(im)
            masks,scores,_=predictor.predict(point_coords=np.array([[x,y]],np.float32),point_labels=np.array([1],np.int32),multimask_output=True)
        # Choose highest score nonempty mask including click, with no claim
        # of semantic correctness. Unknown/unobserved faces stay unlabeled.
        eligible=[j for j,v in enumerate(masks) if v[y,x] and (v&(ids>=0)).any()]
        if not eligible:raise ValueError("no real mask includes click")
        k=max(eligible,key=lambda j:float(scores[j]));mask=np.asarray(masks[k],bool)&(ids>=0)
        idx=s.apply_mask(ids,mask,1);assert len(idx)>0 and set(idx)<=set(np.unique(ids[mask]))
        before=s.labels.copy();s.brush(seed,.025,0);assert s.undo() and np.array_equal(before,s.labels)
        side=a.out/(name+".labels.json");s.save(side,{"1":intent});q=Selection(m);q.load(side);assert np.array_equal(q.labels,s.labels)
        altered=m.copy();altered.vertices[0,0]+=.0001
        try:Selection(altered).load(side);raise AssertionError("wrong geometry accepted")
        except ValueError:pass
        assert mesh_id(m)==original and path.read_bytes()==raw
        # Show input, real SAM2 pixel mask and the same face labels across 4 views.
        sheet=Image.new("RGB",(1536,1040),(29,35,43));d=ImageDraw.Draw(sheet)
        overlay=im.copy();overlay[mask]=(im[mask]*.25+np.array([255,164,52])*.75).astype(np.uint8)
        for j,(title,pic) in enumerate([("ORIGINAL RENDER",im),("SAM2 CLICK MASK",overlay),("SURFACE FRONT",rgb_render(m,ids,s.labels)),("SURFACE SIDE",rgb_render(m,render_ids(m,90),s.labels)),("SURFACE BACK",rgb_render(m,render_ids(m,180),s.labels)),("SURFACE 3/4",rgb_render(m,render_ids(m,45),s.labels))]):
            xx=j%3*512;yy=j//3*520;sheet.paste(Image.fromarray(pic),(xx,yy));d.text((xx+12,yy+500),title,fill="white")
        d.ellipse((x+512-5,y-5,x+512+5,y+5),outline="white",width=2);sheet.save(a.out/(name+".jpg"),quality=92)
        hit,seen=mask_votes(ids,mask,len(m.faces))
        rows.append(dict(name=name,user_intent=intent,point=[x,y],model_score=float(scores[k]),mesh_faces=len(m.faces),visible_faces=int((seen>0).sum()),selected_faces=len(idx),unknown_faces=int((s.labels==0).sum()),brush_faces=len(brush),source_sha256=hashlib.sha256(raw).hexdigest(),mesh_id=original,mesh_unchanged=True,undo=True,wrong_mesh_rejected=True,seconds=time.monotonic()-t))
        (a.out/"report.json").write_text(json.dumps(dict(engine="SAM2.1 tiny CPU",checkpoint_sha256=hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),cases=rows,semantic_automatic=False),indent=2))
    # Verify frontmost selection on overlapping triangles.
    uv=np.array([[3.,3.],[12.,3.],[3.,12.],[3.,3.],[12.,3.],[3.,12.]])
    z=np.array([2.,2.,2.,1.,1.,1.]);f=np.array([[0,1,2],[3,4,5]])
    assert raster(uv,z,f,16)[5,5]==1
    print(json.dumps(rows,indent=2))
if __name__=="__main__":main()
