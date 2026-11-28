"""F01 conservative open-surface LOD. Never silently close or remove geometry."""
import argparse,json,time
from pathlib import Path
import numpy as np,trimesh,vtk
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray,vtk_to_numpy

def poly(m):
    p=vtk.vtkPolyData();pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices),deep=True));p.SetPoints(pts)
    cells=vtk.vtkCellArray();cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,3*(len(m.faces)+1),3,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(np.asarray(m.faces,dtype=np.int64).ravel(),deep=True));p.SetPolys(cells);return p

def distances(src,dst):
    loc=vtk.vtkStaticCellLocator();loc.SetDataSet(poly(dst));loc.BuildLocator()
    q=[0.,0.,0.];cid=vtk.reference(0);sid=vtk.reference(0);ds=vtk.reference(0.)
    v=np.asarray(src.vertices);ix=np.random.default_rng(923).choice(len(v),min(10000,len(v)),replace=False);out=[]
    for a in v[ix]:
        loc.FindClosestPoint(a,q,cid,sid,ds);out.append(float(ds)**.5)
    return np.array(out)

def topo(m):
    counts=np.bincount(m.edges_unique_inverse);e=m.edges_unique[counts==1]
    return dict(euler=int(m.euler_number),boundary_edges=len(e),boundary_length=float(np.linalg.norm(m.vertices[e[:,0]]-m.vertices[e[:,1]],axis=1).sum()),nonmanifold=int((counts>2).sum()),components=len(m.split(only_watertight=False,repair=False)),winding=bool(m.is_winding_consistent))

def candidate(m,target,mode):
    if mode=="preserve":
        d=vtk.vtkDecimatePro();d.PreserveTopologyOn();d.SplittingOff();d.BoundaryVertexDeletionOff()
    elif mode=="quadric":
        d=vtk.vtkQuadricDecimation();d.VolumePreservationOn();d.SetBoundaryWeightFactor(10.)
    else:raise ValueError("unknown mode")
    d.SetInputData(poly(m));d.SetTargetReduction(1-target/len(m.faces));d.Update();o=d.GetOutput()
    return trimesh.Trimesh(vtk_to_numpy(o.GetPoints().GetData()).copy(),vtk_to_numpy(o.GetPolys().GetConnectivityArray()).reshape(-1,3).copy(),process=False)

def main():
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    a.output.mkdir(exist_ok=False);m=trimesh.load(a.source,force="mesh",process=False)
    if not np.isfinite(m.vertices).all() or len(m.faces)<=60000 or m.is_watertight or m.visual.defined:raise ValueError("requires overbudget uncolored open surface")
    src=topo(m)
    if not src["winding"] or src["nonmanifold"] or src["boundary_length"]<=0:raise ValueError("invalid source")
    report={"source":src,"faces":len(m.faces),"candidates":[]}
    for mode in ["preserve","quadric"]:
        t=time.monotonic();o=candidate(m,58000,mode);ts=topo(o)
        di=np.r_[distances(m,o),distances(o,m)]/np.linalg.norm(m.extents)*100
        row=dict(mode=mode,faces=len(o.faces),vertices=len(o.vertices),topology=ts,p99=float(np.quantile(di,.99)),max_sample=float(di.max()),area_delta_pct=float(abs(o.area/m.area-1)*100),boundary_delta_pct=float(abs(ts["boundary_length"]/src["boundary_length"]-1)*100),seconds=time.monotonic()-t)
        row["accepted"]=bool(len(o.faces)<=60000 and len(o.vertices)<=30000 and ts["euler"]==src["euler"] and ts["components"]==src["components"] and ts["winding"] and ts["nonmanifold"]==src["nonmanifold"] and row["p99"]<.1 and row["max_sample"]<.5 and row["area_delta_pct"]<1 and row["boundary_delta_pct"]<1)
        if row["accepted"]:
            dst=a.output/(mode+".glb");o.export(dst,include_normals=True)
            q=trimesh.load(dst,force="mesh",process=False)
            assert len(q.faces)==len(o.faces) and topo(q)["euler"]==src["euler"]
        report["candidates"].append(row);print(row,flush=True)
    accepted=[r for r in report["candidates"] if r["accepted"]]
    report["selected"]=min(accepted,key=lambda r:r["p99"])["mode"] if accepted else None
    (a.output/"report.json").write_text(json.dumps(report,indent=2))
    if not accepted:raise SystemExit("no safe mobile candidate; retain source")
if __name__=="__main__":main()
