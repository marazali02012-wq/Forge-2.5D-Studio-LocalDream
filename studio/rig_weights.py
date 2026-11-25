"""Conservative opposite-leg skin-weight suppression for reviewed humanoid guides."""
import numpy as np

def _smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def protect_legs(distances,vertices,points,names,parents,blend):
    ids={n:i for i,n in enumerate(names)}
    required=[s+' '+n for s in ('L','R') for n in ('Hip','Knee','Ankle','Foot')]
    if any(n not in ids for n in required):raise ValueError('Bilateral leg guide required')
    p=np.asarray(points,dtype=float);v=np.asarray(vertices,dtype=float);h=np.ptp(v,axis=0)[1]
    left=[ids['L '+n] for n in ('Hip','Knee','Ankle','Foot')];right=[ids['R '+n] for n in ('Hip','Knee','Ankle','Foot')]
    for chain in (left,right):
        if any(parents[b]!=a for a,b in zip(chain,chain[1:])) or np.any(np.diff(p[chain,1])>=-h*.008):raise ValueError('Invalid downward leg chain')
    if parents[left[0]]!=parents[right[0]]:raise ValueError('Legs must share pelvis')
    gaps=p[right,0]-p[left,0];sign=np.sign(gaps[0]);gaps*=sign
    if not sign or np.any(gaps<h*.045):raise ValueError('Ambiguous leg separation')
    heights=(p[left,1]+p[right,1])*.5
    if np.any(np.diff(heights)>=0):raise ValueError('Invalid leg levels')
    mids=(p[left,0]+p[right,0])*.5
    mid=np.interp(v[:,1],heights[::-1],mids[::-1]);gap=np.interp(v[:,1],heights[::-1],gaps[::-1]);side=(v[:,0]-mid)*sign/gap
    below=_smooth((min(p[left[0],1],p[right[0],1])-v[:,1])/(h*.12));out=np.array(distances,copy=True)
    for chain,s,direction in ((left,'L',1),(right,'R',-1)):
        limbs=chain+([ids[s+' Toe']] if s+' Toe' in ids else [])
        if len(limbs)>4 and parents[limbs[-1]]!=limbs[-2]:raise ValueError('Invalid toe chain')
        suppress=below*_smooth((side*direction-.06)/.28)
        penalty=-2*blend**2*np.log(np.maximum(1-suppress,1e-12));out[:,limbs]+=penalty[:,None]
        out[np.ix_(suppress>=1-1e-8,limbs)]=np.inf
    if not np.isfinite(out).any(axis=1).all():raise ValueError('No remaining skin influences')
    return out


def protect_foot_contacts(distances,vertices,points,names,parents,blend):
    """Smoothly isolate each sole from shin/pelvis influences in reviewed 26-joint guides.

    A rigid ankle/foot/toe subtree is valid for the current walk (no toe roll).
    Geometry outside the ankle transition is not modified. Existing method unchanged.
    """
    ids={n:i for i,n in enumerate(names)};v=np.asarray(vertices,float);p=np.asarray(points,float)
    h=float(np.ptp(v[:,1]));out=np.array(distances,copy=True)
    if not np.isfinite(h) or h<=1e-6:raise ValueError('Invalid foot height')
    for s,other in (('L','R'),('R','L')):
        try: ankle,foot,toe=[ids[s+' '+k] for k in ('Ankle','Foot','Toe')];op=ids[other+' Ankle']
        except KeyError as e:raise ValueError('26-joint foot chain required') from e
        if parents[foot]!=ankle or parents[toe]!=foot:raise ValueError('Invalid foot chain')
        gap=abs(p[ankle,0]-p[op,0]);mid=(p[ankle,0]+p[op,0])/2
        if gap<h*.045:raise ValueError('Ambiguous feet')
        side=(v[:,0]-mid)*np.sign(p[ankle,0]-p[op,0])/gap
        lateral=_smooth((side-.06)/.28)
        # Full suppression 0.025 body heights below ankle, zero 0.065 above.
        vertical=_smooth((p[ankle,1]+h*.065-v[:,1])/(h*.09))
        strength=lateral*vertical
        rest=[i for i in range(len(p)) if i not in (ankle,foot,toe)]
        penalty=-2*blend**2*np.log(np.maximum(1-strength,1e-12))
        out[:,rest]+=penalty[:,None]
        out[np.ix_(strength>=1-1e-8,rest)]=np.inf
    if not np.isfinite(out).any(axis=1).all():raise ValueError('No remaining foot influences')
    return out
