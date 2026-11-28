"""Validate actual GeoSAM2 raw predictions on its official demo mesh.
Run in a separate CPU environment with the pinned upstream source.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"studio/f02"))
from geosam_adapter import import_geosam_labels
from surface_selection import Selection, mesh_id, render_ids

def main():
    p=argparse.ArgumentParser()
    p.add_argument("upstream",type=Path)
    p.add_argument("source",type=Path)
    p.add_argument("predictions",type=Path)
    p.add_argument("out",type=Path)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(a.upstream.resolve()))
    from utils.inference_utils import load_mesh_with_faces
    before=hashlib.sha256(a.source.read_bytes()).hexdigest()
    original=trimesh.load(a.source,force="mesh",process=False)
    _,engine_mesh=load_mesh_with_faces(str(a.source))
    files=sorted(a.predictions.rglob("segmentation_result_*.npy"))
    if len(files)!=1: raise RuntimeError(f"expected one raw prediction, got {files}")
    labels=np.load(files[0],allow_pickle=False)
    selection=import_geosam_labels(original,engine_mesh,labels)
    selected=int(np.count_nonzero(selection.labels))
    if not 0<selected<len(original.faces): raise RuntimeError("empty or full-mesh result is not a part selection")
    out=a.out/"demo.labels.json"
    selection.save(out,{str(k):f"Part {k}" for k in np.unique(selection.labels) if k})
    restored=Selection(original); restored.load(out)
    assert np.array_equal(restored.labels,selection.labels)
    wrong=original.copy();wrong.faces=wrong.faces[::-1].copy()
    try: import_geosam_labels(original,wrong,labels)
    except ValueError: pass
    else: raise AssertionError("reordered faces accepted")
    try: import_geosam_labels(original,engine_mesh,np.full(len(labels),65536))
    except ValueError: pass
    else: raise AssertionError("out-of-range labels accepted")
    assert hashlib.sha256(a.source.read_bytes()).hexdigest()==before
    # Real triangle-ID views, not a fabricated semantic ground truth.
    sheet=Image.new("RGB",(1536,2160),(29,35,43));draw=ImageDraw.Draw(sheet)
    palette=np.array([[180,180,180],[255,174,64],[69,190,219],[145,110,245]],np.uint8)
    for j,angle in enumerate(range(0,360,30)):
        ids=render_ids(original,angle,size=512); visible=ids>=0
        rgb=np.full((512,512,3),(29,35,43),np.uint8)
        lab=selection.labels[ids[visible]]
        rgb[visible]=palette[np.where(lab==0,0,1+(lab-1)%3)]
        x=j%3*512;y=j//3*540
        sheet.paste(Image.fromarray(rgb),(x,y))
        draw.text((x+8,y+516),f"{angle} deg",fill="white")
    sheet.save(a.out/"demo-12-views.jpg",quality=90)
    report=dict(engine="GeoSAM2 official raw inference",source_sha256=before,mesh_id=mesh_id(original),faces=len(original.faces),selected_faces=selected,unknown_faces=len(original.faces)-selected,labels={str(k):int(v) for k,v in zip(*np.unique(selection.labels,return_counts=True))},source_unchanged=True,reordered_rejected=True,sidecar_roundtrip=True,semantic_ground_truth=False,own_forge_model=False)
    (a.out/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
if __name__=="__main__":main()
