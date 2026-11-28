"""Conservative multiview F02 face-label propagation using actual SAM2.
Only overlapping visible faces anchor another view; never infer unseen faces.
Not GeoSAM2 itself and not automatic semantic recognition.
"""
import numpy as np
from scipy.ndimage import binary_erosion,distance_transform_edt
from surface_selection import mask_votes

def normalized_masks(masks,scores,shape):
    m=np.asarray(masks);s=np.asarray(scores)
    if m.ndim!=3 or m.shape[1:]!=shape or s.shape!=(len(m),) or not np.isfinite(m).all() or not np.isfinite(s).all():raise ValueError("invalid SAM2 outputs")
    return m>.5,s

def face_observation(ids,mask,count):
    hit,seen=mask_votes(ids,mask,count)
    pos=(seen>=3)&(hit>=.75*seen)
    neg=(seen>=3)&(hit<=.10*seen)
    assert not np.any(pos&neg)
    return pos,neg

def anchor_points(region,n):
    # Erode mixed edge pixels before taking separated prompt points.
    inside=binary_erosion(region,iterations=2)
    if inside.sum()<9:inside=region
    d=distance_transform_edt(inside)
    pts=[]
    for _ in range(n):
        y,x=np.unravel_index(d.argmax(),d.shape)
        if d[y,x]<1:break
        pts.append((int(x),int(y)))
        yy,xx=np.ogrid[:d.shape[0],:d.shape[1]]
        d[(xx-x)**2+(yy-y)**2<=18**2]=0
    return pts

def propagate(predictor,frames,first_mask,nfaces,detail=.75):
    if not .6<=detail<=.95 or len(frames)<2:raise ValueError("invalid propagation")
    ids0=frames[0][0];first_mask=np.asarray(first_mask,bool)&(ids0>=0)
    fixed_pos,fixed_neg=face_observation(ids0,first_mask,nfaces)
    if not fixed_pos.any():raise ValueError("seed mask contains no confident faces")
    # Start each direction at the same front seed, preventing one failed
    # direction from making the other direction inherit its error.
    positive=np.zeros(nfaces,np.int16);negative=positive.copy()
    positive+=fixed_pos;negative+=fixed_neg
    results={0:first_mask};audit=[]
    for seq in (range(1,len(frames)//2+1),range(len(frames)-1,len(frames)//2,-1)):
        p=fixed_pos.copy();n=fixed_neg.copy()
        for i in seq:
            ids,img=frames[i];ok=ids>=0;safe=np.maximum(ids,0)
            pp=ok&p[safe];nn=ok&n[safe]
            if pp.sum()<48:
                audit.append(dict(view=i,accepted=False,reason="insufficient shared positive pixels"));continue
            ps=anchor_points(pp,4);ns=anchor_points(nn,4)
            if not ps:
                audit.append(dict(view=i,accepted=False,reason="no positive anchors"));continue
            predictor.set_image(img)
            masks,scores,_=predictor.predict(point_coords=np.asarray(ps+ns,np.float32),point_labels=np.asarray([1]*len(ps)+[0]*len(ns),np.int32),multimask_output=True)
            masks,scores=normalized_masks(masks,scores,ids.shape)
            candidates=[]
            for k,mask in enumerate(masks):
                mask=mask&ok
                recall=float((mask&pp).sum()/pp.sum())
                spill=float((mask&nn).sum()/max(1,nn.sum()))
                if recall>=.70 and spill<=.12 and mask.any() and all(mask[y,x] for x,y in ps):
                    candidates.append((recall-spill+float(scores[k])*.2,k,mask,recall,spill))
            if not candidates:
                audit.append(dict(view=i,accepted=False,reason="SAM2 mask disagrees with known surface"));continue
            _,k,mask,recall,spill=max(candidates,key=lambda c:c[0])
            a,b=face_observation(ids,mask,nfaces)
            positive+=a;negative+=b;results[i]=mask
            # A conflict is not a confident anchor. Seed is never overwritten.
            p=(p|a)&~(n|b);n=(n|b)&~(p|a)
            p=(p|fixed_pos)&~fixed_neg;n=(n|fixed_neg)&~fixed_pos
            audit.append(dict(view=i,accepted=True,recall=recall,spill=spill,score=float(scores[k]),positive_faces=int(a.sum()),negative_faces=int(b.sum())))
    total=positive+negative
    selected=(positive>=2)&(positive>=detail*np.maximum(total,1))
    selected=(selected|fixed_pos)&~fixed_neg
    assert not np.any(selected&(total==0)) and np.all(selected[fixed_pos]) and not selected[fixed_neg].any()
    return selected,positive,negative,results,audit
