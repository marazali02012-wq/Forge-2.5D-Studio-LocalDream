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
    # Copy and weld solely for measurement; UV seams in output remain unchanged.
    m=trimesh.Trimesh(vertices=np.array(mesh.vertices),faces=np.array(mesh.faces),process=True)
    parts=m.split(only_watertight=False);total=max(float(m.area),1e-12)
    ratios=sorted((float(p.area)/total for p in parts),reverse=True)
    return {'triangles':len(m.faces),'watertight':bool(m.is_watertight),'winding_consistent':bool(m.is_winding_consistent),'components':len(parts),'small_components':sum(x<.001 for x in ratios),'small_area_fraction':round(sum(x for x in ratios if x<.001),6),'review_components':len(parts)>1}
