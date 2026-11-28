"""Camera-only world alignment; user chooses which image edge is up."""
import numpy as np

def alignment(rotations,centers,image_up):
    r=np.asarray(rotations,dtype=float);c=np.asarray(centers,dtype=float)
    if r.ndim!=3 or r.shape[1:]!=(3,3) or c.shape!=(len(r),3) or len(r)<6 or not np.isfinite(r).all() or not np.isfinite(c).all():raise ValueError('invalid camera poses')
    if not np.allclose(r@r.transpose(0,2,1),np.eye(3),atol=.003) or not np.allclose(np.linalg.det(r),1,atol=.003):raise ValueError('invalid rotations')
    axes={'top':-r[:,1], 'right':r[:,0], 'bottom':r[:,1], 'left':-r[:,0]}
    u=axes[image_up];mean=u.mean(0);agreement=np.linalg.norm(mean)
    if agreement<.80:raise ValueError('camera up directions do not agree; retain original orientation')
    up=mean/agreement
    _,sv,vt=np.linalg.svd(c-c.mean(0),full_matrices=False)
    planar=float(sv[-1]/max(sv[1],1e-12));n=vt[-1]
    if planar<.025 and abs(n@up)>.95:up=n*np.sign(n@up)
    forward=c[0]-c.mean(0);forward-=up*(forward@up)
    if np.linalg.norm(forward)<1e-8:raise ValueError('ambiguous forward direction')
    forward/=np.linalg.norm(forward);right=np.cross(up,forward);right/=np.linalg.norm(right)
    transform=np.eye(4);transform[:3,:3]=np.stack([right,up,forward]);assert np.isclose(np.linalg.det(transform[:3,:3]),1)
    return transform,{'image_up':image_up,'camera_up_agreement':float(agreement),'camera_ring_planarity':planar,'up_world':up.tolist()}
