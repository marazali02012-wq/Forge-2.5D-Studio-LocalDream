import os, pathlib, subprocess, sys, json, hashlib, math
import numpy as np
from PIL import Image,ImageDraw
out=pathlib.Path('r70-35-qa');out.mkdir(exist_ok=True)
root=pathlib.Path('studio/cloud-ai/rig_adaptive.py')
results={}
# The inputs are actual prior TripoSR inference outputs; no synthetic 3D substitutes.
for name in ['robot','knight']:
 src=pathlib.Path('inputs')/name/'r70-29-qa/real-generated-raw.glb'
 results[name]={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
 for mode in ['baseline','candidate']:
  dest=out/name/mode
  env=dict(os.environ,FORGE_CONTACT_QA='1' if mode=='candidate' else '0')
  subprocess.run([sys.executable,str(root),str(src),str(dest),'--texture'],env=env,check=True)
  report=json.loads((dest/'report.json').read_text())
  assert all(c['accepted'] for c in report['clips'].values())
  results[name][mode]=report['clips']
  poses=np.load(dest/'poses.npz');faces=poses['faces'];rgb=np.asarray(poses['colors'])[:,:3];v=poses['vertices'];h=np.ptp(v[:,1]);canvas=Image.new('RGB',(800,360),(31,38,49));d=ImageDraw.Draw(canvas)
  # Actual triangle projections of deformed meshes, front and side,
  # same scale/ground line for both candidates.
  for i,key in enumerate(['walk_peak','walk_mid','walk_end']):
   a=poses[key]
   for j,axis in enumerate([0,2]):
    x0=132+i*265;y0=165+j*175;s=125/h
    p=np.stack([a[:,axis]*s+x0,y0-a[:,1]*s],axis=1)
    depth=a[:,2 if axis==0 else 0]
    for fi in np.argsort(depth[faces].mean(1)):
     f=faces[fi];d.polygon([tuple(p[k]) for k in f],fill=tuple(np.rint(rgb[f].mean(0)).astype(int)))
    d.line((i*265+5,y0,(i+1)*265-5,y0),fill=(130,130,130))
    d.text((i*265+7,j*175+2),key+' '+('front' if j==0 else 'side'),fill='white')
  canvas.save(dest/'walk_visual.png')
  (dest/'poses.npz').unlink()
 results[name]['comparison']=results[name]['candidate']['walk'].get('contact_r7035')
 c=results[name]['comparison']
 assert c is not None
 if 'candidates' in c:
  assert len(c['candidates'])==3,'Missing experimental IK candidate'
  for m in [c['baseline']]+c['candidates']:
   assert m['samples']==121
   assert all(math.isfinite(m[k]) and m[k]>=0 for k in ('drift','tilt','gap','floor','strain','motion'))
  assert c['selected'] in range(4)
  if c['selected']:
   actual=c['candidates'][c['selected']-1]
   assert actual['strain']<1.5
   assert actual['motion']>=.70*c['baseline']['motion']
 else:
  assert c['selected']==0 and c.get('reason')
 if c['selected']==0:
  assert (out/name/'baseline'/'robot_rig_candidate.glb').read_bytes()==(out/name/'candidate'/'robot_rig_candidate.glb').read_bytes(),'Fallback must preserve baseline bytes'
(out/'comparison.json').write_text(json.dumps(results,indent=2))
print(json.dumps({k:v['comparison'] for k,v in results.items()},indent=2))
