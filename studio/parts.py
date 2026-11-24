"""Connected geometry islands, not semantic parts. Never delete or modify input."""
import io, numpy as np, trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

def split_mesh(raw,j):
    if j.get('skins') or j.get('animations') or j.get('extensionsRequired') or any(p.get('targets') for m in j['meshes'] for p in m.get('primitives',[])):
        raise ValueError('Rig, animation or morph unsupported')
    if len(j['meshes'])!=1 or len(j['meshes'][0].get('primitives',[]))!=1:raise ValueError('Single static mesh required')
    scene=trimesh.load(io.BytesIO(raw),file_type='glb',force='scene',process=False)
    nodes=list(scene.graph.nodes_geometry)
    if len(nodes)!=1:raise ValueError('Single mesh instance required')
    matrix,name=scene.graph[nodes[0]];m=scene.geometry[name].copy()
    m.apply_transform(matrix)
    v=np.asarray(m.vertices);f=np.asarray(m.faces)
    if len(f)==0 or len(f)>500000 or not np.isfinite(v).all():raise ValueError('Geometry limit')
    # Weld coincident positions for connectivity ONLY; keep original texture seams in export.
    _,inv=np.unique(v,axis=0,return_inverse=True);wf=inv[f]
    e=np.sort(np.concatenate([wf[:,[0,1]],wf[:,[1,2]],wf[:,[2,0]]]),axis=1)
    owners=np.tile(np.arange(len(f)),3)
    order=np.lexsort((e[:,1],e[:,0]));e=e[order];owners=owners[order]
    same=np.all(e[1:]==e[:-1],axis=1);a=owners[:-1][same];b=owners[1:][same]
    graph=coo_matrix((np.ones(len(a),dtype=np.uint8),(a,b)),shape=(len(f),len(f))).tocsr()
    count,labels=connected_components(graph,directed=False)
    if count>4096:raise ValueError('Too many components')
    counts=np.bincount(labels,minlength=count);areas=np.bincount(labels,weights=m.area_faces,minlength=count)
    ordered=sorted(range(count),key=lambda x:(-counts[x],x));total=max(float(areas.sum()),1e-20)
    return m,labels,ordered,[{'id':i,'triangles':int(counts[x]),'area_percent':round(float(areas[x]/total*100),3)} for i,x in enumerate(ordered)]

def component_operation(raw,j,index=None,prune=False):
    m,labels,ordered,rows=split_mesh(raw,j)
    for row in rows: row['micro_candidate']=bool(row['id']>0 and row['triangles']<=64 and row['area_percent']<=0.05)
    if index is None:return {'parts':rows,'triangles':len(m.faces),'semantic':False}
    if not 0<=index<len(ordered):raise ValueError('Part out of range')
    if prune:
        if not rows[index]['micro_candidate']:raise ValueError('Only explicitly selected micro islands can be removed')
        selected=np.flatnonzero(labels!=ordered[index])
    else:selected=np.flatnonzero(labels==ordered[index])
    part=m.submesh([selected],append=True,repair=False)
    if len(part.faces)!=len(selected):raise ValueError('Part triangle mismatch')
    return part.export(file_type='glb')
