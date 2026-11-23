"""Match rifle paint in measured surface units; never tune U/V independently."""
from pathlib import Path
import bpy, hashlib, json, math, numpy as np
from mathutils import Vector

HERE=Path(__file__).resolve().parent
OUT=HERE/'GameExport';OUT.mkdir(exist_ok=True)
source=Path(bpy.data.filepath);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
measure=json.loads((HERE/'surface_measurements.json').read_text())
sources=json.loads((HERE.parent/'v0.1.4/paint_sources.json').read_text())
original=bpy.data.objects['NEW NT4 - editable replacement']
scale=float(original.matrix_world.to_scale()[0])
assert max(original.matrix_world.to_scale())-min(original.matrix_world.to_scale())<1e-4
cy,cz=measure['new_body_center_yz'];radius=measure['new_body_outer_radius']
points=np.array([tuple(v.co) for v in original.data.vertices]);xmin,xmax=points[:,0].min(),points[:,0].max()
xmid=(xmin+xmax)/2
scene=bpy.data.scenes.new('NT4 metric camo correction')
target=bpy.data.objects.new('Bake unchanged NT4',original.data.copy());scene.collection.objects.link(target)
bpy.context.window.scene=scene;target.select_set(True);scene.view_layers[0].objects.active=target
target.data.uv_layers.active=target.data.uv_layers['UVmap_0'];target.data.uv_layers['UVmap_0'].active_render=True
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4
scene.render.bake.margin=24;scene.render.bake.use_selected_to_active=False;scene.render.bake.use_clear=True
report=[]

