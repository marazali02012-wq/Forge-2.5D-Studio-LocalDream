"""Conservative separated accessory proposal, exact-coordinate seam connectivity.
No semantic recognition; explicit review and rigid attachment, never delete parts.
"""
import hashlib
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def geometry_components(v, f):
    v=np.asarray(v); f=np.asarray(f)
    if v.ndim!=2 or v.shape[1]!=3 or not 3<=len(v)<=250000 or not np.isfinite(v).all() or f.ndim!=2 or f.shape[1]!=3 or not 1<=len(f)<=200000 or f.dtype.kind not in 'iu' or f.min()<0 or f.max()>=len(v):
        raise ValueError('Component geometry limits')
    unique, inv=np.unique(v,axis=0,return_inverse=True); wf=inv[f]
    tri=v[f]; areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
    if np.any(areas<=0):raise ValueError('Degenerate triangles')
    edges=np.concatenate((wf[:,[0,1]],wf[:,[1,2]],wf[:,[2,0]]))
    graph=coo_matrix((np.ones(len(edges),np.uint8),(edges[:,0],edges[:,1])),shape=(len(unique),len(unique))).tocsr()
    count, labels=connected_components(graph,directed=False)
    if count>128:raise ValueError('Too many components')
    fl=labels[wf[:,0]]; area=np.bincount(fl,weights=areas,minlength=count)
    if np.any(area<=0):raise ValueError('Unused geometry vertex')
    order=np.argsort(-area,kind='stable'); rank=np.empty(count,int);rank[order]=np.arange(count)
    return rank[labels[inv]],rank[fl],area[order]/area.sum()


def _geometry(raw):
    from rig import unpack,accessor
    j,b=unpack(raw)
    if j.get('skins') or j.get('animations') or j.get('extensionsRequired') or len(j.get('meshes',[]))!=1 or len(j['meshes'][0]['primitives'])!=1:raise ValueError('Static mesh required')
    if len([n for n in j['nodes'] if 'mesh' in n])!=1 or any(any(k in n for k in ('matrix','translation','rotation','scale')) for n in j['nodes']):raise ValueError('Apply transforms')
    p=j['meshes'][0]['primitives'][0]
    if p.get('targets') or p.get('mode',4)!=4 or 'indices' not in p:raise ValueError('Indexed triangles required')
    return accessor(j,b,p['attributes']['POSITION']).astype(float),accessor(j,b,p['indices']).reshape(-1,3)


def propose_accessories(raw,joint_count):
    import trimesh
    from auto_rig import _propose_t_pose
    from auto_rig_a import propose_a_pose
    v,f=_geometry(raw); labels,fl,areas=geometry_components(v,f)
    if not 2<=len(areas)<=9 or areas[0]<.95 or np.any(areas[1:]>.025):raise ValueError('No dominant body with small accessories')
    body=v[labels==0]; lo=body.min(0);hi=body.max(0);span=hi-lo;h=span[1]
    if h<=1e-6 or np.any(v.min(0)<lo-h*.035) or np.any(v.max(0)>hi+h*.035):raise ValueError('Accessory extends body bounds')
    for i in range(1,len(areas)):
        if np.linalg.norm(np.ptp(v[labels==i],axis=0))>h*.10:raise ValueError('Accessory too large for rigid suggestion')
    proxy=trimesh.Trimesh(vertices=v,faces=f[fl==0],process=False);proxy.remove_unreferenced_vertices()
    bodyraw=proxy.export(file_type='glb')
    try:r=_propose_t_pose(bodyraw,joint_count)
    except ValueError:r=propose_a_pose(bodyraw,joint_count)
    # Existing guide is normalized to the proxy bounds; remap to original full mesh.
    full_lo=v.min(0);full_span=np.ptp(v,axis=0);g=r['guide']
    for row in g['joints']:
        row['position']=((lo+np.asarray(row['position'])*span-full_lo)/full_span).round(7).tolist()
    points=full_lo+np.asarray([row['position'] for row in g['joints']])*full_span
    bindings=[];review=[]
    for i in range(1,len(areas)):
        pts=np.unique(v[labels==i],axis=0);center=pts.mean(0);d=np.linalg.norm(points-center,axis=1);order=np.argsort(d);k=int(order[0])
        if d[k]>h*.12 or d[order[1]]-d[k]<h*.012:raise ValueError('Accessory joint ambiguous; manual guide required')
        bindings.append({'component':i,'joint':k});review.append({'component':i,'joint':g['joints'][k]['name'],'area_percent':round(float(areas[i]*100),3)})
    g['rigid_components']={'source_sha256':hashlib.sha256(raw).hexdigest(),'bindings':bindings}
    r.update(method='geometry_multipart_pose',body_method=r['method'],accessories=review)
    return r


def bind_accessories(raw,v,f,guide,js,ws):
    """All detached accessories must be explicitly mapped; stable source hash."""
    spec=guide['rigid_components']
    if not isinstance(spec,dict) or spec.get('source_sha256')!=hashlib.sha256(raw).hexdigest():raise ValueError('Stale component guide')
    labels,_,areas=geometry_components(v,f)
    if not 2<=len(areas)<=9 or areas[0]<.95 or np.any(areas[1:]>.025):raise ValueError('Accessory limits')
    bindings=spec.get('bindings'); seen=set()
    if not isinstance(bindings,list) or len(bindings)!=len(areas)-1:raise ValueError('Explicit binding required for every accessory')
    for row in bindings:
        i,k=row['component'],row['joint']
        if type(i)!=int or not 1<=i<len(areas) or i in seen or type(k)!=int or not 0<=k<len(guide['joints']):raise ValueError('Invalid accessory binding')
        seen.add(i);mask=labels==i;js[mask]=0;ws[mask]=0;js[mask,0]=k;ws[mask,0]=1
    return js,ws
