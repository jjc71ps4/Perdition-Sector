"""Measure the rifle UV-to-surface metric and the installed NT4 wrapping."""
from pathlib import Path
import bpy, hashlib, json, math, numpy as np

HERE=Path(__file__).resolve().parent
previous=HERE.parent/'v0.1.4'
rows=json.loads((previous/'paint_sources.json').read_text())
new=bpy.data.objects['NEW NT4 - editable replacement']
verts=np.array([tuple(v.co) for v in new.data.vertices])
lo,hi=verts.min(axis=0),verts.max(axis=0)
axis=np.array(new.matrix_world.to_3x3())
scales=np.linalg.norm(axis,axis=0)
center=np.median(verts[:,1:],axis=0)
# Circular body axis is the source model's origin, not the bounding-box center
# (the asymmetric latch extends beyond the circular can).
radii=np.linalg.norm(verts[:,1:],axis=1)
body=radii[(verts[:,0]>.04)&(verts[:,0]<.15)]
radius=float(np.median(body))
result=dict(source_blend=bpy.data.filepath,source_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
    target_bounds=[lo.tolist(),hi.tolist()],target_world_scales=scales.tolist(),
    body_radius_percentiles=np.percentile(body,[10,25,50,75,90,99]).tolist(),
    axis_origin=[0,0],bounds_center_yz=((lo[1:]+hi[1:])/2).tolist(),
    radial_median_center_yz=center.tolist(),target_radius_world=radius*scales[1],
    target_length_world=(hi[0]-lo[0])*scales[0],patterns=[])
objects=[]
for obj in bpy.context.scene.objects:
    if obj.type!='MESH' or obj==new:continue
    if not any(m and ('mk18' in m.name.lower() or 'suppressor_kac' in m.name.lower()) for m in obj.data.materials):continue
    mesh=obj.data
    if not mesh.uv_layers:continue
    mesh.calc_loop_triangles()
    uv=mesh.uv_layers[0]
    for row in rows:
        cx=(row['crop'][0]+row['crop'][2])/2
        cy=(row['crop'][1]+row['crop'][3])/2
        point=np.array([cx,cy])
        for tri in mesh.loop_triangles:
            mat=mesh.materials[tri.material_index]
            if not mat or 'mk18' not in mat.name.lower():continue
            pixels=np.array([(uv.data[li].uv.x*4096,(1-uv.data[li].uv.y)*4096) for li in tri.loops])
            if np.any(point<pixels.min(axis=0)-.01) or np.any(point>pixels.max(axis=0)+.01):continue
            uv_edges=(pixels[1:]-pixels[0]).T
            if abs(np.linalg.det(uv_edges))<.01:continue
            b=np.linalg.solve(uv_edges,point-pixels[0])
            if b.min()<-.001 or b.sum()>1.001:continue
            positions=np.array([tuple(obj.matrix_world@mesh.vertices[mesh.loops[li].vertex_index].co) for li in tri.loops])
            jac=(positions[1:]-positions[0]).T@np.linalg.inv(uv_edges)
            singular=np.linalg.svd(jac,compute_uv=False)
            world=(positions[0]+(positions[1:]-positions[0]).T@b)
            objects.append(dict(slug=row['slug'],object=obj.name,material=mat.name,triangle=tri.index,
                visible=not obj.hide_get(),world_point=world.tolist(),world_per_pixel_matrix=jac.tolist(),
                world_per_pixel_singular=singular.tolist(),world_per_pixel_axes=np.linalg.norm(jac,axis=0).tolist(),
                column_angle_degrees=math.degrees(math.acos(float(np.clip(np.dot(jac[:,0],jac[:,1])/np.prod(np.linalg.norm(jac,axis=0)),-1,1))))))
for row in rows:
    w,h=row['crop'][2]-row['crop'][0],row['crop'][3]-row['crop'][1]
    length=result['target_length_world'];circum=2*math.pi*result['target_radius_world']
    px_x=w*row['axial_repeat']/length
    px_t=h*row['circumference_repeat']/circum
    result['patterns'].append(dict(slug=row['slug'],old_axial_pixels_per_world=px_x,
        old_circumferential_pixels_per_world=px_t,old_horizontal_stretch=px_t/px_x,
        source_candidates=[o for o in objects if o['slug']==row['slug']]))
old=bpy.data.objects.get('Muzzle:0.008')
if old:
    result['rutex_source_object']=dict(name=old.name,matrix=[list(r) for r in old.matrix_world],
        materials=[m.name if m else None for m in old.data.materials],uvs=[u.name for u in old.data.uv_layers])
(HERE/'projection_audit.json').write_text(json.dumps(result,indent=2,default=float))
print(json.dumps(result,indent=2,default=float),flush=True)
