"""User-box part extraction. GrabCut is classical CPU, not a neural model.
Optional MobileSAM is loaded only from a locally installed trusted checkpoint.
Only alpha may change, strictly inside the user box, and only after client review.
"""
import importlib.util, io, os
from pathlib import Path
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parent

def model_path():
    return Path(os.environ.get('FORGE_MOBILESAM_MODEL') or ROOT/'models/mobile_sam.pt').expanduser()

def diagnose():
    return {'grabcut':importlib.util.find_spec('cv2') is not None,
            'mobilesam':all(importlib.util.find_spec(n) is not None for n in ('mobile_sam','torch')) and model_path().is_file(),
            'inference_verified':False}

_predictor=None
_predictor_key=None

def sam_mask(rgb,alpha,box,points=()):
    import torch
    from mobile_sam import sam_model_registry, SamPredictor
    global _predictor,_predictor_key
    p=model_path();st=p.stat();key=(str(p.resolve()),st.st_size,st.st_mtime_ns)
    if _predictor is None or key!=_predictor_key:
        model=sam_model_registry['vit_t'](checkpoint=str(p)).to('cpu').eval()
        _predictor=SamPredictor(model);_predictor_key=key
    try:
        with torch.inference_mode():
            _predictor.set_image(rgb)
            x0,y0,x1,y1=box
            kwargs={} if not points else {"point_coords":np.array([p[:2] for p in points],dtype=np.float32),"point_labels":np.array([p[2] for p in points],dtype=np.int32)}
            masks,scores,_=_predictor.predict(box=np.array([x0,y0,x1-1,y1-1],dtype=np.float32),multimask_output=True,**kwargs)
        return select_safe_sam(masks,scores,alpha,box,points)
    finally:_predictor.reset_image()

def grab_mask(rgb,alpha,box):
    import cv2
    x0,y0,x1,y1=box
    # Bound runtime without resampling the actual output pixels.
    h,w=alpha.shape; pad=max(8,min(64,max(x1-x0,y1-y0)//4)); l=max(0,x0-pad); t=max(0,y0-pad); r=min(w,x1+pad); b=min(h,y1+pad)
    roi=rgb[t:b,l:r].copy(); a=alpha[t:b,l:r]; mask=np.zeros(a.shape,np.uint8)
    mask[y0-t:y1-t,x0-l:x1-l]=cv2.GC_PR_FGD
    mask[a==0]=cv2.GC_BGD
    if np.count_nonzero(mask==cv2.GC_PR_FGD)<10 or np.count_nonzero(mask==cv2.GC_BGD)<10:raise ValueError('Insufficient foreground/background samples')
    bg=np.zeros((1,65),np.float64);fg=bg.copy()
    cv2.grabCut(roi,mask,None,bg,fg,3,cv2.GC_INIT_WITH_MASK)
    result=np.zeros(alpha.shape,bool);result[t:b,l:r]=(mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD)
    return result

def validate_points(points,alpha,box):
    """1=remove, 0=protect. Coordinates refer to original source pixels."""
    if not isinstance(points,(list,tuple)) or len(points)>12:raise ValueError('Invalid point list')
    h,w=alpha.shape;x0,y0,x1,y1=box;seen=set();out=[]
    for p in points:
        if not isinstance(p,(list,tuple)) or len(p)!=3 or any(type(v) is not int for v in p):raise ValueError('Invalid point')
        x,y,k=p
        if k not in (0,1) or not (0<=x<w and 0<=y<h) or (x,y) in seen:raise ValueError('Invalid or duplicate point')
        if k and not (x0<=x<x1 and y0<=y<y1 and alpha[y,x]>0):raise ValueError('Removal point must be inside visible selection')
        if not k and alpha[y,x]==0:raise ValueError('Protection point must be visible')
        seen.add((x,y));out.append((x,y,k))
    if out and not any(k==1 for x,y,k in out):raise ValueError('At least one removal point required')
    return tuple(out)

def validate_mask(mask,alpha,box,points=()):
    """Reject a candidate without modifying any pixels. Ignore transparent padding."""
    m=np.asarray(mask,dtype=bool)
    if m.shape!=alpha.shape:raise ValueError('Invalid mask shape')
    x0,y0,x1,y1=box; inside=np.zeros_like(m,dtype=bool);inside[y0:y1,x0:x1]=True
    if np.any(m&~inside&(alpha>0)):raise ValueError('Protected region selected')
    m=m&inside&(alpha>0)
    if any(bool(m[y,x])!=bool(k) for x,y,k in points):raise ValueError('Mask violates user points')
    mass=int(alpha[m].sum());total=int(alpha.sum())
    if not mass or mass>total*.4:raise ValueError('Empty or unsafe selection (>40% alpha mass)')
    from scipy.ndimage import label
    labels,n=label(m,structure=np.ones((3,3),dtype=np.uint8))
    if n>1:
        weights=np.bincount(labels[m],weights=alpha[m],minlength=n+1)
        if weights.max()<mass*.95:raise ValueError('Multiple substantial disconnected regions; narrow the box')
    return m,mass

def select_safe_sam(masks,scores,alpha,box,points=()):
    """Use the best *safe* candidate, not merely the highest model score."""
    scores=np.asarray(scores)
    if scores.ndim!=1 or len(scores)!=len(masks):raise ValueError('Invalid MobileSAM scores')
    for i in np.argsort(scores,kind='stable')[::-1]:
        if not np.isfinite(scores[i]):continue
        try:return validate_mask(masks[i],alpha,box,points)[0]
        except ValueError:continue
    raise ValueError('No safe MobileSAM proposal')

def remove_part(image,box,engine,points=()):
    p=np.array(image.convert('RGBA'));h,w=p.shape[:2];alpha=p[:,:,3];x0,y0,x1,y1=box
    if w*h>1536**2 or not (0<=x0<x1<=w and 0<=y0<y1<=h) or min(x1-x0,y1-y0)<6:raise ValueError('Invalid selection box')
    total=int(alpha.sum())
    if not total or (alpha==0).mean()<.01:raise ValueError('Transparent source required')
    if (x1-x0)*(y1-y0)>w*h*.75:raise ValueError('Selection too large')
    points=validate_points(points,alpha,box)
    if points and engine!='mobilesam':raise ValueError('Point prompts require MobileSAM')
    rgb=np.ascontiguousarray(p[:,:,:3]);
    if engine=='grabcut':m=grab_mask(rgb,alpha,box)
    elif engine=='mobilesam':m=sam_mask(rgb,alpha,box,points)
    else:raise ValueError('Unknown engine')
    m,mass=validate_mask(m,alpha,box,points)
    p[m,3]=0
    out=io.BytesIO();Image.fromarray(p).save(out,format='PNG')
    return out.getvalue(),{'engine':engine,'removed_pixels':int(m.sum()),'alpha_fraction':mass/total,'neural_mask':engine=='mobilesam','semantic_ai':False,'point_count':len(points)}
