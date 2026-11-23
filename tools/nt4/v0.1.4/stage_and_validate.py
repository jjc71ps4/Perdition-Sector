"""Create four game materials and narrowly update their existing paint swaps."""
from pathlib import Path
import hashlib, json, struct, subprocess, sys

HERE = Path(__file__).resolve().parent
ROOT = Path(r'C:\Perdition Sector')
MOD = ROOT / 'mods/MK18 Deluxe (Faust Edit)'
sys.path.insert(0, str(ROOT / 'Development/ModelWorkbench/MK18/v0.1.0'))
from asset_io import Reader, norm, plugin_records, subrecords

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def field(tag, data): return tag.encode() + struct.pack('<H', len(data)) + data

rows = json.loads((HERE / 'paint_sources.json').read_text())
bake = json.loads((HERE / 'bake_validation.json').read_text())
assert bake['source_unchanged'] and bake['geometry_unchanged']
assert sha(Path(bake['source_blend'])) == bake['source_sha256']
stage = HERE / 'Staged'
texout = stage / 'Textures/Weapons/MK18/NT4_Repaired'
matout = stage / 'Materials/Weapons/MK18/NT4_Repaired'
texout.mkdir(parents=True, exist_ok=True); matout.mkdir(parents=True, exist_ok=True)
fde = (MOD / 'Materials/Weapons/MK18/NT4_Repaired/NT4_FDE.bgsm').read_bytes()
reader = Reader(fde); reader.pos = 63
old = reader.string(); remainder = fde[reader.pos:]
assert norm(old).endswith('nt4_fde_d.dds')
patch = MOD / 'Perdition_NT4_Repaired.esp'
before = list(plugin_records(patch, {'MSWP', 'OMOD'}))
targets = {}
for row in rows:
    assert sha(Path(row['source_texture'])) == row['source_sha256']
    name = 'nt4_' + row['slug'].lower() + '_d'
    result = subprocess.run([str(ROOT/'tools/FO4Edit 4.1.5f/Edit Scripts/Texconv.exe'), '-nologo', '-nogpu',
        '-bcquick', '-srgb', '-f', 'BC7_UNORM_SRGB', '-m', '0', '-y', '-o', str(texout),
        str(HERE/'GameExport'/(name+'.png'))], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    dds = texout / (name + '.dds'); data = dds.read_bytes()
    assert data[:4] == b'DDS '
    assert struct.unpack_from('<II', data, 12) == (4096,4096)
    assert struct.unpack_from('<I', data, 28)[0] == 13
    assert data[84:88] == b'DX10' and struct.unpack_from('<I',data,128)[0] == 99
    diffuse = ('Weapons\\MK18\\NT4_Repaired\\' + name + '.dds\0').encode()
    material = fde[:63] + struct.pack('<I',len(diffuse)) + diffuse + remainder
    mr = Reader(material); mr.pos = 63; maps = [mr.string() for _ in range(9)]
    fr = Reader(fde); fr.pos = 63; previous = [fr.string() for _ in range(9)]
    assert maps[1:] == previous[1:] and material[mr.pos:] == fde[fr.pos:]
    material_name = 'NT4_' + row['slug'] + '.bgsm'
    (matout / material_name).write_bytes(material)
    record = next(r for r in before if r['key'] == row['material_swap'])
    targets[record['local_id']] = dict(row, replacement='Weapons\\MK18\\NT4_Repaired\\' + material_name)

raw = patch.read_bytes(); changes = []
def rewrite(start,end):
    chunks=[]
    while start < end:
        sig,size,flags,fid=struct.unpack_from('<4sIII',raw,start)
        header=raw[start:start+24]
        if sig == b'GRUP':
            body=rewrite(start+24,start+size)
            chunks.append(header[:4]+struct.pack('<I',len(body)+24)+header[8:]+body)
            start+=size;continue
        body=raw[start+24:start+24+size]
        if sig == b'MSWP' and fid in targets:
            assert not flags & 0x40000
            fields=list(subrecords(body)); selected=False; count=0; result=[]
            for tag,value in fields:
                if tag=='BNAM':
                    selected=norm(value.rstrip(b'\0').decode()) in {
                        'weapons/mk18/attachments/muzzle_suppressor_kac.bgsm',
                        'weapons/mk18/attachments/muzzle_suppressor_kac_black.bgsm'}
                elif tag=='SNAM' and selected:
                    assert norm(value.rstrip(b'\0').decode())=='weapons/mk18/nt4_repaired/nt4_fde.bgsm'
                    value=targets[fid]['replacement'].encode()+b'\0';count+=1;selected=False
                result.append((tag,value))
            assert count==2
            body=b''.join(field(t,d) for t,d in result);changes.append(fid)
        elif sig == b'TES4':
            fields=list(subrecords(body))
            assert any(t=='SNAM' for t,d in fields)
            body=b''.join(field(t,b'Repaired NT4: RUTex default, BLK black, matching Urban/Desert Hex/Brush/Black Hex; other paints FDE.\0' if t=='SNAM' else d) for t,d in fields)
        chunks.append(header[:4]+struct.pack('<I',len(body))+header[8:]+body)
        start+=24+size
    assert start==end
    return b''.join(chunks)
output=stage/patch.name;output.write_bytes(rewrite(0,len(raw)))
assert set(changes)==set(targets) and len(changes)==4
after=list(plugin_records(output,{'MSWP','OMOD'}))
assert len(before)==len(after)
checks=[]
for a,b in zip(before,after):
    assert {k:v for k,v in a.items() if k not in {'fields'}} == {k:v for k,v in b.items() if k not in {'fields'}}
    if a['local_id'] not in targets:
        assert a['fields']==b['fields'],a['key']
        continue
    assert len(a['fields'])==len(b['fields'])
    differences=[(i,t) for i,((t,d),(tt,dd)) in enumerate(zip(a['fields'],b['fields'])) if (t,d)!=(tt,dd)]
    assert len(differences)==2 and all(t=='SNAM' for i,t in differences)
    for i,t in differences:
        assert b['fields'][i-1][0]=='BNAM'
        assert 'suppressor_kac' in norm(b['fields'][i-1][1].decode().rstrip('\0'))
        assert b['fields'][i][1].rstrip(b'\0').decode()==targets[a['local_id']]['replacement']
    checks.append(dict(key=a['key'],slug=targets[a['local_id']]['slug'],only_two_suppressor_replacements_changed=True))
manifest=dict(version='0.1.4',base_patch_sha256=sha(patch),unchanged_record_count=len(before)-4,
    changed_records=checks,geometry_and_alignment_unchanged=True,normal_and_specular_maps_unchanged=True,
    files=[dict(relative_path=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(stage.rglob('*')) if p.is_file()])
assert len(manifest['files'])==9
(HERE/'staged_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
