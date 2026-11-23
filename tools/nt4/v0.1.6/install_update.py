"""Back up and install only the two requested paint adjustments."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=Path(r'C:\Perdition Sector');MOD=ROOT/'mods/MK18 Deluxe (Faust Edit)'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not (HERE/'installation_receipt.json').exists(),'Inspect the existing receipt before rerunning'
p=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process Fallout4,ModOrganizer -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],capture_output=True,text=True)
assert not p.stdout.strip(),'Close Fallout 4 and MO2 before installation'
manifest=json.loads((HERE/'staged_manifest.json').read_text());changes={str((MOD/r['relative_path']).resolve()).lower() for r in manifest['files']}
assert sha(MOD/'Perdition_NT4_Repaired.esp')==manifest['base_patch_sha256']
protected={str(p):sha(p) for folder in ['Meshes/Weapons/MK18/Attachments','Materials/Weapons/MK18/Attachments',
    'Materials/Weapons/MK18/NT4_Repaired','Textures/Weapons/MK18/NT4_Repaired'] for p in (MOD/folder).rglob('*')
    if p.is_file() and str(p.resolve()).lower() not in changes}
for name in ['modlist.txt','plugins.txt','loadorder.txt','Fallout4.ini','Fallout4Prefs.ini','Fallout4Custom.ini']:
    p=ROOT/'profiles/FO4ME'/name
    if p.exists():protected[str(p)]=sha(p)
mods=[s[1:] for s in (ROOT/'profiles/FO4ME/modlist.txt').read_text().splitlines() if s.startswith('+')]
def winner(rel):
    p=ROOT/'overwrite'/rel
    if p.exists():return p
    return next((ROOT/'mods'/m/rel for m in mods if (ROOT/'mods'/m/rel).is_file()),None)
status=HERE.parent/'CURRENT_STATUS.json';current=json.loads(status.read_text());assert current['version']=='0.1.5'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%SZ');backup=HERE/'Backup'/stamp;backup.mkdir(parents=True)
shutil.copy2(status,backup/'CURRENT_STATUS.json');operations=[]
for row in manifest['files']:
    rel=row['relative_path'];src=HERE/'Staged'/rel;dst=MOD/rel
    assert dst.resolve().is_relative_to(MOD.resolve()) and sha(src)==row['sha256']
    assert (sha(dst) if dst.exists() else None)==row['before_sha256']
    assert winner(rel) in {None,dst},str(winner(rel))
    saved=backup/rel if dst.exists() else None
    if saved:saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,saved)
    operations.append(dict(relative_path=rel,path=str(dst),staged=str(src),before_sha256=row['before_sha256'],
        installed_sha256=row['sha256'],backup_path=str(saved) if saved else None))
receipt=dict(version='0.1.6',state='prepared',installed_utc=stamp,operations=operations,protected_hashes=protected,
    status_backup=str(backup/'CURRENT_STATUS.json'),previous_receipt=str(HERE.parent/'v0.1.5/installation_receipt.json'),
    behavior={'Desert Hex Black':'Existing plain black suppressor','Splinter':'New rifle-matched metric Splinter camo',
              'Desert Hex Black 2 Electric Boogaloo':'Existing Black Hex pattern retained'},
    aspect_validation=json.loads((HERE/'aspect_validation.json').read_text()),changed_records=manifest['changed_records'],
    game_visual_confirmation='pending user test',github_published=False)
(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2));done=[]
try:
    for op in operations:
        dst=Path(op['path']);dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name(dst.name+'.splinter_install.tmp');assert not tmp.exists()
        shutil.copy2(op['staged'],tmp);os.replace(tmp,dst);done.append(op)
        assert sha(dst)==op['installed_sha256'] and winner(op['relative_path'])==dst
    for p,h in protected.items():assert sha(Path(p))==h,p
    receipt['state']='complete';(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
    current.update(version='0.1.6',status='installed_locally_pending_visual_test',receipt=str(HERE/'installation_receipt.json'),
        changed_game_files=3,previous_finish_version='0.1.5',texture_only=False,github_published=False,
        camo_paints=['Urban','Desert Hex','Brush','Splinter','Desert Hex Black 2 Electric Boogaloo'],
        desert_hex_black_finish='Plain black')
    status.write_text(json.dumps(current,indent=2))
except Exception:
    for op in reversed(done):
        if op['backup_path']:shutil.copy2(op['backup_path'],op['path'])
        else:Path(op['path']).unlink()
    shutil.copy2(backup/'CURRENT_STATUS.json',status)
    receipt['state']='rolled_back_after_error';(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2));raise
print(json.dumps(dict(installed_files=len(operations),protected_files_verified=len(protected),behavior=receipt['behavior']),indent=2),flush=True)
