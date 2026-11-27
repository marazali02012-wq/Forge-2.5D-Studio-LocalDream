"""Independent sampling of downloaded GLB animation tracks between keyframes."""
import json, pathlib, struct
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
ev=pathlib.Path('evidence34')
report={}
for f in sorted(ev.glob('*.glb')):
 raw=f.read_bytes(); n=struct.unpack_from('<I',raw,12)[0];j=json.loads(raw[20:20+n]);binary=memoryview(raw)[28+n:]
 if not j.get('skins'):continue
 def arr(k):
  a=j['accessors'][k];v=j['bufferViews'][a['bufferView']]
  dt={5126:'<f4',5123:'<u2'}[a['componentType']]
  cols={'SCALAR':1,'VEC3':3,'VEC4':4}[a['type']]
  return np.frombuffer(binary,dtype=dt,count=a['count']*cols,offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,cols)
 nodes=j['nodes'][:26]; parents={child:i for i,node in enumerate(nodes) for child in node.get('children',[])}
 local=np.array([node['translation'] for node in nodes]);rest=local.copy()
 for k in range(1,26):rest[k]+=rest[parents[k]]
 attrs=j['meshes'][0]['primitives'][0]['attributes']
 pos=arr(attrs['POSITION']);ids=arr(attrs['JOINTS_0']);weights=arr(attrs['WEIGHTS_0'])
 # Atlas seams duplicate positions and influences. They can be sampled once.
 _, idx=np.unique(pos,axis=0,return_index=True);pos=pos[idx];ids=ids[idx];weights=weights[idx]
 offset=pos[:,None,:]-rest[ids]; height=np.ptp(pos[:,1]); output={}
 for anim in j['animations']:
  first=anim['samplers'][0];kt=arr(first['input']).ravel(); t=np.linspace(kt[0],kt[-1],121)
  mat=np.broadcast_to(np.eye(3),(len(t),26,3,3)).copy()
  trans=np.broadcast_to(local,(len(t),26,3)).copy()
  for channel in anim['channels']:
   s=anim['samplers'][channel['sampler']];times=arr(s['input']).ravel();vals=arr(s['output']);k=channel['target']['node']
   if channel['target']['path']=='rotation':mat[:,k]=Slerp(times,Rotation.from_quat(vals))(t).as_matrix()
   else:
    for c in range(3):trans[:,k,c]=np.interp(t,times,vals[:,c])
  for k in range(1,26):
   parent=parents[k]
   trans[:,k]=np.einsum('fij,fj->fi',mat[:,parent],trans[:,k])+trans[:,parent];mat[:,k]=mat[:,parent]@mat[:,k]
  floor=[];motion=[]
  for r,tr in zip(mat,trans):
   pose=((np.einsum('nkij,nkj->nki',r[ids],offset)+tr[ids])*weights[:,:,None]).sum(1)
   floor.append(float(pose[:,1].min()/height))
   motion.append(float(np.linalg.norm(pose-pos,axis=1).max()/height))
  output[anim['name']]={'min_floor_over_height':min(floor),'max_floor_over_height':max(floor),'max_motion_over_height':max(motion),'sampled_frames':len(t)}
 report[f.stem]=output
(ev/'interpolated_poses.json').write_text(json.dumps(report,indent=2))
print(len(report),min(c['min_floor_over_height'] for r in report.values() for c in r.values()),max(c['max_floor_over_height'] for r in report.values() for c in r.values()))
