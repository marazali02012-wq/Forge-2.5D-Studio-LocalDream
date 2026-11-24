"""Bounded density extraction retries on the same learned scene; no shape substitution."""
import numpy as np
from quality import compare
from atlas_qa import geometry_report, early_accept, prefer_candidate, topology_rank

DENSITY_RETRIES=(18,32)

def retry_density(model,code,mesh,best,reference,attempts):
    if early_accept(best):return mesh,best
    anchor=best
    for threshold in DENSITY_RETRIES:
        try:
            m=model.extract_mesh(code,False,resolution=anchor['resolution'],threshold=threshold)[0]
            if len(m.faces)<500 or len(m.vertices)<300 or not np.isfinite(m.vertices).all() or min(m.extents)<=.01:
                raise ValueError('Degenerate generated mesh')
            if m.volume<0:m.invert()
            q=compare(reference,m.vertices[:,[1,2,0]],m.faces)
            q.update(resolution=anchor['resolution'],threshold=threshold,framing=anchor['framing'],topology=geometry_report(m),stage='density_retry')
            attempts.append(q)
            # Compare to both the original candidate and current winner. No cumulative fidelity loss.
            if q['recall']>=anchor['recall']-.03 and q['score']>=anchor['score']-.012 and topology_rank(q['topology'])<=topology_rank(best['topology']) and prefer_candidate(best,q):
                mesh,best=m,q
        except Exception as e:
            attempts.append(dict(resolution=anchor['resolution'],threshold=threshold,framing=anchor['framing'],stage='density_retry',error=type(e).__name__))
    return mesh,best

def shape_diagnostics(mesh):
    """Descriptive only: legitimate concave objects need not resemble their convex hull."""
    import trimesh
    m=trimesh.Trimesh(vertices=np.asarray(mesh.vertices),faces=np.asarray(mesh.faces),process=True)
    r=np.linalg.norm(m.vertices-m.bounds.mean(axis=0),axis=1)
    p05,p50,p95=np.quantile(r,[.05,.5,.95])
    hull=float(m.convex_hull.volume)
    return dict(hull_fill=round(abs(float(m.volume))/max(hull,1e-12),5) if m.is_watertight else None,radial_p05_p95=round(float(p05/max(p95,1e-12)),5),radial_spread=round(float((p95-p05)/max(p50,1e-12)),5),descriptive_only=True)
