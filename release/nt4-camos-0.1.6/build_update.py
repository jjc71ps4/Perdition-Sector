"""Package the approved final NT4 finishes over the current published channel."""
from pathlib import Path
import datetime,hashlib,json,shutil,zipfile
HERE=Path(__file__).resolve().parent;ROOT=Path(r'C:\Perdition Sector')
WORK=ROOT/'Development/ModelWorkbench/NT4_Replacement';PUBLIC=HERE/'Public'
PREFIX='release/nt4-camos-0.1.6/';TAG='updates-2026.11.23.2';UPDATE='nt4-camos-0.1.6'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(path,content):
    p=PUBLIC/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8',newline='\n');return p
def main():
    status=json.loads((WORK/'CURRENT_STATUS.json').read_text());assert status['version']=='0.1.6'
    final={}
    for version in ['0.1.4','0.1.5','0.1.6']:
        receipt=json.loads((WORK/('v'+version)/'installation_receipt.json').read_text())
        assert receipt['state']=='complete' and receipt['game_visual_confirmation']=='approved by user'
        for op in receipt['operations']:final[op['relative_path']]=op
    assert len(final)==11
    previous=(HERE/'Remote/beta-v2.json').read_bytes();baseline=json.loads(previous)
    published={f['path']:f for u in baseline['updates'] for f in u['files']}
    assert UPDATE not in {u['id'] for u in baseline['updates']}
    archive=HERE/'Perdition_NT4_Camos_v0.1.6.zip';definitions=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for rel,op in sorted(final.items()):
            src=ROOT/'mods/MK18 Deluxe (Faust Edit)'/rel;data=src.read_bytes();assert sha(data)==op['installed_sha256']
            name=src.relative_to(ROOT).as_posix();old=published.get(name)
            assert src.suffix.lower() in {'.dds','.bgsm','.esp'}
            info=zipfile.ZipInfo(name,(2026,11,23,12,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data)
            definitions.append(dict(path=name,bytes=len(data),sha256=sha(data),previous_sha256=old['sha256'] if old else ''))
    assert sum(bool(f['previous_sha256']) for f in definitions)==1
    assert next(f for f in definitions if f['path'].endswith('.esp'))['previous_sha256']=='aec7d2a7b5644843a2d2de04cdabebedf899eccc1931e0100b25645adcda962a'
    with zipfile.ZipFile(archive) as z:assert len(z.namelist())==11 and z.testzip() is None
    data=archive.read_bytes();chunks=[]
    for off in range(0,len(data),3*1024**2):
        part=data[off:off+3*1024**2]
        chunks.append(dict(offset=off,bytes=len(part),sha256=sha(part),git_sha=hashlib.sha1(b'blob '+str(len(part)).encode()+b'\0'+part).hexdigest()))
    update=dict(id=UPDATE,name='Approved NT4 matching camos and preserved pattern proportions',minimum_updater_version='0.2.3-beta.1',
        url=f'https://github.com/jjc71ps4/Perdition-Sector/releases/download/{TAG}/{archive.name}',bytes=len(data),sha256=sha(data),files=definitions)
    index={**baseline,'updates':baseline['updates']+[update]}
    (HERE/'beta-v2.candidate.json').write_text(json.dumps(index,indent=2)+'\n')
    notes='''# Approved NT4 camo finishes 0.1.6

- Propagate Urban, Desert Hex, Brush, Splinter, and Desert Hex Black 2 Electric Boogaloo onto the repaired NT4 suppressor.
- Match each source rifle pattern's physical scale and proportions. Measured main-body aspect error is below 0.25%; flat end caps use planar mapping.
- Desert Hex Black uses the existing plain black NT4 finish. Electric Boogaloo remains the separate Black Hex pattern.
- Retain the approved mesh alignment, original surface detail, default RUTex, FDE and BLK finishes.

These changes were tested and approved in game by the player on November 23, 2026.

Existing players: close Fallout 4 and MO2, then run **Update Perdition Sector.cmd**.
New installations receive this update automatically through the current channel.
The existing setup/updater already supports it; no new installer is required.

The update contains five diffuse maps, five materials, and the existing ESL-flagged
NT4 paint patch. No NIF, profile, save, gameplay balance, or base snapshot changes.
Files are size/SHA-256 verified and backed up by the updater. Ordinary clones hold
the source, manifests and receipts; the playable assets are a release download.
'''
    write(PREFIX+'RELEASE_NOTES.md',notes)
    readme=(HERE/'Remote/README.md').read_text()
    old='- Default RUTex camo with the confirmed brown-tone correction; Black/BLK uses\n  black, and the other paint options use original FDE.'
    new='- Approved rifle-matched NT4 Urban, Desert Hex, Brush, Splinter and Black Hex\n  camos with preserved pattern proportions and scale. Desert Hex Black and\n  Black/BLK use plain black; default RUTex and remaining FDE options are retained.'
    assert old in readme;readme=readme.replace(old,new)
    readme=readme.replace('## Latest revisions\n','## Latest revisions\n\n- Player-approved NT4 camo propagation, pattern proportions and Desert Hex Black finish.\n')
    write(PREFIX+'README.next.md',readme)
    channel=(HERE/'Remote/CHANNEL_README.md').read_text()
    old='Current NT4 finishes are default RUTex with the confirmed brown-tone correction,\nblack for Black/BLK, and original FDE for the other paints.'
    new='Current NT4 finishes include rifle-matched Urban, Desert Hex, Brush, Splinter\nand Black Hex patterns with preserved proportions and physical scale. Desert Hex\nBlack and Black/BLK use plain black. Default RUTex and remaining FDE paints are retained.'
    assert old in channel;channel=channel.replace(old,new)
    channel+='\n\nThe nt4-camos-0.1.6 entry contains the player-approved final camo textures, materials and paint mappings. It combines the November 23 camo work through Splinter, with the aspect-ratio correction, as one update over the published NT4 patch. It adds no profile migration and needs no installer rebuild.\n'
    write(PREFIX+'CHANNEL_README.next.md',channel)
    write(PREFIX+'beta-v2.candidate.json',json.dumps(index,indent=2)+'\n')
    # Keep the current publisher/workflow intact. Its established trigger reads
    # this transport path, but publication receipts and notes use the new version.
    transport=dict(tag=TAG,title='Perdition Sector - approved NT4 camos and pattern proportions',notes_file=PREFIX+'RELEASE_NOTES.md',
        channel_candidate=PREFIX+'beta-v2.candidate.json',publication_receipt=PREFIX+'publication.json',
        readme_candidate=PREFIX+'README.next.md',channel_readme_candidate=PREFIX+'CHANNEL_README.next.md',
        expected_channel_sha256=sha(previous),retain_transport=True,commit_message='Publish approved NT4 camos and pattern proportions',
        artifacts=[dict(filename=archive.name,bytes=len(data),sha256=sha(data),chunks=chunks)])
    write('release/revisions-0.2.3/transport.json',json.dumps(transport,indent=2)+'\n')
    (HERE/'transport.json').write_text(json.dumps(transport,indent=2)+'\n')
    summary=dict(update_id=UPDATE,tag=TAG,archive=str(archive),archive_bytes=len(data),archive_sha256=sha(data),
        files=definitions,artifacts=transport['artifacts'],previous_channel_sha256=sha(previous),approved_by_user=True,
        installer_update_required=False,base_archive_reuploaded=False)
    (HERE/'build_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    write(PREFIX+'build_manifest.json',json.dumps(summary,indent=2)+'\n')
    write(PREFIX+'build_update.py',Path(__file__).read_text())
    for version in ['v0.1.4','v0.1.5','v0.1.6']:
        folder=WORK/version
        selected=list(folder.glob('*.py'))
        for p in selected:write('tools/nt4/'+version+'/'+p.name,p.read_text())
        for name in ['README.md','paint_sources.json','surface_measurements.json','aspect_validation.json','bake_validation.json']:
            p=folder/name
            if p.exists():write('tools/nt4/'+version+'/'+name,p.read_text())
    for name in ['asset_io.py','nif_geometry.py']:
        write('tools/nt4/shared/'+name,(ROOT/'Development/ModelWorkbench/MK18/v0.1.0'/name).read_text())
    write('tools/nt4/README.md','''# NT4 authoring sources

These are versioned sources for the approved camo work in the existing Perdition
development workspace. The authoring scripts expect the original development
directory layout and the saved MK18_RISII_NT4_Replacement.blend; the Blender file
is an authoring input and is not included in this repository. Shared NIF/plugin
readers are supplied in shared/ for the Development/ModelWorkbench/MK18/v0.1.0
location used by the scripts. The original rifle and NT4 source textures come
from the installed build. Run the v0.1.4 source preparation, v0.1.5 measured bake,
then v0.1.6 Splinter preparation/bake as documented in their READMEs. Historical
install scripts intentionally reject mismatched or already-modified predecessors.
Players should use Update Perdition Sector.cmd rather than these authoring tools.
''')
    write(PREFIX+'user_acceptance.json',json.dumps(dict(approved=True,user_message='changes approved, please push these to the git',
        versions=['0.1.4','0.1.5','0.1.6'],approved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
    print(json.dumps(dict(update=UPDATE,files=len(definitions),archive_bytes=len(data),chunks=len(chunks),sha256=sha(data)),indent=2))
if __name__=='__main__':main()
