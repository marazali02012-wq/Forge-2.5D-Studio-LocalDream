"""Two-bone IK gait with a stationary stance target in world coordinates."""
import numpy as np
from scipy.spatial.transform import Rotation

def rotation_between(a,b):
    a=a/np.linalg.norm(a); b=b/np.linalg.norm(b)
    cross=np.cross(a,b); dot=np.clip(a@b,-1,1); s=np.linalg.norm(cross)
    if s<1e-8:
        if dot>0:return Rotation.identity()
        axis=np.cross(a,[1,0,0] if abs(a[0])<.9 else [0,1,0]);return Rotation.from_rotvec(np.pi*axis/np.linalg.norm(axis))
    return Rotation.from_rotvec(cross/s*np.arctan2(s,dot))

def gait(pts,parents,spec,duration):
    roles=spec['roles']; sign=spec['sign']; names=['lh','lk','la','rh','rk','ra','ls','le','rs','re']
    if type(sign)!=int or sign not in (-1,1) or set(roles)!=set(names) or any(type(roles[k])!=int or not 0<roles[k]<len(pts) for k in names) or len(set(roles.values()))!=10:raise ValueError('Invalid gait roles')
    for a,b in [('lh','lk'),('lk','la'),('rh','rk'),('rk','ra'),('ls','le'),('rs','re')]:
        if parents[roles[b]]!=roles[a]:raise ValueError('Invalid gait chain')
    legs=[]
    for side in 'lr':
        h,k,a=[roles[side+x] for x in ['h','k','a']];u=pts[k]-pts[h];v=pts[a]-pts[k];l1,l2=np.linalg.norm(u),np.linalg.norm(v)
        if -u[1]<.85*l1 or -v[1]<.85*l2:raise ValueError('Nearly straight downward legs required')
        legs.append((h,k,a,u,v,l1,l2))
    length=min(x[5]+x[6] for x in legs); travel=.85*length; stance=.6; lift=.13*length; drop=.05*length
    ts=np.linspace(0,duration,61,dtype=np.float32); rotations={i:[] for i in roles.values()};translations=[]; contacts=[]
    forward=np.array([0.,0.,float(sign)])
    for t in np.linspace(0,1,61):
        root=forward*(travel*(t-.5))+np.array([0.,-drop+.004*length*(1-np.cos(4*np.pi*t)),0.]);translations.append(pts[0]+root)
        for side,(h,k,a,u,v,l1,l2) in enumerate(legs):
            phase=(t+side*.5)%1; cyc=np.floor(t+side*.5)-side*.5
            # Each stance foot stays at a fixed world position; swing advances to next stance.
            s=np.clip((phase-stance)/(1-stance),0,1); advance=s*s*(3-2*s)
            target=pts[a]+forward*travel*(cyc+stance/2-.5+advance)+np.array([0.,lift*np.sin(np.pi*s)**2,0.])
            hip=pts[h]+root; d=target-hip; dist=np.linalg.norm(d)
            if not abs(l1-l2)+1e-6<dist<l1+l2-1e-6:raise ValueError('Unreachable foot target')
            axis=d/dist; bend=forward-axis*(forward@axis); bend/=np.linalg.norm(bend)
            along=(l1*l1-l2*l2+dist*dist)/(2*dist); height=np.sqrt(max(0,l1*l1-along*along)); knee=hip+axis*along+bend*height
            rh=rotation_between(u,knee-hip); rk_world=rotation_between(v,target-knee); rk=rh.inv()*rk_world; ra=rk_world.inv()
            for i,r in [(h,rh),(k,rk),(a,ra)]:rotations[i].append(r.as_quat())
            contacts.append((side,float(t),phase<stance,target.tolist()))
        for side in 'lr':
            sh,el=roles[side+'s'],roles[side+'e']; arm=pts[el]-pts[sh]; swing=sign*22*np.cos(2*np.pi*(t+(side=='r')*.5)); horizontal=abs(arm[0])>2*abs(arm[1]); z=-np.sign(arm[0])*75 if horizontal else 0
            rotations[sh].append(Rotation.from_euler('XYZ',[swing,0,z],degrees=True).as_quat());rotations[el].append(Rotation.from_euler('XYZ',[0,(-1 if side=='r' else 1)*(-15) if horizontal else 0,0],degrees=True).as_quat() if horizontal else Rotation.from_euler('X',-sign*15,degrees=True).as_quat())
    tracks=[]
    for i,qs in rotations.items():
        qs=np.array(qs,dtype=np.float32)
        for k in range(1,len(qs)):
            if qs[k-1]@qs[k]<0:qs[k]*=-1
        tracks.append((i,'rotation',qs))
    tracks.append((0,'translation',np.array(translations,dtype=np.float32)))
    return ts,tracks,contacts,travel
