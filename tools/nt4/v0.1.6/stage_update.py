"""Add Splinter and map the exact Desert Hex Black option to existing black."""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
from PIL import Image,ImageChops,ImageStat
HERE=Path(__file__).resolve().parent;ROOT=Path(r'C:\Perdition Sector');MOD=ROOT/'mods/MK18 Deluxe (Faust Edit)'
sys.path.insert(0,str(ROOT/'Development/ModelWorkbench/MK18/v0.1.0'))
from asset_io import Reader,norm,plugin_records,subrecords
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def field(t,d):return t.encode()+struct.pack('<H',len(d))+d
assert json.loads((HERE/'aspect_validation.json').read_text())['passed']
bake=json.loads((HERE/'bake_validation.json').read_text());assert bake['source_unchanged'] and bake['geometry_unchanged']
assert sha(Path(bake['source_blend']))==bake['source_sha256']
stage=HERE/'Staged';texout=stage/'Textures/Weapons/MK18/NT4_Repaired';texout.mkdir(parents=True,exist_ok=True)
source=HERE/'GameExport/nt4_splinter_d.png'
r=subprocess.run([str(ROOT/'tools/FO4Edit 4.1.5f/Edit Scripts/Texconv.exe'),'-nologo','-nogpu','-bcquick','-srgb',
    '-f','BC7_UNORM_SRGB','-m','0','-y','-o',str(texout),str(source)],capture_output=True,text=True)
assert r.returncode==0,r.stdout+r.stderr
texture=texout/'nt4_splinter_d.DDS';dds=texture.read_bytes()
assert dds[:4]==b'DDS ' and struct.unpack_from('<II',dds,12)==(4096,4096)
assert struct.unpack_from('<I',dds,28)[0]==13 and struct.unpack_from('<I',dds,128)[0]==99
error=ImageStat.Stat(ImageChops.difference(Image.open(source).convert('RGB'),Image.open(texture).convert('RGB'))).mean
assert max(error)<2,error
fde=(MOD/'Materials/Weapons/MK18/NT4_Repaired/NT4_FDE.bgsm').read_bytes();rd=Reader(fde);rd.pos=63
assert norm(rd.string()).endswith('nt4_fde_d.dds')
name=b'Weapons\\MK18\\NT4_Repaired\\nt4_splinter_d.dds\0'
material=fde[:63]+struct.pack('<I',len(name))+name+fde[rd.pos:]
mp=stage/'Materials/Weapons/MK18/NT4_Repaired/NT4_Splinter.bgsm';mp.parent.mkdir(parents=True,exist_ok=True);mp.write_bytes(material)
assert (MOD/'Materials/Weapons/MK18/NT4_Repaired/NT4_Black.bgsm').is_file()
original=MOD/'Perdition_NT4_Repaired.esp';records=list(plugin_records(original,{'MSWP','OMOD'}))
rules={'mk18_deluxe.esp:000067':'Weapons\\MK18\\NT4_Repaired\\NT4_Black.bgsm',
       'mk18_deluxe.esp:00006A':'Weapons\\MK18\\NT4_Repaired\\NT4_Splinter.bgsm'}
targets={r['local_id']:rules[r['key']] for r in records if r['key'] in rules};assert len(targets)==2
raw=original.read_bytes();changed=[]
def rewrite(start,end):
    parts=[]
    while start<end:
        sig,size,flags,fid=struct.unpack_from('<4sIII',raw,start);header=raw[start:start+24]
        if sig==b'GRUP':
            body=rewrite(start+24,start+size);parts.append(header[:4]+struct.pack('<I',len(body)+24)+header[8:]+body);start+=size;continue
        body=raw[start+24:start+24+size]
        if sig==b'MSWP' and fid in targets:
            assert not flags&0x40000
            fields=[];selected=False;count=0
            for t,d in subrecords(body):
                if t=='BNAM':selected=norm(d.rstrip(b'\0').decode()) in {
                    'weapons/mk18/attachments/muzzle_suppressor_kac.bgsm','weapons/mk18/attachments/muzzle_suppressor_kac_black.bgsm'}
                elif t=='SNAM' and selected:
                    assert norm(d.rstrip(b'\0').decode())=='weapons/mk18/nt4_repaired/nt4_fde.bgsm'
                    d=targets[fid].encode()+b'\0';count+=1;selected=False
                fields.append((t,d))
            assert count==2;body=b''.join(field(t,d) for t,d in fields);changed.append(fid)
        elif sig==b'TES4':
            body=b''.join(field(t,b'Repaired NT4: rifle-matched Urban/Desert Hex/Brush/Splinter/Black Hex; Desert Hex Black uses black.\0' if t=='SNAM' else d) for t,d in subrecords(body))
        parts.append(header[:4]+struct.pack('<I',len(body))+header[8:]+body);start+=size+24
    assert start==end
    return b''.join(parts)
out=stage/original.name;out.write_bytes(rewrite(0,len(raw)));assert set(changed)==set(targets)
after=list(plugin_records(out,{'MSWP','OMOD'}));assert len(after)==len(records)
checks=[]
for a,b in zip(records,after):
    assert {k:v for k,v in a.items() if k!='fields'}=={k:v for k,v in b.items() if k!='fields'}
    if a['key'] not in rules:assert a['fields']==b['fields'],a['key'];continue
    assert len(a['fields'])==len(b['fields'])
    diff=[i for i,(x,y) in enumerate(zip(a['fields'],b['fields'])) if x!=y]
    assert len(diff)==2
    for i in diff:
        assert a['fields'][i][0]==b['fields'][i][0]=='SNAM'
        assert b['fields'][i][1].rstrip(b'\0').decode()==rules[a['key']]
        assert b['fields'][i-1][0]=='BNAM' and 'suppressor_kac' in norm(b['fields'][i-1][1].decode())
    checks.append(dict(key=a['key'],new_material=rules[a['key']],only_two_suppressor_destinations_changed=True))
manifest=dict(version='0.1.6',base_patch_sha256=sha(original),changed_records=checks,other_records_unchanged=len(records)-2,
    electric_boogaloo_record_unchanged=True,dds_mean_error_rgb=error,
    files=[dict(relative_path=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p),
                before_sha256=sha(MOD/p.relative_to(stage)) if (MOD/p.relative_to(stage)).exists() else None)
           for p in sorted(stage.rglob('*')) if p.is_file()])
assert len(manifest['files'])==3
(HERE/'staged_manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2),flush=True)
