"""Conservative geometric A-pose guide. No learned anatomy recognition."""
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from rig import unpack,accessor


def propose_a_pose(raw,joint_count=21):
    if joint_count not in (21,26):raise ValueError('21 or 26 joints required')
    j,b=unpack(raw)
    if j.get('skins') or j.get('animations') or j.get('extensionsRequired') or len(j.get('meshes',[]))!=1 or len(j['meshes'][0]['primitives'])!=1:raise ValueError('Single static mesh required')
    if len([n for n in j['nodes'] if 'mesh' in n])!=1 or any(any(k in n for k in ('matrix','translation','rotation','scale')) for n in j['nodes']):raise ValueError('Apply transforms')
    p=j['meshes'][0]['primitives'][0]
    if p.get('targets') or p.get('mode',4)!=4 or 'indices' not in p:raise ValueError('Indexed triangles required')
    v=accessor(j,b,p['attributes']['POSITION']).astype(float);f=accessor(j,b,p['indices']).reshape(-1,3)
    if len(v)>250000 or len(f)>200000 or not np.isfinite(v).all() or f.max()>=len(v):raise ValueError('Geometry limits')
    lo,hi=v.min(0),v.max(0);s=hi-lo
    if min(s)<=1e-6 or not .48<=s[0]/s[1]<=1.0 or not .06<=s[2]/s[1]<=.5:raise ValueError('A-pose proportions required')
    m=trimesh.Trimesh(vertices=v,faces=f,process=True)
    if not m.is_watertight or len(m.split(only_watertight=False))!=1:raise ValueError('One closed connected body required')
    pitch=max(s)/96;vox=m.voxelized(pitch).fill()
    if vox.matrix.size>101**3:raise ValueError('Voxel limit')
    q=(vox.indices_to_points(np.argwhere(vox.matrix))-lo)/s;tree=cKDTree(q*s)
    def band(y,w=.018):
        z=q[abs(q[:,1]-y)<=w]
        if len(z)<12:raise ValueError('Missing body slice')
        return z
    def med(z):
        if len(z)<12:raise ValueError('Missing anatomical region')
        return np.median(z,axis=0)
    # At several waist heights an A-pose has three horizontally separated groups.
    samples=[];mids=[];widths=[]
    for y in np.arange(.53,.66,.015):
        z=band(y);xx=np.sort(np.unique(z[:,0]));groups=np.split(xx,np.flatnonzero(np.diff(xx)>pitch/s[0]*1.6)+1)
        if len(groups)!=3:continue
        regions=[z[(z[:,0]>=a.min())&(z[:,0]<=a.max())] for a in groups]
        if min(map(len,regions))<12:continue
        l,c,r=map(med,regions);mid=c[0];width=groups[1].max()-groups[1].min()
        if not .35<mid<.65 or not .10<width<.40 or min(mid-l[0],r[0]-mid)<.16 or abs(mid-l[0]-(r[0]-mid))>.10:continue
        samples.append((l,c,r));mids.append(mid);widths.append(width)
    if len(samples)<4:raise ValueError('Separate downward arms not recognized')
    mid=float(np.median(mids));tw=float(np.median(widths));samples=np.array(samples)
    arms=[]
    for i,sign in ((0,-1),(2,1)):
        x=samples[:,i,0];y=samples[:,i,1];a,c=np.polyfit(x,y,1)
        if not .18<(-sign*a)*s[1]/s[0]<1.6 or np.max(abs(y-(a*x+c)))>.04:raise ValueError('Non-A-pose arm slope')
        arms.append((sign,a,c))
    def central(y):
        z=band(y,.022);return med(z[abs(z[:,0]-mid)<tw*.45])
    def snap(pos):
        d,i=tree.query(np.asarray(pos)*s)
        if d>max(s)*.025:raise ValueError('Joint outside body')
        return np.clip(q[i],0,1).round(6).tolist()
    def arm_point(sign,a,c,x):
        y=a*x+c;z=q[(abs(q[:,0]-x)<.025)&(abs(q[:,1]-y)<.07)]
        return med(z)
    shoulder_x=[mid+sign*tw*.64 for sign,a,c in arms];shoulder_y=[a*x+c for (_,a,c),x in zip(arms,shoulder_x)]
    if not all(.61<y<.81 for y in shoulder_y) or abs(shoulder_y[0]-shoulder_y[1])>.06:raise ValueError('Shoulder level ambiguous')
    ay=float(np.mean(shoulder_y));head=band(.88,.03);hl,hr=np.quantile(head[:,0],[.025,.975])
    if hr-hl>tw*1.85 or abs((hl+hr)/2-mid)>.07:raise ValueError('Centered head required')
    rows=[];ids={}
    def add(name,parent,pos):
        point=snap(pos);pid=-1 if parent is None else ids[parent]
        if pid>=0 and np.linalg.norm((np.asarray(point)-rows[pid]['position'])*s)<max(s)*.012:raise ValueError('Collapsed joint')
        ids[name]=len(rows);rows.append({'name':name,'parent':pid,'position':point})
    add('Pelvis',None,central(.46));add('Spine','Pelvis',central(.55))
    if joint_count==26:add('Upper Spine','Spine',central((.55+ay)*.5))
    add('Chest','Upper Spine' if joint_count==26 else 'Spine',central(ay))
    neck_y=min(.80,ay+.10);add('Neck','Chest',central(neck_y));add('Head','Neck',central(.88))
    for (sign,a,c),x,side in zip(arms,shoulder_x,('L','R')):
        edge=float(np.quantile(q[(q[:,1]>.42)&(q[:,1]<.78),0],.008 if sign<0 else .992));reach=edge-x
        if abs(reach)<.25:raise ValueError('Insufficient arm reach')
        parent='Chest';shoulder=arm_point(sign,a,c,x)
        if joint_count==26:
            add(side+' Clavicle',parent,(np.asarray(rows[ids[parent]]['position'])+shoulder)*.5);parent=side+' Clavicle'
        for name,frac in [('Shoulder',0),('Elbow',.47),('Wrist',.81),('Hand',.96)]:
            key=side+' '+name;add(key,parent,arm_point(sign,a,c,x+reach*frac));parent=key
    # Require a real open leg gap at all three heights.
    centers={}
    for y in (.075,.25,.34):
        z=band(y);l=z[z[:,0]<mid-.012];r=z[z[:,0]>mid+.012]
        if min(len(l),len(r))<15 or np.quantile(r[:,0],.05)-np.quantile(l[:,0],.95)<.022 or len(z[abs(z[:,0]-mid)<.012])>len(z)*.03:raise ValueError('Two separate legs required')
        centers[y]=(med(l),med(r))
    signs=[]
    for i,side in enumerate(('L','R')):
        sign=-1 if i==0 else 1;hip=centers[.34][i].copy();hip[1]=.43
        add(side+' Hip','Pelvis',hip);add(side+' Knee',side+' Hip',centers[.25][i]);add(side+' Ankle',side+' Knee',centers[.075][i]);z=band(.03,.021);z=z[(z[:,0]-mid)*sign>0];foot=med(z);add(side+' Foot',side+' Ankle',foot)
        if joint_count==26:
            ankle=np.asarray(rows[ids[side+' Ankle']]['position']);zl,zh=np.quantile(z[:,2],[.05,.95]);forward=zh-ankle[2];back=ankle[2]-zl
            if max(forward,back)*s[2]<max(s)*.035 or abs(forward-back)*s[2]<max(s)*.012:raise ValueError('Foot direction ambiguous')
            facing=1 if forward>back else -1;signs.append(facing);region=z[z[:,2]>=np.quantile(z[:,2],.88)] if facing==1 else z[z[:,2]<=np.quantile(z[:,2],.12)]
            toe=med(region)
            if (toe[2]-foot[2])*facing*s[2]<max(s)*.015:raise ValueError('Toe not distinct')
            add(side+' Toe',side+' Foot',toe)
    if signs and signs[0]!=signs[1]:raise ValueError('Feet face different directions')
    return {'guide':{'joints':rows,'test_joint':ids['L Elbow'],'axis':'x','degrees':25,**({'weight_method':'bilateral_leg_guard'} if joint_count==26 else {})},'requires_review':True,'anatomical':False,'method':'geometry_a_pose','joint_count':len(rows),'bone_links':len(rows)-1,'facing':signs[0] if signs else None}