def material_for(row, planar=False):
    material=bpy.data.materials.new(('Reference ' if planar else 'Metric paint ')+row['slug']);material.use_nodes=True
    n,l=material.node_tree.nodes,material.node_tree.links;n.clear()
    def mathnode(op,a,b=None):
        node=n.new('ShaderNodeMath');node.operation=op
        for i,value in enumerate([a,b]):
            if value is None:continue
            if isinstance(value,(int,float,np.floating)):node.inputs[i].default_value=float(value)
            else:l.new(value,node.inputs[i])
        return node.outputs[0]
    geom=n.new('ShaderNodeNewGeometry');sep=n.new('ShaderNodeSeparateXYZ');l.new(geom.outputs['Position'],sep.inputs[0])
    y=mathnode('SUBTRACT',sep.outputs['Y'],cy);z=mathnode('SUBTRACT',sep.outputs['Z'],cz)
    s=mathnode('MULTIPLY',mathnode('SUBTRACT',sep.outputs['X'],xmid),scale)
    theta=mathnode('ARCTAN2',y,z)
    t=mathnode('MULTIPLY',theta,radius*scale)
    metric=next(r for r in measure['patterns'] if r['slug']==row['slug'])
    B=np.array(metric['world_surface_per_source_pixel']);inv=np.linalg.inv(B)
    w,h=row['crop'][2]-row['crop'][0],row['crop'][3]-row['crop'][1]
    def coords(s,t):
        comb=n.new('ShaderNodeCombineXYZ')
        u=mathnode('ADD',mathnode('MULTIPLY',s,inv[0,0]/w),mathnode('MULTIPLY',t,inv[0,1]/w))
        v=mathnode('ADD',mathnode('MULTIPLY',s,-inv[1,0]/h),mathnode('MULTIPLY',t,-inv[1,1]/h))
        l.new(mathnode('ADD',u,.5),comb.inputs['X']);l.new(mathnode('ADD',v,.5),comb.inputs['Y'])
        return comb.outputs[0]
    image=bpy.data.images.load(row['paint_path'],check_existing=True);image.colorspace_settings.name='sRGB'
    def texture(uv):
        tex=n.new('ShaderNodeTexImage');tex.image=image;tex.extension='MIRROR';l.new(uv,tex.inputs['Vector']);return tex.outputs['Color']
    if planar:
        color=texture(coords(s,mathnode('MULTIPLY',z,scale)))
    else:
        primary=texture(coords(s,t))
        # Put the inevitable closure below the can. Crossfade two metrically
        # identical wraps in a narrow underside strip; never stretch to close it.
        alternate_t=mathnode('ADD',t,mathnode('MULTIPLY',mathnode('SIGN',theta),-2*math.pi*radius*scale))
        alternate=texture(coords(s,alternate_t))
        seam_width=math.radians(10)
        weight=n.new('ShaderNodeMapRange');weight.interpolation_type='SMOOTHSTEP';weight.clamp=True
        weight.inputs['From Min'].default_value=math.pi-seam_width;weight.inputs['From Max'].default_value=math.pi
        weight.inputs['To Min'].default_value=0;weight.inputs['To Max'].default_value=.5
        l.new(mathnode('ABSOLUTE',theta),weight.inputs['Value'])
        blend=n.new('ShaderNodeMixRGB');l.new(weight.outputs['Result'],blend.inputs[0]);l.new(primary,blend.inputs[1]);l.new(alternate,blend.inputs[2])
        # End-facing surfaces get a true planar projection. An angular map on
        # a disk would pinch/stretch the same paint at the bore and rim.
        cap=texture(coords(mathnode('MULTIPLY',y,scale),mathnode('MULTIPLY',z,scale)))
        normal=n.new('ShaderNodeSeparateXYZ');l.new(geom.outputs['True Normal'],normal.inputs[0])
        face=mathnode('GREATER_THAN',mathnode('ABSOLUTE',normal.outputs['X']),.85)
        mix=n.new('ShaderNodeMixRGB');l.new(face,mix.inputs[0]);l.new(blend.outputs[0],mix.inputs[1]);l.new(cap,mix.inputs[2])
        color=mix.outputs[0]
        uv=n.new('ShaderNodeUVMap');uv.uv_map='UVmap_0'
        base=n.new('ShaderNodeTexImage');base.image=bpy.data.images.load(str(HERE.parent/'v0.1.0/GameExport/nt4_fde_d.png'),check_existing=True)
        base.image.colorspace_settings.name='sRGB';l.new(uv.outputs[0],base.inputs['Vector'])
        lum=n.new('ShaderNodeRGBToBW');l.new(base.outputs[0],lum.inputs[0])
        detail=mathnode('MINIMUM',mathnode('POWER',mathnode('DIVIDE',lum.outputs[0],.127),.7),1.5)
        tint=n.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1
        l.new(color,tint.inputs[1]);l.new(detail,tint.inputs[2]);color=tint.outputs[0]
    emission=n.new('ShaderNodeEmission');l.new(color,emission.inputs['Color'])
    output=n.new('ShaderNodeOutputMaterial');l.new(emission.outputs[0],output.inputs['Surface'])
    return material,metric

