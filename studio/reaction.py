"""Conservative humanoid reactions with skeletal motion and mesh floor correction."""
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from gait import rotation_between
from combat import punch


def reaction(pts, parents, spec, duration, vertices, ids, weights):
    roles=spec['roles']; sign=spec['sign']; kind=spec['kind']
    names=('spine','chest','head','ls','le','lw','rs','re','rw','lh','lk','la','rh','rk','ra')
    if type(sign)!=int or sign not in (-1,1) or kind not in ('hurt','death') or set(roles)!=set(names) or any(type(roles[k])!=int or not 0<roles[k]<len(pts) for k in names) or len(set(roles.values()))!=len(names):raise ValueError('Invalid reaction roles')
    r=roles
    def ancestor(child,parent):
        while child>0:
            child=parents[child]
            if child==parent:return True
        return False
    for a,b in [('spine','chest'),('chest','head'),('chest','ls'),('chest','rs'),('lh','lk'),('lk','la'),('rh','rk'),('rk','ra')]:
        if not ancestor(r[b],r[a]):raise ValueError('Invalid reaction hierarchy')
    if any(not (pts[r[s+'h'],1]>pts[r[s+'k'],1]>pts[r[s+'a'],1]) for s in 'lr') or pts[r['head'],1]<=pts[0,1]:raise ValueError('Y-up standing humanoid required')
    if len(vertices)>200000:raise ValueError('Reaction vertex limit: 200000')
    _,guard=punch(pts,parents,{'roles':{k:r[k] for k in ('ls','le','lw','rs','re','rw')},'sign':sign,'side':'r'},.9)
    guard={i:Rotation.from_quat(q[0]) for i,path,q in guard}
    relaxed={}
    for side,other in [('l','r'),('r','l')]:
        sh,el,wr=[r[side+k] for k in 'sew']; outward=np.sign(pts[sh,0]-pts[r[other+'s'],0]); target=np.array([outward*.16,-1,0.])
        q=rotation_between(pts[el]-pts[sh],target);relaxed[sh]=q;relaxed[el]=q.inv()*rotation_between(pts[wr]-pts[el],target)
    arm_blend={i:Slerp([0,1],Rotation.from_quat([q.as_quat(),relaxed[i].as_quat()])) for i,q in guard.items()}
    # 0, anticipation, peak, settle, end. Death remains down; hurt returns to guard.
    keys=np.array([0,.18,.42,.75,1.])
    if kind=='hurt':
        values=np.array([[0,0,0,0,0],[0,0,0,0,0],[-8,-12,14,8,.035],[-2,-3,3,2,.01],[0,0,0,0,0]])
    else:
        # pelvis pitch, spine pitch, head counter-pitch, knee bend, backward travel (height fraction)
        values=np.array([[0,0,0,0,0],[-8,9,0,18,.015],[-42,8,14,25,.10],[-89,0,2,6,.23],[-90,0,0,0,.24]])
    height=float(np.ptp(vertices[:,1])); floor=float(vertices[:,1].min()); times=np.linspace(0,duration,61,dtype=np.float32)
    selected=sorted(set([0,r['spine'],r['chest'],r['head'],r['lh'],r['rh'],r['lk'],r['rk'],*guard]))
    rotations={i:[] for i in selected}; translations=[]
    # Precompute vertex offsets for all influences, then evaluate exact skinned y per sample.
    offsets=vertices[:,None,:]-pts[ids]; w=weights.astype(float)
    for t in np.linspace(0,1,61):
        k=min(3,np.searchsorted(keys,t,side='right')-1); f=(t-keys[k])/(keys[k+1]-keys[k]);f=f*f*(3-2*f)
        a,b,c,d,z=values[k]*(1-f)+values[k+1]*f
        local={i:Rotation.identity() for i in selected}
        local[0]=Rotation.from_euler('x',sign*a,degrees=True);local[r['spine']]=Rotation.from_euler('x',sign*b,degrees=True);local[r['chest']]=Rotation.from_euler('x',sign*b*.25,degrees=True);local[r['head']]=Rotation.from_euler('x',sign*c,degrees=True)
        for s in 'lr':
            local[r[s+'h']]=Rotation.from_euler('x',sign*(-d*.45),degrees=True);local[r[s+'k']]=Rotation.from_euler('x',sign*d,degrees=True)
        # Keep hands away from the T pose, relax the guard as the body falls.
        relax=(max(0,min(1,(t-.22)/.63)) if kind=='death' else 0)
        for i,q in guard.items():
            local[i]=arm_blend[i](relax*relax*(3-2*relax)) if kind=='death' else q
        world_r=[];world_p=[]
        for i,p in enumerate(parents):
            q=local.get(i,Rotation.identity())
            if p<0:world_r.append(q);world_p.append(pts[i]+[0,0,-sign*z*height])
            else:world_r.append(world_r[p]*q);world_p.append(world_p[p]+world_r[p].apply(pts[i]-pts[p]))
        m=np.array([q.as_matrix()[1] for q in world_r]);p=np.array(world_p)
        yy=np.sum(w*(np.einsum('nki,nki->nk',m[ids],offsets)+p[ids,1]),axis=1)
        # Exact sampled skin-floor contact; no rigid ground collision simulation.
        root=p[0].copy();root[1]+=floor-float(yy.min());translations.append(root)
        for i in selected:rotations[i].append(local[i].as_quat())
    tracks=[]
    for i,q in rotations.items():
        q=np.asarray(q,dtype=np.float32)
        for k in range(1,len(q)):
            if q[k-1]@q[k]<0:q[k]*=-1
        tracks.append((i,'rotation',q))
    tracks.append((0,'translation',np.asarray(translations,dtype=np.float32)))
    return times,tracks
