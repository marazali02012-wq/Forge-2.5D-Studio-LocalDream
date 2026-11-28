"""Make a TRELLIS.2 GLB usable by the Forge mobile gate (geometry only).

TRELLIS.2 (ZeroGPU) writes UV-split vertices and a WebP-textured material.
After welding, the HARD10 bicycle had 2 boundary and 1,158 non-manifold edges
and one zero-length normal (a Khronos error), so it cannot enter the
watertight-only mobile gate. This keeps the geometry, welds coincident
vertices, lets MeshLib split non-manifold edges and fill holes, and writes an
uncolored GLB. The repaired-vs-original surface deviation is reported so the
repair itself is measured, not assumed. Textures stay a later F05 topic.

Usage: python trellis2_repair.py IN.glb OUT.glb
"""
import json
from pathlib import Path
import sys

import numpy as np
import trimesh


def weld(mesh, tolerance):
    keys = np.round(mesh.vertices / tolerance).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    faces = inverse.reshape(-1)[mesh.faces]
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    return trimesh.Trimesh(mesh.vertices[first], faces[keep], process=False)


def edge_stats(mesh):
    edges = np.sort(mesh.edges, axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return {"boundary_edges": int((counts == 1).sum()), "nonmanifold_edges": int((counts > 2).sum())}


def meshlib_repair(mesh):
    from meshlib import mrmeshnumpy, mrmeshpy

    # MeshLib's builder duplicates vertices around non-manifold edges on import.
    ml = mrmeshnumpy.meshFromFacesVerts(np.asarray(mesh.faces, np.int32), np.asarray(mesh.vertices, np.float32))
    mrmeshpy.fixMultipleEdges(ml)
    mrmeshpy.duplicateMultiHoleVertices(ml)
    params = mrmeshpy.FillHoleParams()
    params.metric = mrmeshpy.getUniversalMetric(ml)
    for edge in ml.topology.findHoleRepresentiveEdges():
        mrmeshpy.fillHole(ml, edge, params)
    degeneracy = mrmeshpy.FixMeshDegeneraciesParams()
    scale = float(np.linalg.norm(mesh.extents))
    degeneracy.maxDeviation = 1e-6 * scale
    degeneracy.tinyEdgeLength = 1e-7 * scale
    mrmeshpy.fixMeshDegeneracies(ml, degeneracy)
    ml.pack()
    return trimesh.Trimesh(mrmeshnumpy.getNumpyVerts(ml), mrmeshnumpy.getNumpyFaces(ml.topology), process=False)


def deviation(a, b, samples=200_000):
    from scipy.spatial import cKDTree

    scale = float(np.linalg.norm(a.extents))
    pa, _ = trimesh.sample.sample_surface(a, samples, seed=3)
    pb, _ = trimesh.sample.sample_surface(b, samples, seed=4)
    d = np.r_[cKDTree(pb).query(pa)[0], cKDTree(pa).query(pb)[0]] / scale * 100
    return {"mean_pct": round(float(d.mean()), 5), "p99_pct": round(float(np.quantile(d, .99)), 5),
            "max_pct": round(float(d.max()), 5)}


def main():
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    raw = trimesh.load(source, force="mesh", process=False)
    plain = trimesh.Trimesh(raw.vertices, raw.faces, process=False)
    welded = weld(plain, 1e-6 * float(np.linalg.norm(plain.extents)))
    repaired = meshlib_repair(welded)
    repaired.export(out)
    report = {
        "source_faces": int(len(plain.faces)), "welded": edge_stats(welded),
        "repaired_faces": int(len(repaired.faces)), "repaired": edge_stats(repaired),
        "watertight": bool(repaired.is_watertight), "winding": bool(repaired.is_winding_consistent),
        "components": int(len(repaired.split(only_watertight=False))),
        "repair_vs_source": deviation(plain, repaired),
    }
    out.with_suffix(".repair.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