for index,row in enumerate(sources):
    material,metric=material_for(row)
    target.data.materials.clear();target.data.materials.append(material)
    for p in target.data.polygons:p.material_index=0
    image=bpy.data.images.new('nt4_'+row['slug'].lower()+'_d',width=4096,height=4096,alpha=False)
    image.colorspace_settings.name='sRGB';node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
    material.node_tree.nodes.active=node
    print('BAKING_METRIC '+row['slug'],flush=True);bpy.ops.object.bake(type='EMIT')
    image.file_format='PNG';image.filepath_raw=str(OUT/(image.name+'.png'));image.save()
    # Preview file pixels, rather than the transient bake image buffer.
    baked=bpy.data.images.load(image.filepath_raw,check_existing=False);baked.colorspace_settings.name='sRGB'
    pm=bpy.data.materials['NT4 | 01 Original FDE'].copy();pn,pl=pm.node_tree.nodes,pm.node_tree.links
    uv=pn.new('ShaderNodeUVMap');uv.uv_map='UVmap_0'
    for node in list(pn):
        if node.type=='TEX_IMAGE' and not node.inputs['Vector'].is_linked:pl.new(uv.outputs[0],node.inputs['Vector'])
        if node.type=='NORMAL_MAP':node.uv_map='UVmap_0'
    pn['NT4 BaseColor'].image=baked
    for socket,value in [('Metallic',.08),('Roughness',.65),('Specular IOR Level',.2)]:
        ps=pn['Principled BSDF']
        for link in list(ps.inputs[socket].links):pl.remove(link)
        ps.inputs[socket].default_value=value
    specimen=bpy.data.objects.new(row['slug'],original.data.copy());scene.collection.objects.link(specimen)
    specimen.data.materials.clear();specimen.data.materials.append(pm);specimen.location.z=.135-index*.09
    # Reference strip uses the rifle's measured scale on a flat surface.
    # It receives the same object-local coordinates as the cylinder.
    refmat,_=material_for(row,planar=True)
    rm=bpy.data.meshes.new('Reference strip '+row['slug'])
    rm.from_pydata([(xmin,-.022,-.007),(xmax,-.022,-.007),(xmax,-.022,.007),(xmin,-.022,.007)],[],[(0,1,2,3)])
    ref=bpy.data.objects.new('Rifle-scale reference '+row['slug'],rm);scene.collection.objects.link(ref)
    ref.data.materials.append(refmat);ref.location.z=specimen.location.z-.039
    # Position is evaluated in world coordinates. Cancel the display row's Z
    # offset for the planar reference so it doesn't shift its paint phase.
    gn=next(n for n in refmat.node_tree.nodes if n.type=='NEW_GEOMETRY')
    sep=next(n for n in refmat.node_tree.nodes if n.type=='SEPXYZ')
    offset=refmat.node_tree.nodes.new('ShaderNodeVectorMath');offset.operation='SUBTRACT'
    offset.inputs[1].default_value=(0,0,ref.location.z)
    refmat.node_tree.links.new(gn.outputs['Position'],offset.inputs[0]);refmat.node_tree.links.new(offset.outputs[0],sep.inputs[0])
    report.append(dict(slug=row['slug'],diffuse=image.filepath_raw,source_surface_metric=metric['world_surface_per_source_pixel'],
        independent_axis_repeats_removed=True,caps_planar=True,seam_width_degrees=10))

target.hide_render=True
scene.world=bpy.data.worlds.new('Metric paint studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.1,.12,.15,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4
center=Vector((xmid,0,-.014));camdata=bpy.data.cameras.new('Metric camera');camera=bpy.data.objects.new('Metric camera',camdata)
scene.collection.objects.link(camera);camera.location=center+Vector((0,-.7,.015))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camdata.type='ORTHO';camdata.ortho_scale=.40;camdata.clip_start=.001;scene.camera=camera
for name,location,energy,size in [('Key',(.08,-.3,.4),5,.4),('Fill',(.1,-.15,-.15),2,.3)]:
    ld=bpy.data.lights.new(name,'AREA');ld.energy=energy;ld.size=size
    light=bpy.data.objects.new(name,ld);scene.collection.objects.link(light);light.location=location
    light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
scene.cycles.samples=20;scene.cycles.use_denoising=True;scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1200;scene.render.resolution_y=1600;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(HERE/'Metric_Camo_Comparison.png')
bpy.ops.render.render(write_still=True)
# Native comparison renders on both sides; keep reference strips readable only
# in the front-side view.
for ob in scene.objects:
    if ob.name.startswith('Rifle-scale reference '):ob.hide_render=True
camera.location=center+Vector((0,.7,.015));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(HERE/'Metric_Camo_Opposite.png');bpy.ops.render.render(write_still=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_sha
assert [tuple(v.co) for v in target.data.vertices]==[tuple(v.co) for v in original.data.vertices]
result=dict(source_blend=str(source),source_sha256=source_sha,geometry_unchanged=True,source_unchanged=True,
    projection_center_yz=[cy,cz],body_radius=radius,source_to_game_world_scale=scale,results=report)
(HERE/'bake_validation.json').write_text(json.dumps(result,indent=2))
print('METRIC_CAMOS_READY',flush=True)
