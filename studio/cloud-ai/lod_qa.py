"""Compare three real mesh reduction candidates without replacing the AI source."""
import argparse,json,pathlib
import numpy as np,trimesh,vtk
from scipy.spatial import cKDTree
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray,vtk_to_numpy
p=argparse.ArgumentParser()
p.add_argument("input",type=pathlib.Path)
p.add_argument("output",type=pathlib.Path)
args=p.parse_args()
out=args.output
out.mkdir(parents=True,exist_ok=True)
m=trimesh.load(args.input,force="mesh",process=False)
assert m.is_watertight and m.visual.kind=="vertex" and np.isfinite(m.vertices).all()
def tovtk(m):
    p=vtk.vtkPolyData();points=vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices),deep=True));p.SetPoints(points)
    cells=vtk.vtkCellArray()
    cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,3*(len(m.faces)+1),3,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(np.asarray(m.faces,dtype=np.int64).ravel(),deep=True))
    p.SetPolys(cells)
    return p
def fromvtk(p,ref):
    v=vtk_to_numpy(p.GetPoints().GetData()).copy()
    f=vtk_to_numpy(p.GetPolys().GetConnectivityArray()).reshape(-1,3).copy()
    _,i=cKDTree(ref.vertices).query(v)
    return trimesh.Trimesh(v,f,vertex_colors=ref.visual.vertex_colors[i],process=False)
def distance(src,dst):
    loc=vtk.vtkStaticCellLocator();loc.SetDataSet(tovtk(dst));loc.BuildLocator()
    p=[0.,0.,0.];cell=vtk.reference(0);sub=vtk.reference(0);d=vtk.reference(0.)
    a=[]
    for x in src.vertices:
        loc.FindClosestPoint(x,p,cell,sub,d);a.append(float(d)**.5)
    return np.array(a)
extent=np.linalg.norm(m.extents)
parts=len(m.split(only_watertight=False))
report=[]
for name,budget in [("preserve_20k",20000),("preserve_12k",12000),("quadric_12k",12000)]:
    if len(m.faces)<=budget:continue
    d=vtk.vtkDecimatePro() if name.startswith("preserve") else vtk.vtkQuadricDecimation()
    d.SetInputData(tovtk(m));d.SetTargetReduction(1-budget/len(m.faces))
    if name.startswith("preserve"):
        d.PreserveTopologyOn();d.SplittingOff();d.BoundaryVertexDeletionOff();d.SetFeatureAngle(35)
    else:d.VolumePreservationOn()
    d.Update()
    c=fromvtk(d.GetOutput(),m)
    ab=distance(c,m)/extent;ba=distance(m,c)/extent
    r={"name":name,"faces":len(c.faces),"vertices":len(c.vertices),"components":len(c.split(only_watertight=False)),"watertight":bool(c.is_watertight),"euler":int(c.euler_number),"p99_surface_error_pct":float(max(np.quantile(ab,.99),np.quantile(ba,.99))*100),"max_surface_error_pct":float(max(ab.max(),ba.max())*100),"volume_change_pct":float(abs(c.volume/m.volume-1)*100),"colors":c.visual.kind=="vertex"}
    r["accepted"]=bool(r["watertight"] and r["components"]==parts and c.euler_number==m.euler_number and r["p99_surface_error_pct"]<.5 and r["max_surface_error_pct"]<1.5 and r["volume_change_pct"]<2 and len(c.faces)<=budget+100 and r["colors"] and np.isfinite(c.vertex_normals).all())
    if r["accepted"]:
        dst=out/(name+".glb")
        c.export(dst,include_normals=True)
        reload=trimesh.load(dst,force="mesh",process=False)
        assert len(reload.faces)==len(c.faces) and reload.visual.kind=="vertex" and reload.is_watertight
        r["bytes"]=dst.stat().st_size
    report.append(r)
passed=[r for r in report if r["accepted"]]
best=min(passed,key=lambda r:(r["faces"],r["p99_surface_error_pct"])) if passed else None
(out/"report.json").write_text(json.dumps({"original":{"faces":len(m.faces),"components":parts,"euler":m.euler_number},"candidates":report,"selected":best},indent=2))
print((out/"report.json").read_text())
assert best is not None,"No safe candidate: preserve original"
