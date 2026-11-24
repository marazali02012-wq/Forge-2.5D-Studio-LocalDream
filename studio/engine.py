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
model=None
original=moderngl.create_context
moderngl.create_context=lambda *a,**kw:original(*a,**dict(kw,backend='egl'))
def generate(rgba,texture):
    global model
    if model is None:
        torch.set_num_threads(max(1,min(4,int(os.environ.get("OMP_NUM_THREADS","4")),os.cpu_count() or 1)))
        model=TSR.from_pretrained('stabilityai/TripoSR',config_name='config.yaml',weight_name='model.ckpt').to('cpu').eval()
        model.renderer.set_chunk_size(4096)
    a=np.asarray(resize_foreground(rgba,0.85),dtype=np.float32)/255
    rgb=a[:,:,:3]*a[:,:,3:]+.5*(1-a[:,:,3:])
    with torch.inference_mode():
        code=model([Image.fromarray(np.uint8(rgb*255))],device='cpu')
        mesh=model.extract_mesh(code,False,resolution=96)[0]
        if len(mesh.faces)<500 or len(mesh.vertices)<300 or not np.isfinite(mesh.vertices).all() or min(mesh.extents)<=0.01:raise ValueError('Degenerate generated mesh')
        if mesh.volume<0:mesh.invert()
        baked=bake_texture(mesh,model,code[0],texture)
    tex=Image.fromarray(np.uint8(np.clip(baked['colors'],0,1)*255)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    vm=baked['vmapping']
    visual=trimesh.visual.texture.TextureVisuals(uv=baked['uvs'],material=trimesh.visual.material.PBRMaterial(baseColorTexture=tex,metallicFactor=0.,roughnessFactor=1.))
    m=trimesh.Trimesh(vertices=mesh.vertices[vm],faces=baked['indices'],vertex_normals=mesh.vertex_normals[vm],visual=visual,process=False)
    # TripoSR native +X front, +Z up -> glTF +Z front, +Y up. Proper rotation (det=+1).
    m.apply_transform(np.array([[0.,1.,0.,0.],[0.,0.,1.,0.],[1.,0.,0.,0.],[0.,0.,0.,1.]]))
    return m.export(file_type='glb')
