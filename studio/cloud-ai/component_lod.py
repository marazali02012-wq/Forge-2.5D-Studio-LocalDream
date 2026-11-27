import argparse,json,pathlib
import numpy as np,trimesh,vtk
from scipy.spatial import cKDTree
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray,vtk_to_numpy
def tovtk(m):
    p=vtk.vtkPolyData();points=vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices),deep=True));p.SetPoints(points)
    cells=vtk.vtkCellArray();cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,3*(len(m.faces)+1),3,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(np.asarray(m.faces,dtype=np.int64).ravel(),deep=True));p.SetPolys(cells);return p
def reduce(m,target,method):
    if target>=len(m.faces):return m.copy()
    d=vtk.vtkQuadricDecimation() if method=='quadric' else vtk.vtkDecimatePro();d.SetInputData(tovtk(m));d.SetTargetReduction(1-target/len(m.faces))
    if method=='quadric':d.VolumePreservationOn()
    else:d.PreserveTopologyOn();d.SplittingOff();d.BoundaryVertexDeletionOff();d.SetFeatureAngle(35)
    d.Update();p=d.GetOutput();v=vtk_to_numpy(p.GetPoints().GetData()).copy();f=vtk_to_numpy(p.GetPolys().GetConnectivityArray()).reshape(-1,3).copy();_,idx=cKDTree(m.vertices).query(v)
    return trimesh.Trimesh(v,f,vertex_colors=m.visual.vertex_colors[idx],process=False)
def distances(src,dst):
    loc=vtk.vtkStaticCellLocator();loc.SetDataSet(tovtk(dst));loc.BuildLocator();p=[0.,0.,0.];cell=vtk.reference(0);sub=vtk.reference(0);d=vtk.reference(0.)
    vals=np.empty(len(src.vertices))
    for i,x in enumerate(src.vertices):loc.FindClosestPoint(x,p,cell,sub,d);vals[i]=float(d)**.5
    return vals
def topology(m):return bool(m.is_watertight and m.is_winding_consistent and np.isfinite(m.vertices).all() and np.min(m.area_faces)>0)
def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');a=p.parse_args();out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    source=trimesh.load(a.input,force='mesh',process=False);assert topology(source) and source.visual.kind=='vertex'
    components=sorted(source.split(only_watertight=False),key=lambda c:len(c.faces),reverse=True);extent=np.linalg.norm(source.extents);attempts=[];selected=[]
    for i,m in enumerate(components):
        n=len(m.faces);candidate=m;info={'component':i,'original_faces':n,'method':'unchanged','faces':n}
        if n>512:
            for target in sorted(set(min(n,max(512,int(n*f)))//2*2 for f in (.12,.18,.25,.35,.50,.75))):
                found=[]
                for method in ('quadric','preserve'):
                    c=reduce(m,target,method);r={'component':i,'method':method,'target':target,'faces':len(c.faces),'watertight':bool(c.is_watertight),'euler':int(c.euler_number)}
                    ok=topology(c) and c.euler_number==m.euler_number and len(c.split(only_watertight=False))==1 and c.visual.kind=='vertex'
                    if ok:
                        ab=distances(c,m)/extent;ba=distances(m,c)/extent
                        r.update(p99_pct=float(max(np.quantile(ab,.99),np.quantile(ba,.99))*100),max_pct=float(max(ab.max(),ba.max())*100),volume_change_pct=float(abs(c.volume/m.volume-1)*100))
                        ok=r['p99_pct']<.5 and r['max_pct']<1.5 and r['volume_change_pct']<2
                    r['accepted']=bool(ok);attempts.append(r);print(r,flush=True)
                    if ok:found.append((c,r))
                if found:
                    candidate,info=min(found,key=lambda x:(len(x[0].faces),x[1]['p99_pct']));break
        selected.append(candidate);info=dict(info);info['original_faces']=n;print('SELECT',info,flush=True)
    mesh=trimesh.util.concatenate(selected);assert topology(mesh) and mesh.euler_number==source.euler_number and len(mesh.split(only_watertight=False))==len(components)
    assert mesh.visual.kind=='vertex';ab=distances(mesh,source)/extent;ba=distances(source,mesh)/extent
    dest=out/'mobile.glb';mesh.export(dest,include_normals=True);reload=trimesh.load(dest,force='mesh',process=False);assert topology(reload) and reload.euler_number==source.euler_number and len(reload.faces)==len(mesh.faces)
    report={'source_faces':len(source.faces),'faces':len(mesh.faces),'components':len(components),'euler':int(mesh.euler_number),'watertight':bool(mesh.is_watertight),'p99_pct':float(max(np.quantile(ab,.99),np.quantile(ba,.99))*100),'max_pct':float(max(ab.max(),ba.max())*100),'volume_change_pct':float(abs(mesh.volume/source.volume-1)*100),'bytes':dest.stat().st_size,'attempts':attempts}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='attempts'},indent=2))
    assert report['p99_pct']<.5 and report['max_pct']<1.5 and report['volume_change_pct']<2 and len(mesh.faces)<len(source.faces)
if __name__=='__main__':main()
