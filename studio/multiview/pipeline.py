"""Calibrated RGBA PNGs -> geometry -> read-only audit -> RGB UV -> GLB."""
import argparse, hashlib, io, json, os, tempfile, time
from pathlib import Path
import numpy as np
from PIL import Image
import trimesh
from multiview_hull import reconstruct
from component_audit import component_evidence
from multiview_texture import texture_mesh
from shared_uv import repack

def read_manifest(path):
    path=Path(path).resolve();root=path.parent
    if path.stat().st_size>65536:raise ValueError('Manifest too large')
    j=json.loads(path.read_text(encoding='utf8'))
    if j.get('schema')!='forge-orthographic-v1':raise ValueError('Calibrated orthographic PNG required')
    rows=j['views']
    if not 3<=len(rows)<=24:raise ValueError('3–24 views required')
    center=np.asarray(j['center'],float);pix=float(j['pixel_size']);extent=float(j['extent'])
    if center.shape!=(3,) or not np.isfinite(center).all() or not np.isfinite([pix,extent]).all() or min(pix,extent)<=0:raise ValueError('Invalid calibration')
    views=[];axes=[];hashes=[];seen=set()
    for r in rows:
        file=(root/r['file']).resolve()
        if not file.is_relative_to(root) or file in seen or file.suffix.lower()!='.png' or file.stat().st_size>8*1024*1024:raise ValueError('Invalid or duplicate local PNG path')
        seen.add(file);data=file.read_bytes()
        with Image.open(io.BytesIO(data)) as im:
            if im.format!='PNG' or im.mode!='RGBA' or not 64<=min(im.size)<=max(im.size)<=768:raise ValueError('RGBA PNG 64–768 px required')
            v=np.array(im)
        if views and v.shape!=views[0].shape:raise ValueError('View sizes differ')
        if not np.all((v[...,3]==0)|(v[...,3]==255)):raise ValueError('Binary alpha required')
        a=np.asarray(r['axes'],float)
        if a.shape!=(2,3) or not np.isfinite(a).all() or not np.allclose(a@a.T,np.eye(2),atol=1e-6):raise ValueError('Invalid orthographic axes')
        views.append(v);axes.append(a);hashes.append(hashlib.sha256(data).hexdigest())
    return np.stack(views),np.stack(axes),center,pix,extent,hashes

def image(m):
    mat=m.visual.material;return np.asarray((getattr(mat,'baseColorTexture',None) or getattr(mat,'image',None)).convert('RGB'))

def run(manifest,output,tile=0):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Output exists; original files preserved')
    if tile not in (0,10,12,14):raise ValueError('Unsupported UV mode')
    t=time.monotonic();views,axes,center,pix,extent,hashes=read_manifest(manifest);masks=(views[...,3]==255).astype(np.uint8)
    mesh=reconstruct(masks,axes,center,pix,extent,n=96);geom_s=time.monotonic()-t
    if len(mesh.faces)>65536:raise ValueError('Mesh exceeds texture budget')
    t1=time.monotonic();audit,parts=component_evidence(mesh,masks,axes,center,pix);audit_s=time.monotonic()-t1;t1=time.monotonic()
    textured,_,bake=texture_mesh(mesh,views,axes,center,pix);bake_s=time.monotonic()-t1;uv=None;t1=time.monotonic()
    if tile:
        candidate,uv=repack(mesh,textured,tile)
        if uv['unsampled_faces']!=0:raise ValueError('Unsampled UV faces; rerun without repack')
        textured=candidate
    uv_s=time.monotonic()-t1
    if not np.allclose(textured.vertices[textured.faces],mesh.vertices[mesh.faces],atol=1e-6,rtol=0):raise ValueError('Geometry changed in UV stage')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.forge-r64-',dir=output.parent) as tmp:
        stage=Path(tmp)/'result';stage.mkdir();file=stage/'model.glb';textured.export(file)
        reload=trimesh.load(file,force='mesh',process=False)
        if len(reload.faces)!=len(mesh.faces) or not np.allclose(reload.vertices[reload.faces],mesh.vertices[mesh.faces],atol=1e-6,rtol=0):raise ValueError('GLB geometry roundtrip failed')
        if not np.allclose(reload.visual.uv,textured.visual.uv,atol=1e-6,rtol=0) or not np.array_equal(image(reload),image(textured)):raise ValueError('GLB UV/texture roundtrip failed')
        report={'scope':'calibrated orthographic multi-view; no AI inference or PBR','views':len(views),'input_sha256':hashes,'grid':96,'triangles':len(mesh.faces),'geometric_vertices':len(mesh.vertices),'uv_vertices':len(reload.vertices),'components':len(parts),'watertight_before_uv':bool(mesh.is_watertight),'removed_components':0,'component_audit':audit,'bake':bake,'uv_repack':uv,'seconds':{'geometry':geom_s,'audit':audit_s,'bake':bake_s,'uv':uv_s,'total':time.monotonic()-t},'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'glb_roundtrip':True}
        (stage/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        if output.exists():raise ValueError('Output exists')
        os.rename(stage,output)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('output');p.add_argument('--tile',type=int,choices=[0,10,12,14],default=0,help='Optional shared UV repack')
    args=p.parse_args();r=run(args.manifest,args.output,args.tile);print(json.dumps({k:v for k,v in r.items() if k not in ('component_audit','input_sha256')},indent=2))
