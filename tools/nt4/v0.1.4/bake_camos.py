"""Bake cylindrical paint onto the unchanged NT4's original game UV layout."""
from pathlib import Path
import bpy, hashlib, json, math
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OUT = HERE / 'GameExport'
OUT.mkdir(exist_ok=True)
source = Path(bpy.data.filepath)
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
rows = json.loads((HERE / 'paint_sources.json').read_text())
original = bpy.data.objects['NEW NT4 - editable replacement']
mesh = original.data.copy()
mesh.uv_layers.active = mesh.uv_layers['UVmap_0']
mesh.uv_layers['UVmap_0'].active_render = True
coords = [v.co.copy() for v in mesh.vertices]
low = Vector([min(p[i] for p in coords) for i in range(3)])
high = Vector([max(p[i] for p in coords) for i in range(3)])
cy, cz = (low.y + high.y) / 2, (low.z + high.z) / 2
paint_uv = mesh.uv_layers.new(name='TEMP Cylindrical Paint')
mesh.calc_loop_triangles()
for poly in mesh.polygons:
    angles = [(math.atan2(mesh.vertices[mesh.loops[li].vertex_index].co.z-cz,
                         mesh.vertices[mesh.loops[li].vertex_index].co.y-cy)/(2*math.pi)) % 1
              for li in poly.loop_indices]
    crossing = max(angles)-min(angles) > .5
    for li, angle in zip(poly.loop_indices, angles):
        if crossing and angle < .5:
            angle += 1
        p = mesh.vertices[mesh.loops[li].vertex_index].co
        paint_uv.data[li].uv = ((p.x-low.x)/(high.x-low.x), angle)
mesh.uv_layers.active = mesh.uv_layers['UVmap_0']
mesh.uv_layers['UVmap_0'].active_render = True

