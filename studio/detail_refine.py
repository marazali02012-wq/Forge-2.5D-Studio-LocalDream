"""Optional bounded high-resolution extraction of the SAME real neural field.
No geometry synthesis, smoothing, or claims about unknown back-side accuracy.
"""
import numpy as np
from PIL import Image, ImageDraw
from quality import compare
from atlas_qa import geometry_report


def view_stability(base, candidate, n=192):
    """Orthographic silhouettes in shared physical coordinates (no separate refit)."""
    a,b=np.asarray(base.vertices),np.asarray(candidate.vertices)
    result={}
    for name,axes in [('front',(1,2)),('side',(0,2)),('top',(0,1))]:
        p,q=a[:,axes],b[:,axes]
        lo=np.minimum(p.min(0),q.min(0));hi=np.maximum(p.max(0),q.max(0))
        scale=(n-12)/max(float(max(hi-lo)),1e-8)
        def draw(v,f):
            v=(v-(lo+hi)/2)*scale+n/2
            img=Image.new('1',(n,n));d=ImageDraw.Draw(img);pts=list(map(tuple,v.tolist()))
            for face in f:d.polygon([pts[i] for i in face],fill=1)
            return np.asarray(img,dtype=bool)
        ma,mb=draw(p,base.faces),draw(q,candidate.faces)
        result[name]=round(float((ma&mb).sum()/max(1,(ma|mb).sum())),5)
    return result


def refine_detail(model,code,mesh,best,reference,attempts):
    """Refine at 160 (or already finer: no-op). Retain baseline if guard fails."""
    audit={'requested':True,'applied':False,'baseline_resolution':int(best['resolution']),
           'target_resolution':160,'unseen_surfaces_verified':False,
           'comparison_is_stability_not_accuracy':True}
    if best['resolution']>=160:
        return mesh,best,dict(audit,reason='already_at_least_160')
    try:
        m=model.extract_mesh(code,False,resolution=160,threshold=best['threshold'])[0]
        if len(m.faces)<500 or len(m.vertices)<300 or len(m.faces)>100000 or not np.isfinite(m.vertices).all() or min(m.extents)<=.01:
            return mesh,best,dict(audit,reason='mesh_budget_or_degeneracy')
        if m.volume<0:m.invert()
        q=compare(reference,m.vertices[:,[1,2,0]],m.faces)
        q.update(resolution=160,threshold=best['threshold'],framing=best['framing'],topology=geometry_report(m),stage='detail_refine_same_field')
        attempts.append(q)
        stable=view_stability(mesh,m)
        g,b=q['topology'],best['topology']
        audit.update(candidate_iou=q['iou'],baseline_iou=best['iou'],candidate_triangles=len(m.faces),baseline_triangles=len(mesh.faces),
                     candidate_components=g['components'],baseline_components=b['components'],view_stability=stable)
        reasons=[]
        if q['iou']<best['iou']-.012 or q['recall']<best['recall']-.015 or (q['warning'] and not best['warning']) or (q['severe'] and not best['severe']):reasons.append('front_fidelity')
        if min(stable.values())<.92:reasons.append('view_stability')
        if (b['watertight'] and not g['watertight']) or (b['winding_consistent'] and not g['winding_consistent']) or g['small_area_fraction']>b['small_area_fraction']+.0005:reasons.append('topology')
        if len(m.faces)<=len(mesh.faces)*1.1 or len(m.faces)>len(mesh.faces)*5:reasons.append('triangle_budget')
        if reasons:return mesh,best,dict(audit,reason=','.join(reasons))
        return m,q,dict(audit,applied=True,reason='guarded_high_resolution')
    except Exception as e:
        attempts.append({'resolution':160,'stage':'detail_refine_same_field','error':type(e).__name__})
        return mesh,best,dict(audit,reason=type(e).__name__)
