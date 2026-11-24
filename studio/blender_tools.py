"""Run by Blender headless. Only explicit, bounded mesh operations; no template rig."""
import bpy, sys, os, json
import numpy as np
# Compatibility for Debian Blender 3.x glTF add-on on NumPy 1.24+.
if 'bool' not in np.__dict__: np.bool=np.bool_
from pathlib import Path
src, dest, op, count = sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes:raise RuntimeError('No mesh')
def faces(objects):
    return sum(sum(max(0,len(p.vertices)-2) for p in o.data.polygons) for o in objects)
before=faces(meshes)
if op=='reduce':
    if any(o.type=='ARMATURE' or o.animation_data for o in bpy.context.scene.objects) or any(o.data.shape_keys for o in meshes):raise RuntimeError('Rigged or animated model cannot be reduced safely')
    target=int(count)
    if target<100 or target>250000:raise RuntimeError('Invalid face target')
    if before>target:
        ratio=target/before
        for obj in meshes:
            if len(obj.data.polygons)<4:continue
            bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
            mod=obj.modifiers.new('Forge Decimate','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=max(.001,min(1.,ratio));mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
    after=faces(meshes)
    if after<=0 or after>before or (before>target and after>=before):raise RuntimeError('Reduction failed')
    bpy.ops.export_scene.gltf(filepath=dest,export_format='GLB',export_texcoords=True,export_normals=True,export_materials='EXPORT',export_animations=False)
    print('FORGE_TOPOLOGY '+json.dumps({'before':before,'after':after}),flush=True)
elif op=='fbx':
    bpy.ops.export_scene.fbx(filepath=dest,path_mode='COPY',embed_textures=True,add_leaf_bones=False,bake_anim=True,axis_forward='-Z',axis_up='Y')
else:raise RuntimeError('Unknown operation')
if not Path(dest).is_file() or Path(dest).stat().st_size<100:raise RuntimeError('Empty output')
