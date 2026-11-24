"""Conservative geometry-only T-pose guide. Not learned anatomy recognition."""
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from rig import unpack, accessor

def propose_humanoid(raw):
    j,b=unpack(raw)
    if j.get('skins') or j.get('animations') or j.get('extensionsRequired') or len(j.get('meshes',[]))!=1 or len(j['meshes'][0]['primitives'])!=1: raise ValueError('Single static mesh required')
    if len([n for n in j['nodes'] if 'mesh' in n])!=1 or any(any(k in n for k in ('matrix','translation','rotation','scale')) for n in j['nodes']): raise ValueError('Apply transforms')
    p=j['meshes'][0]['primitives'][0]
    if p.get('targets') or p.get('mode',4)!=4 or 'indices' not in p: raise ValueError('Indexed triangles required')
    v=accessor(j,b,p['attributes']['POSITION']).astype(float); f=accessor(j,b,p['indices']).reshape(-1,3)
    if len(v)>250000 or len(f)>200000 or not np.isfinite(v).all() or f.max()>=len(v): raise ValueError('Geometry limits')
    lo,hi=v.min(0),v.max(0); s=hi-lo
    if min(s)<=1e-6 or not .65<=s[0]/s[1]<=1.35 or not .06<=s[2]/s[1]<=.5: raise ValueError('T-pose proportions required')
    m=trimesh.Trimesh(vertices=v,faces=f,process=True)
    if not m.is_watertight or len(m.split(only_watertight=False))!=1: raise ValueError('One closed connected body required')
    pitch=max(s)/96; vox=m.voxelized(pitch).fill(); a=vox.matrix
    if a.size>101**3: raise ValueError('Voxel limit')
    q=(vox.indices_to_points(np.argwhere(a))-lo)/s
    tree=cKDTree(q*s); rows=[]
    def band(y,w=.022):
        z=q[abs(q[:,1]-y)<=w]
        if len(z)<12: raise ValueError('Missing body slice')
        return z
    def center(z): return np.median(z,axis=0)
    def bounds(z): return np.quantile(z[:,0],[.025,.975])
    torso=band(.57); tl,tr=bounds(torso); mid=(tl+tr)/2; tw=tr-tl
    if not .30<mid<.70 or not .12<tw<.46: raise ValueError('Torso not recognized')
    def core(y):
        z=band(y); z=z[abs(z[:,0]-mid)<tw*.32]; return center(z) if len(z)>=12 else (_ for _ in ()).throw(ValueError('Missing central body'))
    # Find widest horizontal arm slice; reject asymmetry and overly sloping arms.
    levels=np.arange(.63,.84,.015); ranges=[bounds(band(y)) for y in levels]; k=int(np.argmax([r[1]-r[0] for r in ranges])); ay=float(levels[k]); al,ar=ranges[k]
    if mid-al<.32 or ar-mid<.32 or abs((mid-al)-(ar-mid))>.12: raise ValueError('Both extended arms required')
    head=band(.91); hl,hr=bounds(head)
    if hr-hl>tw*1.2 or abs((hl+hr)/2-mid)>.07: raise ValueError('Centered head required')
    def add(name,parent,pos):
        pos=np.asarray(pos,float); d,i=tree.query(pos*s)
        if d>max(s)*.025 or not np.isfinite(pos).all(): raise ValueError('Joint outside body')
        pos=np.clip(q[i],0,1); rows.append({'name':name,'parent':parent,'position':pos.round(6).tolist()});return len(rows)-1
    # Leg gap at two heights, not just an outer silhouette width.
    legcenters={}
    for y in (.12,.25,.35):
        z=band(y,.018); left=z[z[:,0]<mid-.015]; right=z[z[:,0]>mid+.015]
        if min(len(left),len(right))<15 or np.quantile(right[:,0],.05)-np.quantile(left[:,0],.95)<.025 or len(z[abs(z[:,0]-mid)<.015])>len(z)*.03: raise ValueError('Two separate legs required')
        lc,rc=center(left),center(right)
        if abs((mid-lc[0])-(rc[0]-mid))>.08: raise ValueError('Asymmetric legs')
        legcenters[y]=(lc,rc)
    root=add('Pelvis',-1,core(.50)); spine=add('Spine',root,core(.61)); chest=add('Chest',spine,core(ay)); neck=add('Neck',chest,core(.84)); add('Head',neck,core(.94))
    for side,edge in [('L',al),('R',ar)]:
        # L/R refer to model coordinate sides, not camera sides.
        sign=-1 if side=='L' else 1; start=mid+sign*tw*.45; reach=edge-start
        parent=chest
        for name,frac in [('Shoulder',0),('Elbow',.49),('Wrist',.82),('Hand',.96)]:
            x=start+reach*frac; z=q[(abs(q[:,0]-x)<.025)&(abs(q[:,1]-ay)<.065)]
            if len(z)<12: raise ValueError('Missing arm region')
            parent=add(side+' '+name,parent,center(z))
    for i,side in enumerate(('L','R')):
        parent=root
        for name,y in [('Hip',.35),('Knee',.25),('Ankle',.12)]: parent=add(side+' '+name,parent,legcenters[y][i]+np.array([0,.10 if name=='Hip' else 0,0]))
        z=band(.045,.025); z=z[z[:,0]<mid] if i==0 else z[z[:,0]>mid]; parent=add(side+' Foot',parent,center(z))
    for row in rows[1:]:
        if np.linalg.norm((np.array(row['position'])-rows[row['parent']]['position'])*s)<max(s)*.015: raise ValueError('Collapsed joint')
    return {'guide':{'joints':rows,'test_joint':6,'axis':'x','degrees':25},'requires_review':True,'anatomical':False,'method':'geometry_t_pose','joint_count':len(rows)}
