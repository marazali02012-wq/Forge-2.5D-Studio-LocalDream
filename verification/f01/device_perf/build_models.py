"""Rebuild the device-test model files from public evidence GLBs.

Artifacts do not serve .glb, so each model is published as base64 text and
decoded in the page. Usage: python build_models.py name=../evidence/models/x.glb ...
"""
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys

here = Path(__file__).resolve().parent
models = []
for item in sys.argv[1:]:
    name, path = item.split("=", 1)
    raw = Path(path).read_bytes()
    if struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise SystemExit(f"{path} is not a GLB 2.0 file")
    doc = json.loads(raw[20:20 + struct.unpack_from("<I", raw, 12)[0]])
    triangles = sum(doc["accessors"][p["indices"]]["count"] // 3
                    for mesh in doc["meshes"] for p in mesh["primitives"])
    target = here / "models" / (Path(path).name + ".b64.txt")
    target.parent.mkdir(exist_ok=True)
    target.write_text(base64.b64encode(raw).decode())
    models.append({"name": name, "file": f"models/{target.name}", "encoding": "base64",
                   "triangles": triangles, "sha256": hashlib.sha256(raw).hexdigest()})
(here / "models" / "manifest.json").write_text(json.dumps(models, indent=1, ensure_ascii=False))
print(json.dumps(models, ensure_ascii=False))
