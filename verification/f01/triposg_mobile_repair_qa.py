"""F01 experimental LOD audit for uncolored TripoSG triangle meshes."""
import argparse
import json
from pathlib import Path

import numpy as np
import pymeshfix
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import trimesh
import vtk

from openmvs_mobile_lod import candidate, distances, poly, topo


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


def repair_diagnostics(source, before, after, scale):
    """Measure the same source vertices before and after topology repair."""
    vertices = np.asarray(source.vertices)
    indices = np.random.default_rng(923).choice(len(vertices), min(10000, len(vertices)), replace=False)

    def directed(mesh):
        locator = vtk.vtkStaticCellLocator()
        locator.SetDataSet(poly(mesh))
        locator.BuildLocator()
        nearest = [0.0, 0.0, 0.0]
        cell, subcell, squared = vtk.reference(0), vtk.reference(0), vtk.reference(0.0)
        values = np.empty(len(indices))
        for i, index in enumerate(indices):
            locator.FindClosestPoint(vertices[index], nearest, cell, subcell, squared)
            values[i] = float(squared) ** .5 * 100 / scale
        return values

    pre = directed(before)
    post = directed(after)
    worst = np.argsort(post)[-8:][::-1]
    return {
        "sampled_source_vertices": len(indices),
        "before_topology": topo(before),
        "before_source_to_candidate_max_pct": float(pre.max()),
        "after_source_to_candidate_max_pct": float(post.max()),
        "over_limit_before": int(np.count_nonzero(pre >= .5)),
        "over_limit_after": int(np.count_nonzero(post >= .5)),
        # Coordinates are local only. Do not publish this diagnostic JSON for a private mesh.
        "worst_post_repair_samples": [{
            "point": vertices[indices[i]].tolist(),
            "before_pct": float(pre[i]),
            "after_pct": float(post[i]),
        } for i in worst],
    }

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


def meshlib_mesh(mesh):
    from meshlib import mrmeshnumpy

    return mrmeshnumpy.meshFromFacesVerts(
        np.asarray(mesh.faces, dtype=np.int32), np.asarray(mesh.vertices, dtype=np.float32)
    )


DECIMATION = {}


def topology_first(part, target):
    """Experimental local intersection repair after topology-aware decimation."""
    from meshlib import mrmeshpy, mrmeshnumpy

    mesh = meshlib_mesh(part)
    mrmeshpy.fixMultipleEdges(mesh)
    mrmeshpy.duplicateMultiHoleVertices(mesh)
    hole_fill = mrmeshpy.FillHoleParams()
    hole_fill.metric = mrmeshpy.getUniversalMetric(mesh)
    for edge in mesh.topology.findHoleRepresentiveEdges():
        mrmeshpy.fillHole(mesh, edge, hole_fill)

    decimation = mrmeshpy.DecimateSettings()
    decimation.maxDeletedFaces = mesh.topology.numValidFaces() - target
    decimation.preventNormalFlips = True
    for key, value in DECIMATION.items():
        setattr(decimation, key, value)
    mrmeshpy.decimateMesh(mesh, decimation)
    mesh.pack()
    return trimesh.Trimesh(
        mrmeshnumpy.getNumpyVerts(mesh), mrmeshnumpy.getNumpyFaces(mesh.topology), process=False
    )


def fix_local_intersections(model):
    from meshlib import mrmeshpy, mrmeshnumpy

    mesh = meshlib_mesh(model)
    settings = mrmeshpy.SelfIntersections.Settings()
    settings.method = mrmeshpy.FixSelfIntersectionMethod.SelfBoolean
    settings.touchIsIntersection = False
    mrmeshpy.SelfIntersections.fix(mesh, settings)
    mesh.pack()
    return trimesh.Trimesh(
        mrmeshnumpy.getNumpyVerts(mesh), mrmeshnumpy.getNumpyFaces(mesh.topology), process=False
    )


def collision_count(model):
    from meshlib import mrmeshpy

    mesh = meshlib_mesh(model)
    if mesh.topology.numValidFaces() != len(model.faces):
        raise ValueError("Triangle count changed during intersection validation")
    return len(mrmeshpy.findSelfCollidingTriangles(mrmeshpy.MeshPart(mesh)))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--diagnose-repair", action="store_true",
        help="Save directed error and local hotspots before/after repair in the private output directory",
    )
    parser.add_argument(
        "--topology-first", action="store_true",
        help="Run the optional MeshLib 3.2.0.75 research candidate and collision gate",
    )
    parser.add_argument("--angle-weighted", action="store_true",
                        help="MeshLib angleWeightedDistToPlane (research; default off)")
    parser.add_argument("--stabilizer", type=float, help="MeshLib stabilizer (default 0.001)")
    parser.add_argument("--max-aspect", type=float, help="MeshLib maxTriangleAspectRatio (default 20)")
    args = parser.parse_args()
    if args.angle_weighted:
        DECIMATION["angleWeightedDistToPlane"] = True
    if args.stabilizer is not None:
        DECIMATION["stabilizer"] = args.stabilizer
    if args.max_aspect is not None:
        DECIMATION["maxTriangleAspectRatio"] = args.max_aspect
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
    if args.topology_first:
        simplified = topology_first(largest, target)
        combined = trimesh.util.concatenate([simplified, *parts])
        before = combined if args.diagnose_repair else None
        model = fix_local_intersections(combined)
    else:
        simplified = candidate(largest, target, "quadric")
        before = trimesh.util.concatenate([simplified, *parts]) if args.diagnose_repair else None
        model = trimesh.util.concatenate([repair(simplified), *parts])
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
    if args.topology_first:
        collisions = collision_count(result)
        report["self_intersection_pairs"] = collisions
        report["method"] = "topology_first_local_self_boolean"
        accepted = accepted and collisions == 0
    report["decimation_overrides"] = DECIMATION
    report["geometry_gate_passed"] = accepted
    serialized = json.dumps(report, indent=2)
    (args.output / "report.json").write_text(serialized + "\n")
    if before is not None:
        diagnostics = repair_diagnostics(source, before, result, scale)
        (args.output / "repair_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(serialized, flush=True)
    if not accepted:
        raise SystemExit("Candidate is diagnostic only: geometric quality gate rejected it")


if __name__ == "__main__":
    main()
