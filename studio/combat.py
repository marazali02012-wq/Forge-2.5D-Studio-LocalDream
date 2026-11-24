"""Geometry-aware unarmed punch. Rotations are in the rig's local rest axes."""
import numpy as np
from scipy.spatial.transform import Rotation
from gait import rotation_between


def punch(pts, parents, spec, duration):
    r=spec['roles']; sign=spec['sign']; side=spec['side']
    names=('ls','le','lw','rs','re','rw')
    if type(sign)!=int or sign not in (-1,1) or side not in ('l','r') or set(r)!=set(names) or any(type(r[k])!=int or not 0<r[k]<len(pts) for k in names) or len(set(r.values()))!=6:
        raise ValueError('Invalid punch roles')
    for s in 'lr':
        if parents[r[s+'e']]!=r[s+'s'] or parents[r[s+'w']]!=r[s+'e']:raise ValueError('Shoulder-elbow-wrist chain required')
    if (pts[r['ls'],0]-pts[r['rs'],0])*(pts[r['lw'],0]-pts[r['rw'],0])<=0:raise ValueError('Inconsistent arm sides')
    # Ready, wind-up, impact, recovery, ready. Relative to model forward.
    times=np.array([0,.20,.43,.65,1.])
    upper=np.array([[.32,-.90,.30],[.42,-.45,-.55],[.04,-.06,1],[.27,-.55,.48],[.32,-.90,.30]])
    lower=np.array([[.05,-.25,.95],[.12,.64,.65],[.02,-.02,1],[.05,.40,.85],[.05,-.25,.95]])
    guard_u=np.array([.32,-.90,.30]);guard_l=np.array([.05,-.25,.95])
    ts=np.linspace(0,duration,61,dtype=np.float32); rotations={r[k]:[] for k in ('ls','le','rs','re')}
    def smooth(t,values):
        i=min(len(times)-2,np.searchsorted(times,t,side='right')-1);f=(t-times[i])/(times[i+1]-times[i]);f=f*f*(3-2*f)
        return values[i]*(1-f)+values[i+1]*f
    for t in np.linspace(0,1,61):
        for s in 'lr':
            sh,el,wr=[r[s+k] for k in ('s','e','w')];u=pts[el]-pts[sh];v=pts[wr]-pts[el]
            if min(np.linalg.norm(u),np.linalg.norm(v))<1e-8:raise ValueError('Collapsed arm')
            # Use actual model side, not camera or anatomical naming convention.
            outward=np.sign(pts[sh,0]-pts[r['rs' if s=='l' else 'ls'],0]);axes=np.array([outward,1,sign])
            a=(smooth(t,upper) if s==side else guard_u)*axes; b=(smooth(t,lower) if s==side else guard_l)*axes
            q=rotation_between(u,a);world=rotation_between(v,b);local=q.inv()*world
            rotations[sh].append(q.as_quat());rotations[el].append(local.as_quat())
    tracks=[]
    for i,q in rotations.items():
        q=np.asarray(q,dtype=np.float32)
        for k in range(1,len(q)):
            if q[k-1]@q[k]<0:q[k]*=-1
        tracks.append((i,'rotation',q))
    return ts,tracks
