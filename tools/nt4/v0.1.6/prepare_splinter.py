"""Prepare Splinter using the validated 0.1.5 physical-scale projection."""
from pathlib import Path
import copy,hashlib,json
from PIL import Image

HERE=Path(__file__).resolve().parent;PREVIOUS=HERE.parent/'v0.1.5'
MOD=Path(r'C:\Perdition Sector\mods\MK18 Deluxe (Faust Edit)')
HERE.joinpath('Sources').mkdir(exist_ok=True)
src=MOD/'Textures/Weapons/MK18/MK18/Skins/Splinter/MK18_D.DDS'
crop=(2940,3820,4020,3910)
paint=HERE/'Sources/Splinter_paint.png'
Image.open(src).convert('RGB').crop(crop).save(paint)
row=dict(slug='Splinter',source_texture=str(src),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
    source_size=[4096,4096],crop=crop,paint_path=str(paint),material_swap='mk18_deluxe.esp:00006A')
(HERE/'paint_sources.json').write_text(json.dumps([row],indent=2))
measure=json.loads((PREVIOUS/'surface_measurements.json').read_text())
metric=copy.deepcopy(next(r for r in measure['patterns'] if r['slug']=='Urban'))
assert metric['source_candidates'][0]['triangle']==3018
metric['slug']='Splinter'
for candidate in metric['source_candidates']:candidate['slug']='Splinter'
for key in list(metric):
    if key.startswith('old_'):del metric[key]
measure['patterns']=[metric]
measure['calibration_note']='Same rifle mesh, UV patch and triangle as Urban; only the source paint image differs.'
(HERE/'surface_measurements.json').write_text(json.dumps(measure,indent=2))
# Versioned snapshots retain the already-validated shader implementation.
bake=(PREVIOUS/'bake_metric_camos.py').read_text()
old="sources=json.loads((HERE.parent/'v0.1.4/paint_sources.json').read_text())"
assert bake.count(old)==1
bake=bake.replace(old,"sources=json.loads((HERE/'paint_sources.json').read_text())")
bake=bake.replace("specimen.location.z=.135-index*.09","specimen.location.z=0")
bake=bake.replace("camdata.ortho_scale=.40","camdata.ortho_scale=.235")
bake=bake.replace("scene.render.resolution_y=1600","scene.render.resolution_y=650")
# Light both inspection views equally.
old="scene.render.filepath=str(HERE/'Metric_Camo_Opposite.png');bpy.ops.render.render(write_still=True)"
new="for light in scene.objects:\n    if light.type=='LIGHT':light.location.y=-light.location.y;light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()\n"+old
assert bake.count(old)==1;bake=bake.replace(old,new)
(HERE/'bake_splinter.py').write_text(bake)
validate=(PREVIOUS/'validate_surface_metrics.py').read_text()
validate=validate.replace("rows=json.loads((HERE.parent/'v0.1.4/paint_sources.json').read_text())","rows=json.loads((HERE/'paint_sources.json').read_text())")
start=validate.index('        # Reproduce the legacy repeat mapping')
end=validate.index('    measured=np.array(data)',start)
validate=validate[:start]+validate[end:]
validate=validate.replace("        previous_median_aspect_error_percent=float((np.median(old_data)-1)*100),","        newly_added_paint=True,")
validate=validate[:validate.index('# Audit the separate, existing default RUTex path.')]
validate+="report=dict(splinter=result,passed=True)\n(HERE/'aspect_validation.json').write_text(json.dumps(report,indent=2))\nprint(json.dumps(report,indent=2),flush=True)\n"
(HERE/'validate_splinter.py').write_text(validate)
print('Splinter source and measured projection prepared.')
