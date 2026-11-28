"""F01 HARD10 metrics for real TripoSG outputs: raw topology, mobile LOD gate.

Usage: python hard10_triposg_qa.py OUT_DIR case=raw.glb [case=raw.glb ...]
Writes OUT_DIR/<case>/lod/{candidate.glb,report.json} with the unchanged
mobile gate (<=60k triangles, <=30k vertices, components preserved, p99 <0.1%,
max sampled deviation <0.5%, area change <1%, zero self-intersections) and
OUT_DIR/summary.json. Nothing is substituted when a gate fails.
"""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent


def raw_metrics(path):
    mesh = trimesh.load(path, force="mesh", process=False)
    edges = np.sort(mesh.edges, axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    parts = mesh.split(only_watertight=False)
    return {
        "faces": int(len(mesh.faces)), "vertices": int(len(mesh.vertices)),
        "components": int(len(parts)), "watertight": bool(mesh.is_watertight),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "extents": [round(float(x), 4) for x in mesh.extents],
    }


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for item in sys.argv[2:]:
        case, raw = item.split("=", 1)
        folder = out / case
        folder.mkdir(exist_ok=True)
        row = {"raw": raw_metrics(raw)}
        lod = folder / "lod"
        if lod.exists():
            raise SystemExit(f"{lod} exists; refuse to overwrite evidence")
        run = subprocess.run([sys.executable, str(HERE / "triposg_mobile_repair_qa.py"), raw, str(lod),
                              "--topology-first"], capture_output=True, text=True)
        report = lod / "report.json"
        if run.returncode == 0 and report.exists():
            row["mobile"] = json.loads(report.read_text())
        else:
            row["mobile"] = {"geometry_gate_passed": False,
                             "failure": (run.stderr.strip().splitlines() or ["unknown"])[-1][:300]}
        summary[case] = row
        print(case, json.dumps(row), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
