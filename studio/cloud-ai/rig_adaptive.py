import sys, json, struct, pathlib, os
import numpy as np, trimesh
from scipy.spatial.transform import Rotation
from scipy.sparse import coo_matrix,diags
NAMES=['root','hips','spine','chest','neck','head','shoulder.L','upperarm.L','forearm.L','hand.L','shoulder.R','upperarm.R','forearm.R','hand.R','thigh.L','shin.L','foot.L','toe.L','thigh.R','shin.R','foot.R','toe.R','weapon','cape.1','cape.2','shield']
PARENT=[-1,0,1,2,3,4,3,6,7,8,3,10,11,12,1,14,15,16,1,18,19,20,13,3,23,9]
def run(src,out,texture=False,save_poses=True):
 out=pathlib.Path(out);out.mkdir(exist_ok=True,parents=True)
 m=trimesh.load(src,force='mesh',process=False);v=np.asarray(m.vertices)[:,[1,2,0]].copy();v-= (v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max();v[:,1]-=v[:,1].min();m.vertices=v;h=v[:,1].max();assert m.is_watertight and h>0
 def loops(y):
  sec=m.section(plane_normal=[0,1,0],plane_origin=[0,y,0]);return [] if sec is None else [a[:-1] for a in sec.discrete if len(a)>12]
 # Estimate independent leg and arm bands from actual cross-sections.
 levels=np.arange(.025,.851,.0125)*h
 sections={float(y):loops(y) for y in levels}
 # Off-center accessories shift the bounding-box midpoint. The broad
 # upper torso/neck sections are a more stable fallback anatomical axis.
 section_axis=0.
 def side_at(y,s):
  return sorted([a for a in sections[float(y)] if s*(np.mean(a[:,0])-section_axis)>.07*h and np.ptp(a[:,0])>.025*h],key=lambda a:abs(np.mean(a[:,0])-section_axis))
 def central_at(y):
  a=sections[float(y)];return min(a,key=lambda b:abs(b[:,0].mean()-section_axis)) if a else None
 def limb_bands():
  arm_levels=[];leg_levels=[]
  for y in levels:
   left,right=side_at(y,-1),side_at(y,1);central_loop=central_at(y)
   if not left or not right:continue
   central=central_loop is not None and abs(central_loop[:,0].mean()-section_axis)<.055*h
   if y<.40*h and (not central or len(left)>=2 and len(right)>=2):leg_levels.append(y)
   if central or len(left)>=2 and len(right)>=2:arm_levels.append(y)
  return arm_levels,leg_levels
 arm_levels,leg_levels=limb_bands()
 recentered=len(leg_levels)<3 or len(arm_levels)<4
 if recentered:
  upper=[max(sections[float(y)],key=lambda a:np.ptp(a[:,0]))[:,0].mean()
         for y in levels if .68*h<y<.82*h and sections[float(y)]]
  if upper:section_axis=float(np.median(upper))
  arm_levels,leg_levels=limb_bands()
 if len(leg_levels)<3 or len(arm_levels)<3:raise ValueError('No reliable bilateral limb bands')
 # contiguous arm groups; choose longest, never guess on a fused silhouette.
 groups=[]
 for y in arm_levels:
  if not groups or y-groups[-1][-1]>.014*h:groups.append([])
  groups[-1].append(y)
 arms=max(groups,key=len);assert len(arms)>=4,'Arm separation insufficient'
 arms=np.asarray(arms);legs=np.asarray(leg_levels);legs=legs[legs<=.40*h]
 def at_frac(a,f):return float(a[min(len(a)-1,round((len(a)-1)*f))])
 def central_width(y):
  c=central_at(y);return float(np.ptp(c[:,0])) if c is not None and abs(c[:,0].mean()-section_axis)<.06*h else np.inf
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
   a=side_at(y,sign);assert a,'Missing limb section';return (max(a,key=lambda loop:np.ptp(loop[:,0])) if outer and recentered else a[-1] if outer else a[0]).mean(0)
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
 for _ in range(20):
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
 colors=np.asarray(m.visual.vertex_colors[:,:3],dtype='f4')/255
 mapping=m.faces.ravel() if texture else np.arange(len(v))
 pos=add(v[mapping].astype('f4'),'VEC3',5126,34962)
 normal=add(np.asarray(m.vertex_normals[mapping],dtype='f4'),'VEC3',5126,34962)
 ji=add(ids[mapping],'VEC4',5123,34962);wi=add(wt[mapping],'VEC4',5126,34962)
 attributes={'POSITION':pos,'NORMAL':normal,'JOINTS_0':ji,'WEIGHTS_0':wi}
 if texture:
  from texture_atlas import bake_faces
  uv,png=bake_faces(m.faces,colors)
  attributes['TEXCOORD_0']=add(uv,'VEC2',5126,34962)
  data.extend(bytes((-len(data))%4))
  image_view=len(views);views.append({'buffer':0,'byteOffset':len(data),'byteLength':len(png)});data.extend(png)
 else:
  attributes['COLOR_0']=add(colors,'VEC3',5126,34962)

 nodes=[{'name':name,'translation':(P[j]-(P[PARENT[j]] if j else 0)).tolist()} for j,name in enumerate(NAMES)]
 for j,n in enumerate(nodes):
  child=[k for k in range(26) if PARENT[k]==j]
  if child:n['children']=child
 nodes.append({'name':'AI character','mesh':0,'skin':0});ib=np.tile(np.eye(4),(26,1,1));ib[:,:3,3]=-P;ibm=add(ib.transpose(0,2,1).astype('f4'),'MAT4',5126)
 gltf={'asset':{'version':'2.0','generator':'Forge R70.34 adaptive rig'},'scene':0,'scenes':[{'nodes':[0,26]}],'nodes':nodes,'skins':[{'joints':list(range(26)),'skeleton':0,'inverseBindMatrices':ibm}],'meshes':[{'primitives':[{'attributes':attributes,'material':0}]}],'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':.8}}],'animations':[]}
 if texture:
  gltf.update(images=[{'bufferView':image_view,'mimeType':'image/png'}],textures=[{'source':0,'sampler':0}],samplers=[{'magFilter':9729,'minFilter':9729,'wrapS':33071,'wrapT':33071}])
  gltf['materials'][0]['pbrMetallicRoughness']['baseColorTexture']={'index':0}
 else:
  gltf['meshes'][0]['primitives'][0]['indices']=add(m.faces.astype('u4').ravel(),'SCALAR',5125,34963)
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
  t=np.linspace(0,dur,31);qs=[];ts=[];rat=[];moved=[];floor=[];sole_traces=[];contact_error=[]
  soles=[np.flatnonzero((y<.06*h)&(side*(v[:,0]-cx)>0)) for side in (-1,1)]
  def pose_angles(f):
   x=np.sin(f*2*np.pi);pulse=np.sin(f*np.pi);ang=np.zeros((26,3));
   if clip=='idle':ang[5,1]=5*x;ang[3,2]=2*x
   if clip=='walk':
    for k,sign in [(14,1),(18,-1)]:ang[k,0]=sign*18*x;ang[k+1,0]=12*max(0,sign*x);ang[k+2,0]=-5*max(0,sign*x)
    ang[7,0]=-15*x;ang[11,0]=15*x
   if clip=='attack':
    # Share the strike across the chest, shoulder and elbow. A large
    # isolated elbow bend pulls fused sleeves and props across the seam.
    ang[3,1]=-9*pulse;ang[11,0]=-26*pulse
    ang[12,0]=-20*pulse;ang[13,2]=-7*pulse
   if clip=='hurt':ang[3,0]=-12*pulse;ang[5,2]=10*pulse
   if clip=='death':ang[0,0]=-82*f;ang[7,2]=10*f;ang[11,2]=-10*f
   return ang
  # Fused armor may stretch at full range. Preserve at least 70% of the clip;
  # retain the full 31-frame rejection gate for every selected amplitude.
  gain=1.
  if clip in ('walk','attack'):
   for gain in (1.,.85,.70):
    strain=[]
    for phase in ((.25,.75) if clip=='walk' else (.5,)):
     peak=skin(Rotation.from_euler('xyz',pose_angles(phase)*gain,degrees=True).as_quat())
     lengths=np.linalg.norm(peak[edges[:,0]]-peak[edges[:,1]],axis=1)
     strain.append(np.quantile(lengths[mask]/rest[mask],.99))
    if max(strain)<1.5:break
  # Experimental R70.35: compare actual skinned plantar surface, not
  # the algebraic offset that was used to place it.
  contact_report=None;selected_contact=None
  if clip=='walk' and os.getenv('FORGE_CONTACT_QA')=='1':
   from scipy.spatial.transform import Slerp
   # Use each foot's own lower 30% of the vertices in the original
   # low band; exclude unweighted nearby accessories.
   feet=[]
   for side,chain in [(-1,[20,21]),(1,[16,17])]:
    influence=np.sum(wt*np.isin(ids,chain),axis=1)
    cand=np.flatnonzero((side*(v[:,0]-cx)>0)&(y<.09*h)&(influence>.45))
    feet.append(cand[y[cand]<=np.quantile(y[cand],.30)] if len(cand)>=12 else np.array([],dtype=int))
   if all(len(a)>=8 for a in feet):
    # R70.35 IK candidate: solve the hip/knee/ankle triangle while
    # retaining the existing global foot orientation. Only lower the
    # support ankle by the measured plantar gap; preserve bone lengths.
    def rotate_between(a,b):
     a=a/np.linalg.norm(a);b=b/np.linalg.norm(b)
     axis=np.cross(a,b);length=np.linalg.norm(axis);dot=np.clip(a@b,-1.,1.)
     if length<1e-8:
      if dot>0:return np.eye(3)
      basis=np.eye(3)[np.argmin(abs(a))]
      axis=np.cross(a,basis);axis/=np.linalg.norm(axis)
      return Rotation.from_rotvec(axis*np.pi).as_matrix()
     return Rotation.from_rotvec(axis/length*np.arctan2(length,dot)).as_matrix()
    def lower_ankle(q,k,amount):
     if amount<1e-7:return q
     R=Rotation.from_quat(q).as_matrix()
     u=P[k+1]-P[k];w=P[k+2]-P[k+1]
     a,b=np.linalg.norm(u),np.linalg.norm(w)
     if min(a,b)<1e-7:return q
     thigh=R[k];shin=thigh@R[k+1];foot=shin@R[k+2]
     knee=thigh@u;ankle=knee+shin@w
     target=ankle-np.array([0.,amount,0.]);distance=np.linalg.norm(target)
     if distance<1e-8:return q
     direction=target/distance
     d=np.clip(distance,abs(a-b)+1e-7,a+b-1e-7)
     along=(a*a-b*b+d*d)/(2*d)
     bend=knee-direction*(knee@direction)
     if np.linalg.norm(bend)<1e-7:
      basis=np.eye(3)[np.argmin(abs(direction))]
      bend=basis-direction*(basis@direction)
     bend/=np.linalg.norm(bend)
     new_knee=along*direction+np.sqrt(max(0.,a*a-along*along))*bend
     new_ankle=d*direction
     new_thigh=rotate_between(knee,new_knee)@thigh
     new_shin=rotate_between(shin@w,new_ankle-new_knee)@shin
     res=q.copy()
     res[k]=Rotation.from_matrix(new_thigh).as_quat()
     res[k+1]=Rotation.from_matrix(new_thigh.T@new_shin).as_quat()
     res[k+2]=Rotation.from_matrix(new_shin.T@foot).as_quat()
     return res
    def build(mode):
     keys=[];offsets=[]
     for f in t/dur:
      phase=np.sin(f*2*np.pi);ang=pose_angles(f)*gain
      # The extended leg is the support leg. Compensate ankle pitch
      # against its hip/knee flexion; try full and blended compensation.
      stance=0 if phase>=0 else 1
      if mode:
       for side,k in [(0,18),(1,14)]:
        factor=(1. if side==stance else .35) if mode==1 else 1.
        ang[k+2,0]=-(ang[k,0]+ang[k+1,0])*factor
      q=Rotation.from_euler('xyz',ang,degrees=True).as_quat();sv=skin(q)
      if mode>=3:
       # Two bounded IK iterations; fade out at stance exchange.
       # Skinning, rather than the ankle position alone, sets the gap.
       strength={3:1.,4:.25,5:.50,6:.75}[mode]
       blend=min(abs(phase)*2,1.)*strength
       for _ in range(2):
        gap=max(0.,float(sv[feet[stance],1].min()-sv[:,1].min()))
        q=lower_ankle(q,18 if stance==0 else 14,min(gap,.04*h)*blend)
        sv=skin(q)
      tr=np.array([0.,-sv[:,1].min(),0.])
      if mode==0:
       old_stance=1 if phase>=0 else 0
       sole=soles[old_stance]
      else:sole=feet[stance]
      if len(sole):
       delta=(v[sole]-sv[sole]).mean(0)
       tr[[0,2]]=delta[[0,2]]*min(abs(phase)*4,1.)
      keys.append(q);offsets.append(tr)
     return np.asarray(keys),np.asarray(offsets)
    def evaluate(key,offset):
     sample=np.linspace(0,dur,121)
     interp=np.stack([Slerp(t,Rotation.from_quat(key[:,j]))(sample).as_quat() for j in range(26)],axis=1)
     trans=np.stack([np.interp(sample,t,offset[:,k]) for k in range(3)],axis=1)
     drift=[];tilt=[];gaps=[];strains=[];motions=[];floor_errors=[]
     for f,q,tr in zip(sample/dur,interp,trans):
      sv=skin(q)+tr
      phase=np.sin(f*2*np.pi);stance=0 if phase>=0 else 1
      if abs(phase)>=.5:
       sole=feet[stance];delta=sv[sole]-v[sole]
       drift.append(np.linalg.norm(delta.mean(0)[[0,2]])/h)
       tilt.append(np.std(delta[:,1])/h)
       gaps.append(max(0.,float(np.min(sv[sole,1])))/h)
      floor_errors.append(abs(float(sv[:,1].min()))/h)
      lengths=np.linalg.norm(sv[edges[:,0]]-sv[edges[:,1]],axis=1)
      strains.append(float(np.quantile(lengths[mask]/rest[mask],.99)))
      motions.append(float(np.max(np.linalg.norm(sv-v,axis=1))/h))
     return dict(samples=121,drift=float(np.mean(drift)),tilt=float(np.mean(tilt)),gap=float(np.mean(gaps)),floor=max(floor_errors),strain=max(strains),motion=max(motions))
    variants=[build(i) for i in range(7)]
    metrics=[evaluate(*item) for item in variants];base=metrics[0]
    score=lambda m:m['drift']+m['tilt']+m['gap']
    allowed=[i for i in (1,2) if metrics[i]['strain']<1.5 and metrics[i]['motion']>=.70*base['motion'] and metrics[i]['floor']<=max(.006,base['floor']*1.10) and metrics[i]['gap']<=base['gap']+.001 and metrics[i]['tilt']<=base['tilt']+.001 and score(metrics[i])<.85*score(base)]
    chosen=min(allowed,key=lambda i:score(metrics[i])) if allowed else 0
    # IK must improve the actual support gap, without weakening the
    # selected R70.35 candidate beyond explicit relative tolerances.
    ik=metrics[3];reference=metrics[chosen]
    if (ik['strain']<1.5 and ik['strain']<=reference['strain']*1.03
        and ik['motion']>=.95*reference['motion']
        and ik['floor']<=max(.001,reference['floor']*1.10)
        and ik['drift']<=reference['drift']+.0001
        and ik['tilt']<=reference['tilt']+.0005
        and ik['gap']<.85*reference['gap']
        and score(ik)<score(reference)):
     chosen=3
    # Keep the previously accepted full-strength result as a hard
    # reference; partial IK cannot replace it merely by reducing motion.
    reference=metrics[chosen]
    partial=[i for i in (4,5,6) if metrics[i]['strain']<1.5
        and metrics[i]['strain']<=reference['strain']*1.03
        and metrics[i]['motion']>=.95*reference['motion']
        and metrics[i]['floor']<=max(.001,reference['floor']*1.10)
        and metrics[i]['drift']<=reference['drift']+.0001
        and metrics[i]['tilt']<=reference['tilt']+.0005
        and metrics[i]['gap']<.85*reference['gap']
        and score(metrics[i])<score(reference)]
    previous=chosen
    if partial:chosen=min(partial,key=lambda i:score(metrics[i]))
    selected_contact=variants[chosen] if chosen else None
    contact_report={'selected':chosen,'previous_selected':previous,'baseline':base,'candidates':metrics[1:],'ik_strengths':[1.,.25,.50,.75],'foot_vertices':[len(a) for a in feet]}
   else:contact_report={'selected':0,'reason':'insufficient reliable plantar vertices'}
  for frame_index,f in enumerate(t/dur):
   ang=pose_angles(f)*gain
   q=Rotation.from_euler('xyz',ang,degrees=True).as_quat();sv=skin(q)
   tr=np.array([0,-sv[:,1].min(),0])
   if clip=='walk' and all(len(sole) for sole in soles):
    # Anchor the stance sole in the ground plane. Blend near exchange to
    # avoid snapping the pelvis between two competing contact constraints.
    phase=np.sin(f*2*np.pi)
    stance=1 if phase>=0 else 0
    sole=soles[stance]
    offset=(v[sole]-sv[sole]).mean(0)
    blend=min(abs(phase)*4,1.)
    tr[[0,2]]=offset[[0,2]]*blend
    if blend==1.:contact_error.append(float(np.linalg.norm((offset-tr)[[0,2]])/h))
   if selected_contact is not None:
    q=selected_contact[0][frame_index];tr=selected_contact[1][frame_index];sv=skin(q)
   sv+=tr;qs.append(q);ts.append(tr);r=np.linalg.norm(sv[edges[:,0]]-sv[edges[:,1]],axis=1)[mask]/rest[mask];rat.append(np.quantile(r,.99));moved.append(np.max(np.linalg.norm(sv-v,axis=1)))
   floor.append(float(sv[:,1].min()));sole_traces.append([sv[sole].mean(0) if len(sole) else [np.nan]*3 for sole in soles])
   if abs(f-.5)<1e-5 or abs(f-7/30)<1e-5 or f==1:frames[clip+('_mid' if abs(f-.5)<1e-5 else '_peak' if f<1 else '_end')]=sv
   if save_poses and clip=='walk' and os.getenv('FORGE_WALK_VISUAL_QA')=='1' and frame_index%3==0:frames[f'walk_frame_{frame_index:02d}']=sv.copy()
  qs=np.asarray(qs,dtype='f4');ti=add(t.astype('f4'),'SCALAR',5126);sam=[];channels=[]
  for j in range(26):
   if np.max(np.abs(qs[:,j]-identity[j]))<1e-7:continue
   sam.append({'input':ti,'output':add(qs[:,j].copy(),'VEC4',5126),'interpolation':'LINEAR'});channels.append({'sampler':len(sam)-1,'target':{'node':j,'path':'rotation'}})
  sam.append({'input':ti,'output':add(np.asarray(ts+P[0],dtype='f4'),'VEC3',5126),'interpolation':'LINEAR'});channels.append({'sampler':len(sam)-1,'target':{'node':0,'path':'translation'}})
  gltf['animations'].append({'name':clip,'samplers':sam,'channels':channels});reports[clip]={'amplitude':gain,'frames':31,'p99_edge_ratio_max':float(max(rat)),'max_motion':float(max(moved)),'accepted':bool(max(rat)<1.5 and max(moved)>.01)}
  if contact_report is not None:reports[clip]['contact_r7035']=contact_report
  reports[clip]['max_floor_error']=max(abs(value) for value in floor)
  if clip=='walk' and all(len(sole) for sole in soles) and selected_contact is None:
   reports[clip]['stance_horizontal_error_over_height']=max(contact_error,default=None)
   traces=np.asarray(sole_traces);reports[clip]['sole_horizontal_excursion_over_height']=[float(np.linalg.norm(np.ptp(traces[:,i][:,[0,2]],axis=0))/h) for i in (0,1)]
 gltf.update(bufferViews=views,accessors=acc,buffers=[{'byteLength':len(data)}]);jb=json.dumps(gltf,separators=(',',':')).encode();jb+=b' '*((-len(jb))%4);data.extend(b'\0'*((-len(data))%4));(out/'robot_rig_candidate.glb').write_bytes(struct.pack('<4sII',b'glTF',2,28+len(jb)+len(data))+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',len(data),b'BIN\0')+data)
 report={'experimental':True,'recentered':recentered,'joints':26,'triangles':len(m.faces),'neck_height':float(neck),'joint_positions':dict(zip(NAMES,P.tolist())),'rest_error':float(np.max(np.abs(skin(identity)-v))),'clips':reports,'note':'Adaptive bilateral section prototype, no universal rig or visual approval.'};(out/'report.json').write_text(json.dumps(report,indent=2))
 if save_poses:np.savez_compressed(out/'poses.npz',vertices=v,faces=m.faces,colors=m.visual.vertex_colors,joints=P,parents=PARENT,**frames)
 print(json.dumps(report['clips'],indent=2))
if __name__=='__main__':run(sys.argv[1],sys.argv[2],texture='--texture' in sys.argv[3:],save_poses='--no-poses' not in sys.argv[3:])
