"""F01 full-resolution photo colors on existing actual OpenMVS dense output."""
import argparse,json,time
from pathlib import Path
import numpy as np,trimesh,pycolmap
from PIL import Image,ImageDraw
from forge_dense_color import colorize_dense,depth_buffer
from forge_sfm_orientation import alignment
from perspective_photo_probe import read_middlebury
from colmap_photo_probe import estimated_views

def main():
    p=argparse.ArgumentParser();p.add_argument("dataset",type=Path);p.add_argument("artifact",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    a.output.mkdir(exist_ok=False)
    # Depth test: overlapping triangles, foreground depth must win independent of face order.
    uv=np.array([[2.,2.],[8.,2.],[2.,8.],[2.,2.],[8.,2.],[2.,8.]])
    z=np.array([2.,2.,2.,1.,1.,1.]);f=np.array([[0,1,2],[3,4,5]])
    b=depth_buffer(uv,z,f,12,12);assert b[4,4]==1 and np.isinf(b[10,10]) and np.array_equal(b,depth_buffer(uv,z,f[::-1],12,12))
    r=pycolmap.Reconstruction(str(a.artifact/"colmap/sparse"))
    source=read_middlebury(a.dataset,a.output/"masks")
    views=estimated_views(r,{q["name"]:q for q in source})
    assert len(views)==48
    m=trimesh.load(a.artifact/"openmvs.glb",force="mesh",process=False)
    report={"source_run":46092339226,"faces":len(m.faces),"vertices":len(m.vertices),"watertight":bool(m.is_watertight)}
    c=m.copy();t=time.monotonic();colors,stats=colorize_dense(c,views);c.visual.vertex_colors=colors
    assert np.array_equal(m.vertices,c.vertices) and np.array_equal(m.faces,c.faces)
    report.update(stats,seconds=time.monotonic()-t)
    ordered=sorted((im for im in r.images.values() if im.has_pose),key=lambda im:im.name)
    rt=[im.cam_from_world().matrix() for im in ordered]
    T,metrics=alignment([q[:,:3] for q in rt],[-q[:,:3].T@q[:,3] for q in rt],"right")
    c.apply_transform(T);m.apply_transform(T)
    assert np.array_equal(m.faces,c.faces) and np.array_equal(m.vertices,c.vertices)
    c.export(a.output/"colored.glb",include_normals=True)
    re=trimesh.load(a.output/"colored.glb",force="mesh",process=False)
    assert np.array_equal(re.faces,c.faces) and np.array_equal(re.visual.vertex_colors,c.visual.vertex_colors)
    canvas=Image.new("RGB",(1200,650),(28,33,43));d=ImageDraw.Draw(canvas)
    for j,mesh in enumerate([m,c]):
        v=mesh.vertices.copy();v-=(v.min(0)+v.max(0))/2;v*=2/np.ptp(v,axis=0).max();f=mesh.faces;n=mesh.face_normals
        rgb=np.asarray(mesh.visual.vertex_colors)[f,:3].mean(1)/255 if j else np.tile([.46,.53,.61],(len(f),1))
        rgb=np.clip(np.where(rgb<=.0031308,12.92*rgb,1.055*np.maximum(rgb,0)**(1/2.4)-.055),0,1)
        d.text((12,j*325+8),("ORIGINAL" if j==0 else "REAL PNG PHOTO COLORS WITH FOREGROUND MASKS"),fill="white")
        for i,angle in enumerate([0,90,180,45]):
            theta=np.deg2rad(angle);x=v[:,0]*np.cos(theta)-v[:,2]*np.sin(theta);z=v[:,0]*np.sin(theta)+v[:,2]*np.cos(theta)
            pp=np.stack([i*300+150+135*x,j*325+165-135*v[:,1]],1)
            nz=n[:,0]*np.sin(theta)+n[:,2]*np.cos(theta);col=np.rint(rgb*(.55+.45*np.clip(.3*n[:,1]+.7*nz,0,1))[:,None]*255).astype(np.uint8)
            for k in np.argsort(z[f].mean(1)):d.polygon([tuple(pp[t]) for t in f[k]],fill=tuple(map(int,col[k])))
            d.text((i*300+10,j*325+307),str(angle)+" DEG",fill="white")
    canvas.save(a.output/"comparison.jpg")
    report["orientation"]=metrics;(a.output/"report.json").write_text(json.dumps(report,indent=2));print(report)
    # Old mesh includes floor: coverage is diagnostic, not a quality acceptance gate.
if __name__=="__main__":main()
