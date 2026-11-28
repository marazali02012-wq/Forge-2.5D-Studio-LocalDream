"""F01 experimental LOD audit for uncolored TripoSG triangle meshes."""
import argparse
import json
from pathlib import Path

import numpy as np
import pymeshfix
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import trimesh

from openmvs_mobile_lod import candidate, distances, topo


def components(mesh):
    edges = mesh.edges_unique
    graph = coo_matrix(
        (np.ones(len(edges), dtype=bool), (edges[:, 0], edges[:, 1])),
        shape=(len(mesh.vertices), len(mesh.vertices)),
    ).tocsr()
    count, labels = connected_components(graph, directed=False)
    groups = labels[mesh.faces[:, 0]]
    sizes = np.bincount(groups, minlength=count)
    for group in np.argsort(-sizes):
        if sizes[group]:
            faces = mesh.faces[groups == group]
            used, indices = np.unique(faces, return_inverse=True)
            yield trimesh.Trimesh(mesh.vertices[used], indices.reshape(-1, 3), process=False)


def clean(mesh):
    return bool(
        not mesh.is_empty
        and mesh.is_watertight
        and mesh.is_winding_consistent
        and np.isfinite(mesh.vertices).all()
        and np.all(mesh.area_faces > 1e-12)
    )


def repair(mesh):
    if clean(mesh):
        return mesh
    fixer = pymeshfix.MeshFix(mesh.vertices, mesh.faces)
    fixer.repair(joincomp=False, remove_smallest_components=False)
    return trimesh.Trimesh(fixer.points, fixer.faces, process=False)


def surface_difference(source, model, scale):
    delta = np.r_[distances(source, model), distances(model, source)] * (100 / scale)
    return float(np.quantile(delta, .99)), float(delta.max())


def preserve_small_part(part, scale):
    fixed = repair(part)
    if clean(fixed):
        return fixed
    if len(part.faces) <= 6:
        raise ValueError("Small component could not be repaired")
    fixed = candidate(part, len(part.faces) - 2, "quadric")
    if (
        not clean(fixed)
        or fixed.euler_number != part.euler_number
        or surface_difference(part, fixed, scale)[1] >= .1
    ):
        raise ValueError("Small component could not be repaired without detail loss")
    return fixed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    if source.is_empty or source.visual.defined or not np.isfinite(source.vertices).all():
        raise ValueError("Expected a finite, uncolored mesh")
    scale = np.linalg.norm(source.extents)
    if scale <= 0 or source.area <= 0:
        raise ValueError("Empty source surface")

    largest, *small = components(source)
    parts = [preserve_small_part(part, scale) for part in small]
    target = 59000 - sum(len(part.faces) for part in parts)
    if target <= 6:
        raise ValueError("Accessories exceed the triangle budget")
    parts.insert(0, repair(candidate(largest, target, "quadric")))

    model = trimesh.util.concatenate(parts)
    if not clean(model):
        raise ValueError("Invalid repaired surface")
    args.output.mkdir(exist_ok=False, mode=0o700)
    scratch_glb = args.output / "candidate.glb"
    model.export(scratch_glb, include_normals=True)
    result = trimesh.load(scratch_glb, force="mesh", process=False)
    if not clean(result):
        raise ValueError("GLB round-trip changed surface validity")

    p99, maximum = surface_difference(source, result, scale)
    topology = topo(result)
    area_change = float(abs(result.area / source.area - 1) * 100)
    report = {
        "source_components": len(small) + 1,
        "triangles": len(result.faces),
        "vertices": len(result.vertices),
        "bytes": scratch_glb.stat().st_size,
        "topology": topology,
        "p99_surface_pct": p99,
        "max_sample_surface_pct": maximum,
        "area_change_pct": area_change,
    }
    accepted = (
        len(result.faces) <= 60000
        and len(result.vertices) <= 30000
        and report["bytes"] <= 8_000_000
        and topology["components"] == report["source_components"]
        and p99 < .1 and maximum < .5 and area_change < 1
    )
    report["geometry_gate_passed"] = accepted
    serialized = json.dumps(report, indent=2)
    (args.output / "report.json").write_text(serialized + "\n")
    print(serialized, flush=True)
    if not accepted:
        raise SystemExit("Candidate is diagnostic only: geometric quality gate rejected it")


if __name__ == "__main__":
    main()
