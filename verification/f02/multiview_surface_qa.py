"""Evaluate actual multiview SAM2 selection on the same immutable F01 meshes."""
import argparse,json,hashlib,time,sys
from pathlib import Path
import numpy as np,torch,trimesh
from PIL import Image,ImageDraw
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from sam2_surface_qa import rgb_render,Selection,render_ids,mesh_id
from multiview_selection import normalized_masks,propagate,face_observation
def main():
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);p.add_argument("checkpoint",type=Path);p.add_argument("out",type=Path);a=p.parse_args();a.out.mkdir(exist_ok=False)
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    predictor=SAM2ImagePredictor(build_sam2("configs/sam2.1/sam2.1_hiera_t.yaml",str(a.checkpoint),device="cpu",apply_postprocessing=False))
    rows=[]
    for name,intent,point in [("chair","chair back",(.50,.28)),("robot_regression","robot head",(.50,.31)),("seated_scene","seated person",(.36,.39))]:
        t=time.monotonic();path=a.source/name/"generated.glb";raw=path.read_bytes();m=trimesh.load(path,force="mesh",process=False)
        m.apply_transform(np.array([[0.,1,0,0],[0,0,1,0],[1,0,0,0],[0,0,0,1]]))
        identity=mesh_id(m);frames=[]
        for angle in range(0,360,30):
            ids=render_ids(m,angle,size=512);frames.append((ids,rgb_render(m,ids)))
        ids,img=frames[0];ys,xs=np.where(ids>=0);target=np.array(point)*512;k=np.argmin((xs-target[0])**2+(ys-target[1])**2);x,y=int(xs[k]),int(ys[k])
        with torch.inference_mode():
            predictor.set_image(img)
            masks,scores,_=predictor.predict(point_coords=np.array([[x,y]],np.float32),point_labels=np.array([1],np.int32),multimask_output=True)
            masks,scores=normalized_masks(masks,scores,ids.shape)
            eligible=[j for j,v in enumerate(masks) if v[y,x] and (v&(ids>=0)).any()]
            if not eligible:raise ValueError("missing valid seed")
            mask=masks[max(eligible,key=lambda j:scores[j])]&(ids>=0)
            sel,pos,neg,masks_by_view,audit=propagate(predictor,frames,mask,len(m.faces))
        fp,fn=face_observation(ids,mask,len(m.faces));selection=Selection(m);selection.labels[sel]=1
        selection.save(a.out/(name+".labels.json"),{"1":intent});q=Selection(m);q.load(a.out/(name+".labels.json"));assert np.array_equal(q.labels,selection.labels)
        assert path.read_bytes()==raw and identity==mesh_id(m)
        # Actual accepted masks and fused face labels in all 12 views.
        sheet=Image.new("RGB",(1536,4*540),(29,35,43));d=ImageDraw.Draw(sheet)
        for j,(ii,im) in enumerate(frames):
            xx=j%3*512;yy=j//3*540;panel=rgb_render(m,ii,selection.labels);sheet.paste(Image.fromarray(panel),(xx,yy));d.text((xx+12,yy+516),f"{j*30} deg | mask {'accepted' if j in masks_by_view else 'not accepted'}",fill="white")
        sheet.save(a.out/(name+".jpg"),quality=90)
        # Unobserved faces and contradictory votes remain distinguishable.
        np.savez_compressed(a.out/(name+"-votes.npz"),positive=pos,negative=neg,selected=sel)
        row=dict(name=name,intent=intent,faces=len(m.faces),seed_faces=int(fp.sum()),selected_faces=int(sel.sum()),new_faces=int((sel&~fp).sum()),accepted_views=len(masks_by_view),unobserved_faces=int(((pos+neg)==0).sum()),conflicting_faces=int(((pos>0)&(neg>0)).sum()),audit=audit,source_sha256=hashlib.sha256(raw).hexdigest(),unchanged=True,seconds=time.monotonic()-t)
        rows.append(row);(a.out/"report.json").write_text(json.dumps(dict(engine="SAM2.1 tiny + visible-face anchored fusion",semantic_ground_truth=False,cases=rows),indent=2));print(json.dumps(row),flush=True)
    # A meaningful expansion is necessary; mere front-seed fallback is not success.
    if not all(r["new_faces"]>0 and r["accepted_views"]>=3 for r in rows):raise SystemExit("multiview expansion acceptance failed")
if __name__=="__main__":main()
