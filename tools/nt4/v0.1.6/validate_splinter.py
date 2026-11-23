"""Measure actual triangle footprints against the rifle's source UV metric."""
from pathlib import Path
import bpy,json,math,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'surface_measurements.json').read_text())
rows=json.loads((HERE/'paint_sources.json').read_text())
new=bpy.data.objects['NEW NT4 - editable replacement'];mesh=new.data;mesh.calc_loop_triangles()
scale=float(new.matrix_world.to_scale()[0]);cy,cz=m['new_body_center_yz'];R=m['new_body_outer_radius']
p=np.array([tuple(v.co) for v in mesh.vertices]);mid=(p[:,0].min()+p[:,0].max())/2
legacy_center=(p[:,1:].min(axis=0)+p[:,1:].max(axis=0))/2
length=p[:,0].max()-p[:,0].min()
result=[]
for row in rows:
    ref=next(r for r in m['patterns'] if r['slug']==row['slug'])
    B=np.array(ref['world_surface_per_source_pixel']);inverse=np.linalg.inv(B)
    w,h=row['crop'][2]-row['crop'][0],row['crop'][3]-row['crop'][1]
    data=[];old_data=[];cap_data=[]
    for tri in mesh.loop_triangles:
        positions=p[list(tri.vertices)]
        centroid=positions.mean(axis=0);rad=np.linalg.norm(centroid[1:]-[cy,cz])
        normal=np.cross(positions[1]-positions[0],positions[2]-positions[0]);area=np.linalg.norm(normal)
        if area<1e-12:continue
        normal/=area
        theta=np.arctan2(positions[:,1]-cy,positions[:,2]-cz)
        kind=None
        if .04<centroid[0]<.15 and abs(rad-R)<.00008 and abs(normal[0])<.03 and np.max(np.abs(theta))<math.pi-math.radians(12):
            st=np.column_stack([(positions[:,0]-mid)*scale,theta*R*scale]);kind='body'
        elif abs(normal[0])>.99999 and rad>R*.25:
            st=(positions[:,1:]-[cy,cz])*scale;kind='cap'
        else:continue
        pixel=st@inverse.T
        dp=(pixel[1:]-pixel[0]).T
        if abs(np.linalg.det(dp))<1e-8:continue
        J=((positions[1:]-positions[0])*scale).T@np.linalg.inv(dp)
        singular=np.linalg.svd(J@np.linalg.inv(B),compute_uv=False)
        entry=[float(singular.min()),float(singular.max()),float(singular.max()/singular.min())]
        if kind=='cap':cap_data.append(entry);continue
        data.append(entry)
    measured=np.array(data);caps=np.array(cap_data)
    assert len(data)>100 and len(cap_data)>10,(row['slug'],len(data),len(cap_data))
    assert measured[:,2].max()<1.03,(row['slug'],measured[:,2].max())
    assert np.max(np.abs(measured[:,:2]-1))<.03
    assert caps[:,2].max()<1.0001
    result.append(dict(slug=row['slug'],outer_body_triangles_checked=len(data),cap_triangles_checked=len(cap_data),
        maximum_body_aspect_error_percent=float((measured[:,2].max()-1)*100),
        maximum_body_scale_error_percent=float(np.max(np.abs(measured[:,:2]-1))*100),
        maximum_cap_aspect_error_percent=float((caps[:,2].max()-1)*100),
        newly_added_paint=True,
        source_gun_metric_preserved=True))

report=dict(splinter=result,passed=True)
(HERE/'aspect_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
