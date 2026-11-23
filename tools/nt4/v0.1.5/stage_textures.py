"""Stage only four corrected diffuse maps; retain every material/record byte."""
from pathlib import Path
import hashlib,json,struct,subprocess
from PIL import Image,ImageChops,ImageStat
HERE=Path(__file__).resolve().parent;ROOT=Path(r'C:\Perdition Sector');MOD=ROOT/'mods/MK18 Deluxe (Faust Edit)'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
bake=json.loads((HERE/'bake_validation.json').read_text());aspect=json.loads((HERE/'aspect_validation.json').read_text())
assert bake['source_unchanged'] and aspect['passed']
assert sha(Path(bake['source_blend']))==bake['source_sha256']
prior=json.loads((HERE.parent/'v0.1.4/installation_receipt.json').read_text())
out=HERE/'Staged/Textures/Weapons/MK18/NT4_Repaired';out.mkdir(parents=True,exist_ok=True)
files=[]
for row in bake['results']:
    name='nt4_'+row['slug'].lower()+'_d'
    rel='Textures/Weapons/MK18/NT4_Repaired/'+name+'.DDS';current=MOD/rel
    old=next(o for o in prior['operations'] if o['relative_path'].lower()==rel.lower())
    assert sha(current)==old['installed_sha256']
    source=Path(row['diffuse'])
    r=subprocess.run([str(ROOT/'tools/FO4Edit 4.1.5f/Edit Scripts/Texconv.exe'),'-nologo','-nogpu','-bcquick','-srgb',
        '-f','BC7_UNORM_SRGB','-m','0','-y','-o',str(out),str(source)],capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr
    texture=out/(name+'.DDS');dds=texture.read_bytes()
    assert dds[:4]==b'DDS ' and struct.unpack_from('<II',dds,12)==(4096,4096)
    assert struct.unpack_from('<I',dds,28)[0]==13 and struct.unpack_from('<I',dds,128)[0]==99
    error=ImageStat.Stat(ImageChops.difference(Image.open(source).convert('RGB'),Image.open(texture).convert('RGB'))).mean
    assert max(error)<2,error
    files.append(dict(relative_path=rel,bytes=texture.stat().st_size,before_sha256=sha(current),
        sha256=sha(texture),dds_mean_error_rgb=error))
manifest=dict(version='0.1.5',files=files,texture_only=True,aspect_validation='aspect_validation.json',
    geometry_materials_plugins_unchanged=True,default_rutex_review=aspect['default_rutex_audit'])
(HERE/'staged_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2),flush=True)
