"""Heuristic front-silhouette QA. Not a semantic or full 3D quality certificate."""
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label, binary_dilation
N=192

def source_mask(image):
    a=np.asarray(image.convert('RGBA'))[:,:,3]; y,x=np.where(a>=96)
    if not len(x): raise ValueError('No visible source')
    a=a[y.min():y.max()+1,x.min():x.max()+1]; h,w=a.shape
    scale=(N-12)/max(h,w); size=(max(1,round(w*scale)),max(1,round(h*scale)))
    out=Image.new('L',(N,N)); out.paste(Image.fromarray(a).resize(size,Image.Resampling.BILINEAR),((N-size[0])//2,(N-size[1])//2))
    return np.asarray(out)>=96

def projection(vertices,faces):
    p=np.asarray(vertices,dtype=float)[:,:2].copy(); p[:,1]*=-1
    lo=p.min(0); hi=p.max(0); span=max(hi-lo)
    if not np.isfinite(p).all() or span<=1e-9: raise ValueError('Invalid projected geometry')
    p=(p-(lo+hi)/2)*((N-12)/span)+N/2
    out=Image.new('L',(N,N)); d=ImageDraw.Draw(out); points=list(map(tuple,p.tolist()))
    for f in faces: d.polygon([points[i] for i in f],fill=255)
    return np.asarray(out)>0

def compare(reference,vertices,faces):
    b=projection(vertices,faces); a=reference
    inter=int((a&b).sum()); union=int((a|b).sum()); area=int(a.sum())
    iou=inter/max(1,union); recall=inter/max(1,area); precision=inter/max(1,int(b.sum()))
    labels,count=label(a); expanded=binary_dilation(b,iterations=2); lost=[]
    for i in range(1,count+1):
        c=labels==i; n=int(c.sum())
        if n>=max(14,area*.004):
            cover=float((c&expanded).sum()/n)
            if cover<.50: lost.append({'area':round(n/area,3),'coverage':round(cover,3)})
    warn=iou<.83 or recall<.90 or bool(lost)
    return {'iou':round(iou,4),'recall':round(recall,4),'precision':round(precision,4),'lost_parts':lost,'warning':bool(warn),'severe':bool(iou<.55 or recall<.65),'score':round(iou-.15*sum(v['area'] for v in lost),4)}

def prefer(best,new):
    # Do not trade away a large amount of visible source to gain overlap.
    return (new['score']>best['score']+.012 or (best['warning'] and not new['warning'] and new['score']>=best['score'])) and new['recall']>=best['recall']-.03 and not (new['severe'] and not best['severe'])
