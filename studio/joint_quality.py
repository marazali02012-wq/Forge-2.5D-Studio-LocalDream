"""Experimental GLB-compatible joint-weight refinement; no topology/UV edits."""
import numpy as np


def edge_metrics(rest, posed, faces):
    e=np.unique(np.sort(np.concatenate((faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]])),axis=1),axis=0)
    l=np.linalg.norm(rest[e[:,0]]-rest[e[:,1]],axis=1);ok=l>1e-10
    ratio=np.linalg.norm(posed[e[ok,0]]-posed[e[ok,1]],axis=1)/l[ok]
    def area(v):
        t=v[faces];return np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)
    a=area(rest);valid=a>1e-12; ar=area(posed)[valid]/a[valid]
    if not len(ratio) or not len(ar):raise ValueError('No nondegenerate geometry')
    return {'p95':float(np.quantile(abs(ratio-1),.95)), 'mean':float(np.mean(abs(ratio-1))), 'compression':float(np.mean(np.maximum(1-ratio,0))), 'area_loss':float(np.mean(np.maximum(1-ar,0)))}


def _pose(v, pivot, fraction, axis, angle):
    a=v-pivot; angle=np.deg2rad(angle);c=np.cos(angle);s=np.sin(angle)
    r=a*c+np.cross(axis,a)*s+np.outer(a@axis,axis)*(1-c)+pivot
    return v+(r-v)*fraction[:,None]


def refine_joint_weights(v, faces, pts, names, parents, js, ws):
    """Evaluate local two-bone candidates under isolated bends; retain baseline on regression.

    Intended only for explicit reviewed humanoid guides. No claim of volume correction.
    Four original influence slots are retained; exact-coordinate duplicate weights stay equal.
    """
    v=np.asarray(v,float);faces=np.asarray(faces);pts=np.asarray(pts,float)
    if len(v)>250000 or len(faces)>500000:raise ValueError('Joint QA mesh limit')
    if faces.ndim!=2 or faces.shape[1]!=3 or faces.dtype.kind not in 'iu' or not len(faces) or faces.min()<0 or faces.max()>=len(v):raise ValueError('Invalid triangles')
    if len(v)!=len(js) or js.shape!=ws.shape or js.shape[1]!=4 or not np.isfinite(v).all() or not np.isfinite(ws).all() or np.any(ws<0) or not np.allclose(ws.sum(1),1,atol=1e-6):raise ValueError('Invalid skin')
    outj=js.copy();outw=ws.copy();report=[]
    for i,name in enumerate(names):
        if name not in {s+' '+k for s in ('L','R') for k in ('Elbow','Knee','Shoulder','Hip')}:continue
        par=parents[i];children=[k for k,p in enumerate(parents) if p==i]
        if par<0 or len(children)!=1:continue
        child=children[0];a=pts[i]-pts[par];b=pts[child]-pts[i];la=np.linalg.norm(a);lb=np.linalg.norm(b)
        if min(la,lb)<1e-8:continue
        axis=a/la+b/lb;norm=np.linalg.norm(axis)
        if norm<.6:continue
        axis/=norm;delta=v-pts[i];t=delta@axis;rad=np.linalg.norm(delta-t[:,None]*axis,axis=1)
        length=min(la,lb);region=(abs(t)<=.55*length)&(rad<=.6*length)
        # Preserve the R67 ankle and sole transition explicitly for knee/hip.
        ankles=[names.index(s+' Ankle') for s in ('L','R') if s+' Ankle' in names]
        if ankles:region &= v[:,1]>max(pts[ankles,1])+np.ptp(v[:,1])*.065
        maskp=outj==par;maski=outj==i
        pw=(outw*maskp).sum(1);iw=(outw*maski).sum(1);pair=pw+iw
        # Only redistribute the dominant local pair; do not introduce extra influences.
        region &= (pair>.95)&maskp.any(1)&maski.any(1)
        if not region.any():continue
        local=faces[np.any(region[faces],axis=1)]
        if not len(local):continue
        idx,lf=np.unique(local,return_inverse=True);lf=lf.reshape(-1,3);vr=v[idx];pivot=pts[i]
        descendants={i};stack=[i]
        while stack:
            q=stack.pop();kids=[k for k,p in enumerate(parents) if p==q];descendants.update(kids);stack.extend(kids)
        frac=(outw*np.isin(outj,list(descendants))).sum(1)
        basis=np.eye(3)[np.argmin(abs(axis))];ax=np.cross(axis,basis);ax/=np.linalg.norm(ax)
        ax2=np.cross(axis,ax)
        def score(f):
            vals=[edge_metrics(vr,_pose(vr,pivot,f[idx],rot,angle),lf) for rot in (ax,ax2) for angle in (-90,-45,45,90)]
            return {k:float(np.mean([x[k] for x in vals])) for k in vals[0]}
        base=score(frac);best=base;best_iw=None
        for width in (.05,.1,.15,.2,.35,.5):
            u=np.clip((t/(width*length)+1)*.5,0,1);u=u*u*(3-2*u)
            fade=np.clip((.55*length-abs(t))/(.1*length),0,1);fade=fade*fade*(3-2*fade)
            new_iw=np.where(region,iw+(pair*u-iw)*fade,iw)
            candidate=score(frac+new_iw-iw)
            if candidate['p95']<best['p95']-1e-5 and all(candidate[k]<=base[k]+1e-6 for k in ('mean','compression','area_loss')):
                best=candidate;best_iw=new_iw
        if best_iw is not None:
            for slot in range(4):
                # Zero repeated slots; put the pair in the first matching slot.
                outw[:,slot]=np.where(region&maskp[:,slot],np.where(maskp.argmax(1)==slot,pair-best_iw,0),np.where(region&maski[:,slot],np.where(maski.argmax(1)==slot,best_iw,0),outw[:,slot]))
        report.append({'joint':name,'accepted':best_iw is not None,'before':base,'after':best})
    if not np.allclose(outw.sum(1),1,atol=1e-6) or (outw<0).any():raise ValueError('Refinement invalid')
    return outj,outw,report
