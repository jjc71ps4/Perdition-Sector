from pathlib import Path
import bpy,json,numpy as np,math
HERE=Path(__file__).resolve().parent
new=bpy.data.objects['NEW NT4 - editable replacement'];old=bpy.data.objects['Muzzle:0.008']
v=np.array([tuple(p.co) for p in new.data.vertices]);sel=v[(v[:,0]>.04)&(v[:,0]<.15)]
yz=sel[:,1:]
def circle(points):
    yz=points; A=np.column_stack([2*yz,np.ones(len(yz))]);abc=np.linalg.lstsq(A,(yz*yz).sum(axis=1),rcond=None)[0]
    return abc[:2],np.sqrt(abc[2]+(abc[:2]**2).sum())
c,r=circle(yz)
for _ in range(5):
    dist=np.linalg.norm(yz-c,axis=1); outer=dist>=np.percentile(dist,65)
    c,r=circle(yz[outer])
dist=np.linalg.norm(yz-c,axis=1)
convert=new.matrix_world.inverted()@old.matrix_world
ov=np.array([tuple(convert@p.co) for p in old.data.vertices])
oldr=np.linalg.norm(ov[:,1:],axis=1)
oldsel=ov[oldr>=np.percentile(oldr,70)][:,1:]
oc,orr=circle(oldsel)
print('NEW CIRCLE',c.tolist(),r,'RADIAL',np.percentile(dist,[10,25,50,75,90,95,99]).tolist(),flush=True)
print('OLD CIRCLE',oc.tolist(),orr,'BOUNDS',[ov.min(axis=0).tolist(),ov.max(axis=0).tolist()],flush=True)
report=dict(new_body_center_yz=c.tolist(),new_body_outer_radius=float(r),new_body_radius_percentiles=np.percentile(dist,[10,25,50,75,90,95,99]).tolist(),
    old_body_center_in_new_space=oc.tolist(),old_body_radius_in_new_space=float(orr),rutex_radial_scale_ratio=float(r/orr),
    rutex_transfer='Existing ray transfer: axial distance is retained; circumferential size follows old/new cylinder radii.',
    old_bounds_in_new_space=[ov.min(axis=0).tolist(),ov.max(axis=0).tolist()])
# Find actual triangle-to-surface UV metrics for the four rifle patches.
audit=json.loads((HERE/'projection_audit.json').read_text())
forward=np.array([0,1,0.]);up=np.array([0,0,1.])
for row in audit['patterns']:
    sample=next(c for c in row['source_candidates'] if c['visible'])
    J=np.array(sample['world_per_pixel_matrix'])
    normal=np.cross(J[:,0],J[:,1]);normal/=np.linalg.norm(normal)
    f=forward-normal*np.dot(forward,normal);f/=np.linalg.norm(f)
    t=np.cross(normal,f)
    if np.dot(t,up)<0:t=-t
    B=np.array([f@J,t@J])
    row['world_surface_per_source_pixel']=B.tolist()
    row['source_pixel_per_world_surface']=np.linalg.inv(B).tolist()
    row['source_basis']=[f.tolist(),t.tolist()]
report['patterns']=audit['patterns']
(HERE/'surface_measurements.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
