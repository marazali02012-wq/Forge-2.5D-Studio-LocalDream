"""TripoSR real CPU inference with xatlas and software EGL texture baking.
Requires upstream-triposr checkout and installed dependencies; no synthetic fallback."""
import os,sys
from pathlib import Path
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE','1')
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
sys.path.insert(0,str(Path(__file__).resolve().parent/'upstream-triposr'))
import torch, numpy as np, trimesh, moderngl
from PIL import Image
from tsr.system import TSR
from tsr.utils import resize_foreground
from tsr.bake_texture import bake_texture
from quality import source_mask, compare, prefer
from color_qa import calibrate
from atlas_qa import pad_generated_atlas, geometry_report
model=None
original=moderngl.create_context
moderngl.create_context=lambda *a,**kw:original(*a,**dict(kw,backend='egl'))
def generate_checked(rgba,texture,resolution=96):
    global model
    if model is None:
        torch.set_num_threads(max(1,min(4,int(os.environ.get("OMP_NUM_THREADS","4")),os.cpu_count() or 1)))
        model=TSR.from_pretrained('stabilityai/TripoSR',config_name='config.yaml',weight_name='model.ckpt').to('cpu').eval()
        model.renderer.set_chunk_size(4096)
    ref=source_mask(rgba)
    attempts=[]; best=None; mesh=None; best_code=None
    # Change input framing as well as extraction. Each alternate is a real AI inference.
    configs=[(0.85,resolution,25),(0.94,max(resolution,128),25),(0.72,max(resolution,128),25)]
    with torch.inference_mode():
        for framing,r,t in configs:
            try:
                a=np.asarray(resize_foreground(rgba,framing),dtype=np.float32)/255
                rgb=a[:,:,:3]*a[:,:,3:]+.5*(1-a[:,:,3:])
                code=model([Image.fromarray(np.uint8(np.clip(rgb,0,1)*255))],device='cpu')
                m=model.extract_mesh(code,False,resolution=r,threshold=t)[0]
                if len(m.faces)<500 or len(m.vertices)<300 or not np.isfinite(m.vertices).all() or min(m.extents)<=.01:
                    raise ValueError('Degenerate generated mesh')
                if m.volume<0:m.invert()
                q=compare(ref,m.vertices[:,[1,2,0]],m.faces)
                q.update(resolution=r,threshold=t,framing=framing)
                attempts.append(q)
                if best is None or prefer(best,q):
                    mesh,best,best_code=m,q,code
                if best is not None and not best['warning']:break
            except Exception as e:
                attempts.append({'resolution':r,'threshold':t,'framing':framing,'error':type(e).__name__})
        if mesh is None:raise ValueError('No valid generated mesh')
        # Extract the single scene from the batch, as required by upstream bake_texture.
        if best_code.ndim!=5 or best_code.shape[0]!=1:raise ValueError('Unexpected scene batch dimensions')
        baked=bake_texture(mesh,model,best_code[0],texture)
    tex=Image.fromarray(np.uint8(np.clip(baked['colors'],0,1)*255)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    vm=baked['vmapping']
    visual=trimesh.visual.texture.TextureVisuals(uv=baked['uvs'],material=trimesh.visual.material.PBRMaterial(baseColorTexture=tex,metallicFactor=0.,roughnessFactor=1.))
    m=trimesh.Trimesh(vertices=mesh.vertices[vm],faces=baked['indices'],vertex_normals=mesh.vertex_normals[vm],visual=visual,process=False)
    # TripoSR native +X front, +Z up -> glTF +Z front, +Y up. Proper rotation (det=+1).
    m.apply_transform(np.array([[0.,1.,0.,0.],[0.,0.,1.,0.],[1.,0.,0.,0.],[0.,0.,0.,1.]]))
    if np.asarray(tex)[:,:,3].max()==0:raise ValueError('Empty texture')
    color={'applied':False,'method':'bounded_global_color_gain','reason':'silhouette_warning'}
    if not best['warning']:
        try: color=calibrate(m,rgba)
        except Exception as e:
            import logging
            logging.exception('Optional color calibration failed; original texture retained')
            color={'applied':False,'method':'bounded_global_color_gain','reason':type(e).__name__}
    padded,atlas=pad_generated_atlas(m.visual.material.baseColorTexture)
    m.visual.material.baseColorTexture=padded
    geometry=geometry_report(mesh)
    return m.export(file_type='glb'),dict(best=best,attempts=attempts,method='front_silhouette_multi_inference',color=color,atlas=atlas,geometry=geometry)

def generate(rgba,texture,resolution=96):
    return generate_checked(rgba,texture,resolution)[0]
