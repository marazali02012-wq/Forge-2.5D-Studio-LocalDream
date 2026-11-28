"""F01 SAM 2 foreground assistance, not semantic 3D part separation.
Box prompt comes from existing foreground mask; no manual benchmark labels.
Compare masks and reconstruction without altering working default.
"""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np,torch,trimesh
from PIL import Image,ImageDraw
from scipy.ndimage import binary_erosion
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from perspective_photo_probe import read_middlebury,reconstruct,colorize,silhouette

def main():
    p=argparse.ArgumentParser();p.add_argument("dataset",type=Path);p.add_argument("checkpoint",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    rows=read_middlebury(a.dataset,a.output/"baseline_masks")
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    predictor=SAM2ImagePredictor(build_sam2("configs/sam2.1/sam2.1_hiera_t.yaml",str(a.checkpoint),device="cpu",apply_postprocessing=False))
    result=[];modified=[]
    t=time.monotonic()
    for row in rows:
        m=row["mask"];y,x=np.where(m);h,w=m.shape
        box=np.array([max(0,x.min()-8),max(0,y.min()-8),min(w-1,x.max()+8),min(h-1,y.max()+8)],np.float32)
        with torch.inference_mode():
            predictor.set_image(row["im"])
            masks,scores,_=predictor.predict(box=box,multimask_output=True)
        k=int(np.argmax(scores));candidate=np.asarray(masks[k],bool)
        if not candidate.any():raise ValueError("SAM2 empty mask")
        iou=float((candidate&m).sum()/max(1,(candidate|m).sum()))
        result.append(dict(name=row["name"],iou_with_baseline=iou,model_score=float(scores[k]),area_ratio=float(candidate.sum()/m.sum())))
        q=dict(row,mask=candidate);modified.append(q)
        panel=Image.new("RGB",(w*3,h))
        panel.paste(Image.fromarray(row["im"]),(0,0))
        for j,mask in enumerate([m,candidate],1):
            overlay=row["im"].copy();overlay[~mask]=(overlay[~mask]*.25).astype(np.uint8)
            panel.paste(Image.fromarray(overlay),(j*w,0))
        panel.save(a.output/(Path(row["name"]).stem+".jpg"))
    # Fixed held-out baseline masks: comparison is not independent GT.
    test=rows[::4];report=dict(engine="SAM2.1 tiny CPU",checkpoint_sha256=hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),mask_comparisons=result,seconds=time.monotonic()-t)
    (a.output/"report.json").write_text(json.dumps(report,indent=2))
    for name,source in [("baseline",rows),("sam2",modified)]:
        train=[r for i,r in enumerate(source) if i%4]
        m=reconstruct(train);colorize(m,train)
        score=[]
        for row in test:
            pred=silhouette(m,row);truth=row["mask"];score.append(float((pred&truth).sum()/max(1,(pred|truth).sum())))
        m.export(a.output/(name+".glb"),include_normals=True)
        report[name]=dict(faces=len(m.faces),watertight=bool(m.is_watertight),heldout_iou=score,mean_iou=float(np.mean(score)))
        (a.output/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    if report["sam2"]["mean_iou"]<.85:raise ValueError("SAM2 candidate below existing silhouette gate")
if __name__=="__main__":main()
