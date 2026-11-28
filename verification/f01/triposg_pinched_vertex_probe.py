"""Experimental final local repair for closed meshes with a single pinched vertex.
Input must already have zero boundary and nonmanifold edges. No global mesh
repair, no production acceptance. Based on actual R3 Quadric model experiment.
"""
import argparse, collections, json
from pathlib import Path
import numpy as np
import trimesh
import vtk

def fans(f):
    links=collections.defaultdict(list)
    for a,b,c in f:
        links[a].append((b,c));links[b].append((c,a));links[c].append((a,b))
    bad={}
    for i,pairs in links.items():
        adj=collections.defaultdict(set)
        for a,b in pairs:adj[a].add(b);adj[b].add(a)
        if any(len(x)!=2 for x in adj.values()):
            raise ValueError("invalid vertex-link degree")
        seen=set();groups=[]
        for a in adj:
            if a in seen:continue
            todo=[a];g=set()
            while todo:
                n=todo.pop()
                if n not in g:g.add(n);todo.extend(adj[n]-g)
            seen|=g;groups.append(g)
        if len(groups)>1:bad[i]=groups
    return bad

def split(m):
    v=np.asarray(m.vertices);f=np.asarray(m.faces)
    if not m.is_watertight or not m.is_winding_consistent or np.any(m.area_faces<=1e-12):
        raise ValueError("input must be closed and consistently wound")
    bad=fans(f)
    if not bad:return m.copy(),dict(changed=False)
    if len(bad)!=1:raise ValueError("more than one pinched vertex")
    i,groups=next(iter(bad.items()))
    if len(groups)!=2:raise ValueError("unsupported vertex fans")
    idx=np.flatnonzero((f==i).any(1));diag=float(np.linalg.norm(m.extents))
    if len(idx)>24 or len(v)>=30000:raise ValueError("local repair budget exceeded")
    if max(np.linalg.norm(v[j]-v[i]) for g in groups for j in g)>diag*.015:
        raise ValueError("large region")
    vv=np.vstack([v,v[i]]);ff=f.copy();delta=[]
    for n,g in enumerate(groups):
        direction=v[sorted(g)].mean(0)-v[i];length=min(.05*np.linalg.norm(direction),diag*.0005)
        if length<=1e-10:raise ValueError("no separation direction")
        j=int(i) if n==0 else len(v)
        vv[j]=v[i]+direction/np.linalg.norm(direction)*length;delta.append(float(length))
        for k in idx:
            if any(int(a) in g for a in f[k] if a!=i):ff[k,ff[k]==i]=j
    x=trimesh.Trimesh(vv,ff,process=False)
    dot=np.einsum("ij,ij->i",x.face_normals[idx],m.face_normals[idx])
    if min(dot)<.95 or np.any(x.area_faces<=1e-12) or fans(ff) or not x.is_watertight or not x.is_winding_consistent:
        raise ValueError("post-repair topology rejected")
    if len(x.split(only_watertight=False))!=1 or x.volume<=0 or len(ff)>60000:
        raise ValueError("component or budget rejected")
    tri=x.triangles;lo=tri.min(1);hi=tri.max(1)
    for k in idx:
        t=tri[k]
        near=np.flatnonzero(np.all(hi>=t.min(0)-1e-9,axis=1)&np.all(lo<=t.max(0)+1e-9,axis=1))
        for j in near:
            if j==k or set(ff[k])&set(ff[j]):continue
            cop=vtk.reference(0);p1=[0.,0.,0.];p2=p1.copy();sid=[0.,0.]
            ret=vtk.vtkIntersectionPolyDataFilter.TriangleTriangleIntersection(*t,*tri[j],cop,p1,p2,sid,1e-10)
            if ret or cop.get():raise ValueError("local intersection or coplanar uncertainty")
    return x,dict(changed=True,vertex=int(i),displacements=delta,min_normal_dot=float(min(dot)),faces=len(ff),vertices=len(vv),global_self_intersection_verified=False)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("input",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    if a.output.exists() or a.input.resolve()==a.output.resolve():raise ValueError("refuse overwrite")
    m=trimesh.load(a.input,force="mesh",process=False);x,r=split(m)
    x.export(a.output,include_normals=True)
    q=trimesh.load(a.output,force="mesh",process=False)
    assert not fans(q.faces) and q.is_watertight and q.is_winding_consistent and len(q.faces)==len(x.faces)
    print(json.dumps(r,indent=2))
