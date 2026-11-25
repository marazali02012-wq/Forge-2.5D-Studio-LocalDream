"""Report per-component silhouette evidence; never remove geometry automatically."""
import numpy as np, cv2, trimesh

def component_evidence(mesh,masks,axes,center,pixel_size):
 masks=np.asarray(masks);axes=np.asarray(axes,float);center=np.asarray(center,float)
 if masks.ndim!=3 or not 3<=len(masks)<=32 or not 64<=min(masks.shape[1:])<=max(masks.shape[1:])<=1024 or axes.shape!=(len(masks),2,3) or not np.all(np.isin(masks,[0,1])):raise ValueError('Invalid masks')
 if center.shape!=(3,) or not np.isfinite(center).all() or not np.isfinite(pixel_size) or pixel_size<=0 or not np.isfinite(axes).all() or not np.allclose(axes@axes.transpose(0,2,1),np.eye(2),atol=1e-6):raise ValueError('Invalid calibration')
 if len(mesh.faces)>200000 or not np.isfinite(mesh.vertices).all() or mesh.area<=0:raise ValueError('Invalid mesh')
 parts=sorted(mesh.split(only_watertight=False,repair=False),key=lambda p:p.area,reverse=True)
 if len(parts)>128:raise ValueError('Component budget')
 h,w=masks.shape[1:];rows=[dict(id=i,faces=len(p.faces),area_fraction=float(p.area/mesh.area),supported_pixels=0,exclusive_supported_pixels=0,outside_pixels=0,visible_views=0) for i,p in enumerate(parts)]
 for mask,cam in zip(masks,axes):
  ras=[]
  for p in parts:
   xy=(p.vertices-center)@cam.T/pixel_size+np.array([(w-1)/2,(h-1)/2]);tri=np.rint(xy[p.faces]*256);
   if not np.isfinite(tri).all() or np.max(np.abs(tri))>2**30:raise ValueError('Projection out of bounds')
   tri=tri.astype(np.int32);im=np.zeros((h,w),np.uint8)
   for t in tri:cv2.fillConvexPoly(im,t,1,shift=8)
   ras.append(im.astype(bool))
  count=np.sum(ras,axis=0);mask=mask.astype(bool)
  for row,im in zip(rows,ras):
   a=int((im&mask).sum());row['supported_pixels']+=a;row['exclusive_supported_pixels']+=int((im&mask&(count==1)).sum());row['outside_pixels']+=int((im&~mask).sum());row['visible_views']+=int(a>0)
 for row in rows:
  row['classification']='review_no_exclusive_silhouette' if row['exclusive_supported_pixels']==0 else 'preserve_observed_silhouette'
 return rows,parts
