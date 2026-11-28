"""Import raw GeoSAM2 per-face predictions without modifying the source GLB.
The upstream face-order witness must be captured by its actual mesh loader.
Unknown labels stay unknown. This is interactive part selection, not semantics.
"""
import numpy as np
from surface_selection import Selection, mesh_id

def import_geosam_labels(source_mesh, engine_mesh, raw_labels):
    # Exact face order AND vertices are mandatory; matching counts are insufficient.
    if mesh_id(source_mesh) != mesh_id(engine_mesh):
        raise ValueError("GeoSAM2 source mesh identity or ordering mismatch")
    labels = np.asarray(raw_labels)
    if labels.shape != (len(source_mesh.faces),) or labels.dtype.kind not in "iu":
        raise ValueError("invalid GeoSAM2 label vector")
    if np.any(labels < -1) or np.any(labels > 65535):
        raise ValueError("GeoSAM2 label out of range")
    selected = Selection(source_mesh)
    selected.labels[:] = np.maximum(labels, 0).astype(np.int32)
    return selected
