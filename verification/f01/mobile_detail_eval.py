"""F01 mobile LOD detail metric: surface-normal error against the raw model.

Distance gates (p99 < 0.1 %, max < 0.5 %) can pass while creases, faces and
thin plates are smoothed away. This samples the raw surface, finds the
nearest point on each candidate and measures the angle between the raw normal
and the candidate normal, overall and on "feature" areas (raw faces whose
dihedral angle to a neighbour exceeds 20 degrees: edges of blades, armour
plates, hair strands, facial relief). Lower is better.

Usage: python mobile_detail_eval.py RAW.glb CANDIDATE.glb [CANDIDATE.glb ...]
"""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree
import trimesh

SAMPLES = 300_000


def sample(mesh, count, seed):
    points, faces = trimesh.sample.sample_surface(mesh, count, seed=seed)
    return points, mesh.face_normals[faces], faces


def main():
    raw = trimesh.load(sys.argv[1], force="mesh", process=False)
    scale = float(np.linalg.norm(raw.extents))
    angles = raw.face_adjacency_angles
    sharp = np.zeros(len(raw.faces), bool)
    sharp[raw.face_adjacency[angles > np.radians(20)].ravel()] = True
    points, normals, faces = sample(raw, SAMPLES, 7)
    feature = sharp[faces]
    for path in sys.argv[2:]:
        cand = trimesh.load(path, force="mesh", process=False)
        dense, dense_normals, _ = sample(cand, 4 * SAMPLES, 11)
        distance, index = cKDTree(dense).query(points, workers=-1)
        cosine = np.clip(np.einsum("ij,ij->i", normals, dense_normals[index]), -1, 1)
        error = np.degrees(np.arccos(cosine))

        def stats(mask):
            values = error[mask]
            return {"mean_deg": round(float(values.mean()), 3),
                    "p90_deg": round(float(np.quantile(values, .9)), 3),
                    "over_30deg_pct": round(float((values > 30).mean() * 100), 3)}

        print(json.dumps({
            "candidate": path, "triangles": int(len(cand.faces)),
            "feature_sample_pct": round(float(feature.mean() * 100), 2),
            "all": stats(np.ones_like(feature)), "feature": stats(feature),
            "nearest_p99_pct": round(float(np.quantile(distance, .99) / scale * 100), 5),
        }), flush=True)


if __name__ == "__main__":
    main()
