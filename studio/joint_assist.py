"""Geometric medial-axis assistance, not anatomical detection or automatic binding."""
import copy
import numpy as np
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
import trimesh
from rig import unpack, accessor

def medial_points(raw):
    j,b=unpack(raw)
    if j.get('skins') or j.get('animations') or j.get('extensionsRequired') or len(j.get('meshes',[]))!=1 or len(j['meshes'][0]['primitives'])!=1:raise ValueError('Static mesh required')
    if any(any(k in n for k in ('matrix','translation','rotation','scale')) for n in j['nodes']):raise ValueError('Apply transforms first')
    p=j['meshes'][0]['primitives'][0]
    if p.get('targets') or p.get('mode',4)!=4 or 'indices' not in p:raise ValueError('Indexed triangles required')
    v=accessor(j,b,p['attributes']['POSITION']).astype(float);f=accessor(j,b,p['indices']).reshape(-1,3)
    if len(v)>250000 or len(f)>200000 or not np.isfinite(v).all() or f.max()>=len(v):raise ValueError('Geometry limit')
    m=trimesh.Trimesh(vertices=v,faces=f,process=True)
    # Disconnected accessories are not anatomical limbs. Fail closed rather than snap to them.
    if len(m.split(only_watertight=False))!=1:raise ValueError('Multiple disconnected geometry components; review manually before joint suggestion')
    lo,hi=v.min(0),v.max(0);span=hi-lo
    if min(span)<=1e-6 or not m.is_watertight:raise ValueError('Closed volumetric mesh required')
    pitch=float(max(span)/80);vox=m.voxelized(pitch).fill();a=np.pad(vox.matrix,1)
    if a.size>85**3:raise ValueError('Voxel limit')
    sk=skeletonize(a,method='lee').astype(bool);pts=vox.indices_to_points(np.argwhere(sk)-1)
    if not 2<=len(pts)<=100000:raise ValueError('No usable medial line')
    return lo,hi,pts

def suggest_joints(raw,guide):
    lo,hi,pts=medial_points(raw);span=hi-lo;diag=float(np.linalg.norm(span));rows=guide['joints']
    if not isinstance(rows,list) or not 2<=len(rows)<=64:raise ValueError('Joint count')
    tree=cKDTree(pts);candidate=copy.deepcopy(guide);report=[];names=set()
    for i,r in enumerate(rows):
        name=r['name'];parent=r['parent'];q=np.asarray(r['position'],dtype=float)
        if not isinstance(name,str) or not 1<=len(name)<=48 or name in names or type(parent)!=int or (parent!=-1 if i==0 else not 0<=parent<i) or q.shape!=(3,) or not np.isfinite(q).all() or np.any(q<0) or np.any(q>1):raise ValueError('Invalid guide')
        names.add(name);d,ix=tree.query(lo+q*span);ratio=float(d/diag);target=(pts[ix]-lo)/span
        eligible=bool(.003<=ratio<=.035 and np.all((target>=0)&(target<=1)))
        if eligible:candidate['joints'][i]['position']=target.round(6).tolist()
        report.append({'name':name,'distance_percent':round(ratio*100,3),'suggested':eligible})
    # Do not return a collapsed parent/child link after snapping.
    for i,r in enumerate(candidate['joints'][1:],1):
        if np.linalg.norm((np.array(r['position'])-np.array(candidate['joints'][r['parent']]['position']))*span)<diag*.005:raise ValueError('Suggestion collapses a bone; revise manual guide')
    return {'guide':candidate,'joints':report,'medial_samples':len(pts),'anatomical':False,'requires_review':True}
