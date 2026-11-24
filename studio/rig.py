"""Explicit landmark-driven GLB skeletal binding. No automatic anatomy claims."""
import json, struct, copy
import numpy as np


def unpack(raw):
    n,t=struct.unpack_from('<II',raw,12)
    if t!=0x4e4f534a:raise ValueError('JSON chunk')
    j=json.loads(raw[20:20+n]);size,t=struct.unpack_from('<II',raw,20+n)
    if t!=0x004e4942 or 28+n+size!=len(raw):raise ValueError('BIN chunk')
    return j,bytearray(raw[28+n:])


def accessor(j,b,i):
    a=j['accessors'][i];v=j['bufferViews'][a['bufferView']]
    if a.get('sparse') or a.get('normalized') or v.get('buffer',0)!=0:raise ValueError('Unsupported accessor')
    dt=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]);k={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    off=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',dt.itemsize*k);n=a['count']
    if n<1 or n>1500000 or stride<dt.itemsize*k or off<0 or off+(n-1)*stride+k*dt.itemsize>v.get('byteOffset',0)+v['byteLength'] or off+(n-1)*stride+k*dt.itemsize>len(b):raise ValueError('Accessor bounds')
    return np.ndarray((n,k),dtype=dt,buffer=b,offset=off,strides=(stride,dt.itemsize)).copy()


def build_rig(raw,guide):
    j,b=unpack(raw)
    if j.get('skins') or j.get('animations') or j.get('extensionsRequired') or len(j['meshes'])!=1 or len(j['meshes'][0]['primitives'])!=1 or len(j.get('buffers',[]))!=1:raise ValueError('Single static embedded mesh required')
    p=j['meshes'][0]['primitives'][0];nodes=j['nodes'];ids=[i for i,n in enumerate(nodes) if 'mesh' in n]
    if len(ids)!=1 or p.get('targets') or p.get('mode',4)!=4:raise ValueError('Single static triangle mesh required')
    # Reject transformed meshes instead of binding in an incorrect coordinate frame.
    if any(any(k in n for k in ('matrix','translation','rotation','scale')) for n in nodes):raise ValueError('Apply node transforms before binding')
    v=accessor(j,b,p['attributes']['POSITION']).astype(np.float64)
    if v.shape[1]!=3 or len(v)>500000 or not np.isfinite(v).all():raise ValueError('Vertex limit')
    lo=v.min(0);hi=v.max(0);span=hi-lo;diag=float(np.linalg.norm(span))
    if min(span)<=1e-6 or diag<=1e-6:raise ValueError('Nonvolumetric mesh')
    rows=guide['joints'];n=len(rows)
    if not 2<=n<=64:raise ValueError('2–64 joints required')
    names=[];parents=[];pts=[]
    for i,r in enumerate(rows):
        name=r['name'];parent=r['parent'];q=np.asarray(r['position'],dtype=float)
        if not isinstance(name,str) or not 1<=len(name)<=48 or name in names or type(parent)!=int or (parent!=-1 if i==0 else not 0<=parent<i) or q.shape!=(3,) or not np.isfinite(q).all() or np.any(q<0) or np.any(q>1):raise ValueError('Invalid joint')
        names.append(name);parents.append(parent);pts.append(lo+q*span)
        if i and np.linalg.norm(pts[i]-pts[parent])<diag*.005:raise ValueError('Coincident joints')
    pts=np.asarray(pts);children=[[] for _ in rows]
    for i in range(1,n):children[parents[i]].append(i)
    # Distance to explicit joint-to-child guide segments, with point support for leaf joints.
    # Equal vertex coordinates get equal weights, including duplicate UV seam vertices.
    distances=np.empty((len(v),n),dtype=np.float32)
    for i in range(n):
        d=np.sum((v-pts[i])**2,axis=1)
        for child in children[i]:
            seg=pts[child]-pts[i];t=np.clip((v-pts[i])@seg/(seg@seg),0,.85)
            d=np.minimum(d,np.sum((v-pts[i]-t[:,None]*seg)**2,axis=1))
        distances[:,i]=d
    k=min(4,n);order=np.argsort(distances,axis=1,kind='stable')[:,:k];d=np.take_along_axis(distances,order,axis=1)
    blend=max(diag*.055,1e-8);weight=np.exp(-(d-d[:,0:1])/(2*blend**2));weight/=weight.sum(1,keepdims=True)
    js=np.zeros((len(v),4),dtype='<u2');ws=np.zeros((len(v),4),dtype='<f4');js[:,:k]=order;ws[:,:k]=weight
    if not np.isfinite(ws).all() or not np.allclose(ws.sum(1),1,atol=1e-6):raise ValueError('Invalid weights')
    # Append to original GLB: existing positions, UVs, indices, image bytes remain untouched.
    def add(a,ctype,kind,target=None,bounds=False):
        while len(b)%4:b.append(0)
        off=len(b);data=np.ascontiguousarray(a).tobytes();b.extend(data);view={'buffer':0,'byteOffset':off,'byteLength':len(data)}
        if target:view['target']=target
        j['bufferViews'].append(view);acc={'bufferView':len(j['bufferViews'])-1,'componentType':ctype,'count':len(a),'type':kind}
        if bounds:acc.update(min=[float(np.min(a))],max=[float(np.max(a))])
        j['accessors'].append(acc);return len(j['accessors'])-1
    p['attributes']['JOINTS_0']=add(js,5123,'VEC4',34962);p['attributes']['WEIGHTS_0']=add(ws,5126,'VEC4',34962)
    start=len(nodes);inv=np.tile(np.eye(4,dtype='<f4'),(n,1,1));inv[:,:3,3]=-pts
    for i in range(n):
        node={'name':names[i],'translation':(pts[i]-(pts[parents[i]] if i else 0)).tolist()}
        if children[i]:node['children']=[start+c for c in children[i]]
        nodes.append(node)
    j['scenes'][j.get('scene',0)]['nodes'].append(start)
    j['skins']=[{'name':'Forge landmark rig','joints':list(range(start,start+n)),'skeleton':start,'inverseBindMatrices':add(inv.transpose(0,2,1),5126,'MAT4')}];nodes[ids[0]]['skin']=0
    joint=guide.get('test_joint',n-1);axis=guide.get('axis','z');deg=float(guide.get('degrees',25))
    if type(joint)!=int or not 1<=joint<n or axis not in 'xyz' or len(axis)!=1 or not np.isfinite(deg) or not 1<=abs(deg)<=60:raise ValueError('Invalid test motion')
    q=np.array([[0,0,0,1],[0,0,0,1],[0,0,0,1]],dtype='<f4');ang=np.deg2rad(deg)/2;q[1,'xyz'.index(axis)]=np.sin(ang);q[1,3]=np.cos(ang)
    j['animations']=[{'name':'Forge joint bend test (not walk)','samplers':[{'input':add(np.array([0,1,2],dtype='<f4'),5126,'SCALAR',bounds=True),'output':add(q,5126,'VEC4'),'interpolation':'LINEAR'}],'channels':[{'sampler':0,'target':{'node':start+joint,'path':'rotation'}}]}]
    while len(b)%4:b.append(0)
    j['buffers'][0]['byteLength']=len(b);s=json.dumps(j,separators=(',',':'),ensure_ascii=True).encode();s+=b' '*((-len(s))%4)
    return struct.pack('<4sII',b'glTF',2,28+len(s)+len(b))+struct.pack('<II',len(s),0x4e4f534a)+s+struct.pack('<II',len(b),0x004e4942)+b