scene = bpy.data.scenes.new('NT4 four camo bake')
target = bpy.data.objects.new('NT4 bake target', mesh)
scene.collection.objects.link(target)
bpy.context.window.scene = scene
target.select_set(True)
scene.view_layers[0].objects.active = target
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
scene.render.bake.margin = 24
scene.render.bake.use_selected_to_active = False
scene.render.bake.use_clear = True
results = []
for row in rows:
    material = bpy.data.materials['NT4 | 01 Original FDE'].copy()
    material.name = 'NT4 | ' + row['slug']
    nodes, links = material.node_tree.nodes, material.node_tree.links
    game_uv = nodes.new('ShaderNodeUVMap'); game_uv.uv_map = 'UVmap_0'
    for node in list(nodes):
        if node.type == 'TEX_IMAGE' and not node.inputs['Vector'].is_linked:
            links.new(game_uv.outputs['UV'], node.inputs['Vector'])
        if node.type == 'NORMAL_MAP':
            node.uv_map = 'UVmap_0'
    uv = nodes.new('ShaderNodeUVMap'); uv.uv_map = paint_uv.name
    scale = nodes.new('ShaderNodeVectorMath'); scale.operation = 'MULTIPLY'
    scale.inputs[1].default_value = (row['axial_repeat'], row['circumference_repeat'], 1)
    links.new(uv.outputs['UV'], scale.inputs[0])
    paint = nodes.new('ShaderNodeTexImage')
    paint.image = bpy.data.images.load(row['paint_path'], check_existing=True)
    paint.image.colorspace_settings.name = 'sRGB'
    paint.extension = 'MIRROR'
    links.new(scale.outputs[0], paint.inputs['Vector'])
    # Neutralize the FDE pigment; retain the original NT4 wear, engraving,
    # dark bore and dirt as a grayscale surface-detail multiplier.
    lum = nodes.new('ShaderNodeRGBToBW')
    links.new(nodes['NT4 BaseColor'].outputs['Color'], lum.inputs[0])
    divide = nodes.new('ShaderNodeMath'); divide.operation = 'DIVIDE'; divide.inputs[1].default_value = .127
    links.new(lum.outputs[0], divide.inputs[0])
    power = nodes.new('ShaderNodeMath'); power.operation = 'POWER'; power.inputs[1].default_value = .70
    links.new(divide.outputs[0], power.inputs[0])
    minimum = nodes.new('ShaderNodeMath'); minimum.operation = 'MINIMUM'; minimum.inputs[1].default_value = 1.5
    links.new(power.outputs[0], minimum.inputs[0])
    mix = nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1
    links.new(paint.outputs['Color'], mix.inputs[1]); links.new(minimum.outputs[0], mix.inputs[2])
    shader = nodes['Principled BSDF']; links.new(mix.outputs[0], shader.inputs['Base Color'])
    emission = nodes.new('ShaderNodeEmission'); links.new(mix.outputs[0], emission.inputs['Color'])
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
    links.new(emission.outputs[0], output.inputs['Surface'])
    image = bpy.data.images.new('nt4_' + row['slug'].lower() + '_d', width=4096, height=4096, alpha=False)
    image.colorspace_settings.name = 'sRGB'
    bake = nodes.new('ShaderNodeTexImage'); bake.image = image; nodes.active = bake
    mesh.materials.clear(); mesh.materials.append(material)
    for poly in mesh.polygons: poly.material_index = 0
    print('BAKING ' + row['slug'], flush=True)
    bpy.ops.object.bake(type='EMIT')
    image.file_format = 'PNG'; image.filepath_raw = str(OUT / (image.name + '.png')); image.save()
    links.new(shader.outputs[0], output.inputs['Surface'])
    # Preview the exact baked diffuse on the original PBR material.
    preview_mat = bpy.data.materials['NT4 | 01 Original FDE'].copy()
    pn, pl = preview_mat.node_tree.nodes, preview_mat.node_tree.links
    p_uv = pn.new('ShaderNodeUVMap'); p_uv.uv_map = 'UVmap_0'
    for node in list(pn):
        if node.type == 'TEX_IMAGE' and not node.inputs['Vector'].is_linked: pl.new(p_uv.outputs[0], node.inputs['Vector'])
        if node.type == 'NORMAL_MAP': node.uv_map = 'UVmap_0'
    pn['NT4 BaseColor'].image = image
    # A diffuse-biased inspection material makes the paint legible; the game
    # retains its existing BGSM normal/specular settings exactly.
    ps = pn['Principled BSDF']
    for socket, value in [('Metallic', .12), ('Roughness', .65)]:
        for link in list(ps.inputs[socket].links): pl.remove(link)
        ps.inputs[socket].default_value = value
    specimen = bpy.data.objects.new('Preview ' + row['slug'], mesh.copy())
    scene.collection.objects.link(specimen)
    specimen.data.materials.clear(); specimen.data.materials.append(preview_mat)
    specimen.location.z = .09 - .06 * len(results)
    results.append(dict(slug=row['slug'], diffuse=image.filepath_raw, vertices=len(mesh.vertices), triangles=len(mesh.polygons)))
target.hide_render = True
scene.world = bpy.data.worlds.new('NT4 camo studio'); scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.13,.16,.20,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
center = Vector(((low.x+high.x)/2,0,0))
camdata = bpy.data.cameras.new('Camo camera'); cam = bpy.data.objects.new('Camo camera', camdata)
scene.collection.objects.link(cam); cam.location = center + Vector((0,-.6,.10))
cam.rotation_euler = (center-cam.location).to_track_quat('-Z','Y').to_euler()
camdata.type='ORTHO';camdata.ortho_scale=.30;camdata.clip_start=.001;scene.camera=cam
for name, loc, energy, size in [('Key',(.06,-.22,.30),5,.3),('Fill',(.08,.14,.10),3,.25),('Front',(.23,-.2,0),1.5,.2)]:
    data=bpy.data.lights.new(name,'AREA'); data.energy=energy;data.size=size
    light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=loc
    light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(HERE/'Camo_Preview.png')
bpy.ops.render.render(write_still=True)
cam.location = center + Vector((0,.6,.10))
cam.rotation_euler = (center-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(HERE/'Camo_Preview_Opposite.png')
bpy.ops.render.render(write_still=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
assert [tuple(v.co) for v in mesh.vertices] == [tuple(v.co) for v in original.data.vertices]
(HERE/'bake_validation.json').write_text(json.dumps(dict(source_blend=str(source),source_sha256=source_hash,
    source_unchanged=True,geometry_unchanged=True,original_game_uv='UVmap_0',results=results),indent=2))
print('FOUR_CAMOS_READY',flush=True)
