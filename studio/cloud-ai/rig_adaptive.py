import sys, json, struct, pathlib
import numpy as np, trimesh
from scipy.spatial.transform import Rotation
from scipy.sparse import coo_matrix,diags
NAMES=['root','hips','spine','chest','neck','head','shoulder.L','upperarm.L','forearm.L','hand.L','shoulder.R','upperarm.R','forearm.R','hand.R','thigh.L','shin.L','foot.L','toe.L','thigh.R','shin.R','foot.R','toe.R','weapon','cape.1','cape.2','shield']
PARENT=[-1,0,1,2,3,4,3,6,7,8,3,10,11,12,1,14,15,16,1,18,19,20,13,3,23,9]
def run(src,out):
 out=pathlib.Path(out);out.mkdir(exist_ok=True,parents=True)
 m=trimesh.load(src,force='mesh',process=False);v=np.asarray(m.vertices)[:,[1,2,0]].copy();v-= (v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max();v[:,1]-=v[:,1].min();m.vertices=v;h=v[:,1].max();assert m.is_watertight and h>0
 def loops(y):
  sec=m.section(plane_normal=[0,1,0],plane_origin=[0,y,0]);return [] if sec is None else [a[:-1] for a in sec.discrete if len(a)>12]
 def width(y):
  a=loops(y);return np.ptp(np.concatenate(a)[:,0]) if a else np.inf
 # Estimate independent leg and arm bands from actual cross-sections.
 levels=np.arange(.025,.851,.0125)*h
 sections={float(y):loops(y) for y in levels}
 def side_at(y,s):
  return sorted([a for a in sections[float(y)] if s*np.mean(a[:,0])>.07*h and np.ptp(a[:,0])>.025*h],key=lambda a:abs(np.mean(a[:,0])))
 def central_at(y):
  a=sections[float(y)];return min(a,key=lambda b:abs(b[:,0].mean())) if a else None
 arm_levels=[];leg_levels=[]
 for y in levels:
  l,r=side_at(y,-1),side_at(y,1);c=central_at(y)
  if not l or not r:continue
  central=c is not None and abs(c[:,0].mean())<.055*h
  if y<.40*h and (not central or len(l)>=2 and len(r)>=2):leg_levels.append(y)
  if central or len(l)>=2 and len(r)>=2:arm_levels.append(y)
 assert len(leg_levels)>=3 and len(arm_levels)>=3,'No reliable bilateral limb bands'
 # contiguous arm groups; choose longest, never guess on a fused silhouette.
 groups=[]
 for y in arm_levels:
  if not groups or y-groups[-1][-1]>.014*h:groups.append([])
  groups[-1].append(y)
 arms=max(groups,key=len);assert len(arms)>=4,'Arm separation insufficient'
 arms=np.asarray(arms);legs=np.asarray(leg_levels);legs=legs[legs<=.40*h]
 def at_frac(a,f):return float(a[min(len(a)-1,round((len(a)-1)*f))])
 def central_width(y):
  c=central_at(y);return float(np.ptp(c[:,0])) if c is not None and abs(c[:,0].mean())<.06*h else np.inf
 cand=[]
 for y in levels:
  if not arms[-1]+.035*h<y<.84*h:continue
  w=central_width(y);after=[central_width(q) for q in levels if y+.035*h<q<y+.17*h];before=[central_width(q) for q in levels if y-.13*h<q<y-.025*h]
  after=[x for x in after if np.isfinite(x)];before=[x for x in before if np.isfinite(x)]
  if after and before and w<.9*max(after) and w<.9*max(before):cand.append((w/min(max(after),max(before)),y))
 assert cand,'No reliable neck valley';neck=float(min(cand)[1]);center=central_at(neck).mean(0);cx,_,cz=center
 assert legs[-1]<neck and arms[-1]<neck
 P=np.zeros((26,3));P[0]=[cx,0,cz];hip_y=min(legs[-1]+.035*h,neck*.8);P[1]=[cx,hip_y,cz];P[2]=[cx,hip_y+(neck-hip_y)*.25,cz];P[3]=[cx,hip_y+(neck-hip_y)*.65,cz];P[4]=center;P[5]=[cx,neck+.04*h,cz]
 for sign,arm,leg in [(1,6,14),(-1,10,18)]:
  def limb_at(y,outer):
   a=side_at(y,sign);assert a,'Missing limb section';return (a[-1] if outer else a[0]).mean(0)
  ankle=limb_at(at_frac(legs,.12),False);knee=limb_at(at_frac(legs,.55),False);hip=limb_at(float(legs[-1]),False);hip[1]=hip_y
  hand=limb_at(at_frac(arms,.12),True);elbow=limb_at(at_frac(arms,.50),True);upper=limb_at(at_frac(arms,.95),True);shoulder=upper+(upper-elbow)*.40;shoulder[1]=min(neck-.025*h,shoulder[1]);wrist=hand+(elbow-hand)*.18
  toe=ankle.copy();toe[2]+=.035*h;toe[1]=.025*h
  P[arm:arm+4]=[[cx+sign*abs(shoulder[0]-cx)*.25,shoulder[1],cz],shoulder,elbow,wrist];P[leg:leg+4]=[hip,knee,ankle,toe]
 print('Bands',legs[[0,-1]]/h,arms[[0,-1]]/h,neck/h,flush=True)
 P[22]=P[13]+[0,-.04,0];P[23]=P[3]+[0,0,-.05];P[24]=P[1]+[0,0,-.05];P[25]=P[9]+[0,-.04,0]
 assert np.isfinite(P).all()
 # Distance to bone segments; prevent contralateral and head leakage. Soft transitions only near joints.
 D=np.full((len(v),26),1e6);y=v[:,1]
 for j in range(1,22):
  children=[k for k in range(1,22) if PARENT[k]==j];end=P[children[0]] if children else P[j]+[0,-.025*h,0]
  if j==5:end=np.array([cx,h,cz])
  a=P[j];d=end-a;t=np.clip((v-a)@d/max(d@d,1e-9),0,1);D[:,j]=np.linalg.norm(v-a-t[:,None]*d,axis=1)
  if j in list(range(6,10))+list(range(14,18)):D[v[:,0]<cx-.025*h,j]=1e6
  if j in list(range(10,14))+list(range(18,22)):D[v[:,0]>cx+.025*h,j]=1e6
  if j!=5:D[y>neck+.035*h,j]=1e6
  if j==5:D[y<neck-.03*h,j]=1e6
  if j==4:D[y<neck-.10*h,j]=1e6
  if j in range(1,5):D[y<min(hip_y*.65,.20*h),j]=1e6
  if j in range(14,22):D[y>hip_y+.04*h,j]=1e6
  if j in range(6,14):D[y<arms[0]-.035*h,j]=1e6
 # At most four influences. Smooth weights along connected surface, without crossing disconnected parts.
 W=np.exp(-np.minimum((D-D.min(1)[:,None])/(.024*h),80));W[D>1e5]=0;W/=W.sum(1)[:,None]
 e=m.edges_unique;A=coo_matrix((np.ones(2*len(e)),(np.r_[e[:,0],e[:,1]],np.r_[e[:,1],e[:,0]])),shape=(len(v),len(v))).tocsr();A=diags(1/np.maximum(np.asarray(A.sum(1)).ravel(),1))@A
 # Cross-section-derived torso core. Suppress leg/arm influence on central torso
 # while keeping a soft transition near shoulders and hips.
 corewidth=min(abs(P[14,0]-cx),abs(P[18,0]-cx))*.78
 core=np.clip((corewidth-np.abs(v[:,0]-cx))/(.035*h),0,1)*np.clip((y-hip_y+.03*h)/(.075*h),0,1)*np.clip((neck*.87-y)/(.09*h),0,1)
 limb=list(range(6,22))
 for _ in range(4):
  W=.65*W+.35*(A@W)
  W[:,limb]*=(1-core[:,None]);W/=W.sum(1)[:,None]

 W[y>neck+.035*h]=0;W[y>neck+.035*h,5]=1
 ids=np.argsort(-W,axis=1)[:,:4];wt=np.take_along_axis(W,ids,axis=1);wt/=wt.sum(1)[:,None];wt=wt.astype('f4');ids=np.where(wt>0,ids,0).astype('u2')
 assert np.max(abs(wt.sum(1)-1))<1e-6
 # Real animated GLB, 26 joints, five candidate clips. QA only, not an approved universal auto-rig.
 data=bytearray();views=[];acc=[]
 def add(a,typ,ctype,target=None):
  a=np.ascontiguousarray(a);data.extend(b'\0'*((-len(data))%4));b=len(data);data.extend(a.tobytes());view={'buffer':0,'byteOffset':b,'byteLength':a.nbytes};
  if target:view['target']=target
  views.append(view);r={'bufferView':len(views)-1,'componentType':ctype,'count':len(a),'type':typ}
  if typ=='SCALAR' and ctype==5126 or typ=='VEC3' and target==34962 and len(acc)==0:r.update(min=np.atleast_1d(a.min(0)).tolist(),max=np.atleast_1d(a.max(0)).tolist())
  acc.append(r);return len(acc)-1
 pos=add(v.astype('f4'),'VEC3',5126,34962);normal=add(np.asarray(m.vertex_normals,dtype='f4'),'VEC3',5126,34962);color=add(np.asarray(m.visual.vertex_colors[:,:3],dtype='f4')/255,'VEC3',5126,34962);ji=add(ids,'VEC4',5123,34962);wi=add(wt,'VEC4',5126,34962);idx=add(m.faces.astype('u4').ravel(),'SCALAR',5125,34963)
 nodes=[{'name':name,'translation':(P[j]-(P[PARENT[j]] if j else 0)).tolist()} for j,name in enumerate(NAMES)]
 for j,n in enumerate(nodes):
  child=[k for k in range(26) if PARENT[k]==j]
  if child:n['children']=child
 nodes.append({'name':'AI reconstructed robot','mesh':0,'skin':0});ib=np.tile(np.eye(4),(26,1,1));ib[:,:3,3]=-P;ibm=add(ib.transpose(0,2,1).astype('f4'),'MAT4',5126)
 gltf={'asset':{'version':'2.0','generator':'Forge R70.30 experimental cross-section rig'},'scene':0,'scenes':[{'nodes':[0,26]}],'nodes':nodes,'skins':[{'joints':list(range(26)),'skeleton':0,'inverseBindMatrices':ibm}],'meshes':[{'primitives':[{'attributes':{'POSITION':pos,'NORMAL':normal,'COLOR_0':color,'JOINTS_0':ji,'WEIGHTS_0':wi},'indices':idx,'material':0}]}],'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':.8}}],'animations':[]}
 edges=m.edges_unique;rest=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1);mask=rest>1e-5;reports={};frames={}
 def skin(q,translation=None):
  R=Rotation.from_quat(q).as_matrix();A=np.zeros((26,3,3));T=np.zeros((26,3));
  for j,pa in enumerate(PARENT):
   l=P[j]-(P[pa] if pa>=0 else 0)
   if j==0 and translation is not None:l=l+translation
   A[j]=R[j] if pa<0 else A[pa]@R[j];T[j]=l if pa<0 else T[pa]+A[pa]@l
  return sum(wt[:,k,None]*(np.einsum('nij,nj->ni',A[ids[:,k]],v-P[ids[:,k]])+T[ids[:,k]]) for k in range(4))
 identity=np.tile([0.,0,0,1],(26,1));assert np.max(np.abs(skin(identity)-v))<1e-6
 for clip,dur in [('idle',1.6),('walk',.9),('attack',.8),('hurt',.5),('death',1.4)]:
  t=np.linspace(0,dur,31);qs=[];ts=[];rat=[];moved=[]
  for f in t/dur:
   x=np.sin(f*2*np.pi);pulse=np.sin(f*np.pi);ang=np.zeros((26,3));
   if clip=='idle':ang[5,1]=5*x;ang[3,2]=2*x
   if clip=='walk':
    for k,sign in [(14,1),(18,-1)]:ang[k,0]=sign*18*x;ang[k+1,0]=12*max(0,sign*x);ang[k+2,0]=-5*max(0,sign*x)
    ang[7,0]=-15*x;ang[11,0]=15*x
   if clip=='attack':ang[11,0]=-32*pulse;ang[12,0]=-40*pulse;ang[3,1]=-12*pulse
   if clip=='hurt':ang[3,0]=-12*pulse;ang[5,2]=10*pulse
   if clip=='death':ang[0,0]=-82*f;ang[7,2]=10*f;ang[11,2]=-10*f
   q=Rotation.from_euler('xyz',ang,degrees=True).as_quat();sv=skin(q);tr=np.array([0,-sv[:,1].min(),0]);sv+=tr;qs.append(q);ts.append(tr);r=np.linalg.norm(sv[edges[:,0]]-sv[edges[:,1]],axis=1)[mask]/rest[mask];rat.append(np.quantile(r,.99));moved.append(np.max(np.linalg.norm(sv-v,axis=1)))
   if abs(f-.5)<1e-5 or abs(f-7/30)<1e-5 or f==1:frames[clip+('_mid' if abs(f-.5)<1e-5 else '_peak' if f<1 else '_end')]=sv
  qs=np.asarray(qs,dtype='f4');ti=add(t.astype('f4'),'SCALAR',5126);sam=[];channels=[]
  for j in range(26):
   if np.max(np.abs(qs[:,j]-identity[j]))<1e-7:continue
   sam.append({'input':ti,'output':add(qs[:,j].copy(),'VEC4',5126),'interpolation':'LINEAR'});channels.append({'sampler':len(sam)-1,'target':{'node':j,'path':'rotation'}})
  sam.append({'input':ti,'output':add(np.asarray(ts+P[0],dtype='f4'),'VEC3',5126),'interpolation':'LINEAR'});channels.append({'sampler':len(sam)-1,'target':{'node':0,'path':'translation'}})
  gltf['animations'].append({'name':clip,'samplers':sam,'channels':channels});reports[clip]={'frames':31,'p99_edge_ratio_max':float(max(rat)),'max_motion':float(max(moved)),'accepted':bool(max(rat)<1.5 and max(moved)>.01)}
 gltf.update(bufferViews=views,accessors=acc,buffers=[{'byteLength':len(data)}]);jb=json.dumps(gltf,separators=(',',':')).encode();jb+=b' '*((-len(jb))%4);data.extend(b'\0'*((-len(data))%4));(out/'robot_rig_candidate.glb').write_bytes(struct.pack('<4sII',b'glTF',2,28+len(jb)+len(data))+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',len(data),b'BIN\0')+data)
 report={'experimental':True,'joints':26,'triangles':len(m.faces),'neck_height':float(neck),'joint_positions':dict(zip(NAMES,P.tolist())),'rest_error':float(np.max(np.abs(skin(identity)-v))),'clips':reports,'note':'Adaptive bilateral section prototype, no universal rig or visual approval.'};(out/'report.json').write_text(json.dumps(report,indent=2));np.savez_compressed(out/'poses.npz',vertices=v,faces=m.faces,colors=m.visual.vertex_colors,joints=P,parents=PARENT,**frames);print(json.dumps(report['clips'],indent=2))
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
