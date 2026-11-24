"""Generated opaque atlas only: extend valid colors into unused texels; never edit valid pixels."""
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

def pad_generated_atlas(image):
    a=np.array(image.convert('RGBA')); valid=a[:,:,3]==255
    if not valid.any():raise ValueError('No valid baked pixels')
    if np.any((a[:,:,3]!=0)&~valid):raise ValueError('Expected binary bake coverage, not material transparency')
    missing=~valid
    result=a.copy()
    if missing.any():
        idx=distance_transform_edt(missing,return_distances=False,return_indices=True)
        result[missing,:3]=a[idx[0][missing],idx[1][missing],:3]
        result[missing,3]=255
    assert np.array_equal(result[valid],a[valid])
    return Image.fromarray(result),{'filled_pixels':int(missing.sum()),'original_coverage':round(float(valid.mean()),5),'valid_pixels_unchanged':True,'method':'nearest_opaque_atlas_padding'}

def geometry_report(mesh):
    import trimesh
    # Weld a copy solely for measurement; UV seams and original parts stay intact.
    m=trimesh.Trimesh(vertices=np.array(mesh.vertices),faces=np.array(mesh.faces),process=True)
    parts=m.split(only_watertight=False);total=max(float(m.area),1e-12)
    ratios=sorted((float(p.area)/total for p in parts),reverse=True)
    tiny=sum(x<.001 for x in ratios)
    # Detached details may be intentional. Flag the topology, never delete parts.
    closed=bool(m.is_watertight); consistent=bool(m.is_winding_consistent)
    extents=[round(float(x),6) for x in m.extents]
    return {'triangles':len(m.faces),'watertight':closed,'winding_consistent':consistent,'components':len(parts),'small_components':tiny,'small_area_fraction':round(sum(x for x in ratios if x<.001),6),'review_components':len(parts)>1,'review_topology':not closed or not consistent or tiny>=3,'extent_xyz':extents,'largest_area_fraction':round(ratios[0],6) if ratios else 0.,'unseen_surfaces_verified':False}

def topology_rank(g):
    """Compare only artifacts, not semantic correctness or intended part count."""
    return (int(not g['watertight'])+int(not g['winding_consistent']),int(g['small_components']>=3),g['small_components'])

def prefer_candidate(best,new):
    from quality import prefer
    # Front fidelity remains the primary criterion. Break near-ties by topology.
    if abs(new['score']-best['score'])<=.012 and abs(new['recall']-best['recall'])<=.03 and new['severe']==best['severe'] and new['warning']==best['warning']:
        a,b=topology_rank(best['topology']),topology_rank(new['topology'])
        if a!=b:return b<a
    return prefer(best,new)

def early_accept(q):
    return not q['warning'] and not q['topology']['review_topology']
