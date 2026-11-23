"""Install the validated local camo update with exact backups and rollback."""
from pathlib import Path
import datetime, hashlib, json, os, shutil, subprocess

HERE=Path(__file__).resolve().parent
ROOT=Path(r'C:\Perdition Sector')
MOD=ROOT/'mods/MK18 Deluxe (Faust Edit)'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert not (HERE/'installation_receipt.json').exists(),'Already installed; inspect receipt before changing files again'
running=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process Fallout4,ModOrganizer -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],capture_output=True,text=True)
assert not running.stdout.strip(),'Close Fallout 4 and Mod Organizer before installation'
manifest=json.loads((HERE/'staged_manifest.json').read_text())
assert sha(MOD/'Perdition_NT4_Repaired.esp')==manifest['base_patch_sha256']
mods=[s[1:] for s in (ROOT/'profiles/FO4ME/modlist.txt').read_text().splitlines() if s.startswith('+')]
def winner(relative):
    over=ROOT/'overwrite'/relative
    if over.exists():return over
    return next((ROOT/'mods'/m/relative for m in mods if (ROOT/'mods'/m/relative).is_file()),None)
assert winner('Perdition_NT4_Repaired.esp')==MOD/'Perdition_NT4_Repaired.esp'
protected={str(p):sha(p) for folder in ['Meshes/Weapons/MK18/Attachments','Materials/Weapons/MK18/NT4_Repaired','Textures/Weapons/MK18/NT4_Repaired']
           for p in (MOD/folder).rglob('*') if p.is_file()}
for name in ['modlist.txt','plugins.txt','loadorder.txt','Fallout4.ini','Fallout4Prefs.ini','Fallout4Custom.ini']:
    p=ROOT/'profiles/FO4ME'/name
    if p.exists():protected[str(p)]=sha(p)
for name in ['Muzzle_Suppressor_KAC.BGSM','Muzzle_Suppressor_KAC_Black.BGSM']:
    p=MOD/'Materials/Weapons/MK18/Attachments'/name;protected[str(p)]=sha(p)
status=HERE.parent/'CURRENT_STATUS.json'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%SZ')
backup=HERE/'Backup'/stamp;backup.mkdir(parents=True)
shutil.copy2(status,backup/'CURRENT_STATUS.json')
operations=[]
for row in manifest['files']:
    relative=row['relative_path'];src=HERE/'Staged'/relative;dst=MOD/relative
    assert sha(src)==row['sha256']
    assert dst==MOD/'Perdition_NT4_Repaired.esp' or not dst.exists(),str(dst)
    assert winner(relative) in {None,dst},str(winner(relative))
    saved=backup/relative if dst.exists() else None
    if saved:saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,saved)
    operations.append(dict(relative_path=relative,path=str(dst),staged=str(src),before_sha256=sha(dst) if dst.exists() else None,
                           installed_sha256=row['sha256'],backup_path=str(saved) if saved else None))
receipt=dict(version='0.1.4',state='prepared',installed_utc=stamp,operations=operations,protected_hashes=protected,
             status_backup=str(backup/'CURRENT_STATUS.json'),geometry_and_alignment_unchanged=True,
             material_swap_validation=manifest['changed_records'],game_visual_confirmation='pending user test',github_published=False,
             previous_finish_receipt=str(HERE.parent/'v0.1.2/installation_receipt.json'),
             previous_geometry_receipt=str(HERE.parent/'v0.1.3/installation_receipt.json'),
             paint_behavior={'default':'Existing corrected RUTex', 'BLK':'Existing black NT4',
                 'Urban':'Matching rifle Urban camo','Desert Hex':'Matching rifle Desert Hex camo',
                 'Brush':'Matching rifle Brush camo',
                 'Desert Hex Black 2 Electric Boogaloo':'Matching rifle Black Hex camo',
                 'remaining_paints':'Existing FDE behavior'})
(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
done=[]
try:
    for op in operations:
        dst=Path(op['path']);dst.parent.mkdir(parents=True,exist_ok=True)
        tmp=dst.with_name(dst.name+'.nt4_camo_install.tmp');assert not tmp.exists()
        shutil.copy2(op['staged'],tmp);os.replace(tmp,dst);done.append(op)
        assert sha(dst)==op['installed_sha256']
    for path,digest in protected.items():assert sha(Path(path))==digest,path
    for op in operations:assert winner(op['relative_path'])==Path(op['path'])
    receipt['state']='complete'
    (HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
    current=json.loads(status.read_text())
    current.update(version='0.1.4',status='installed_locally_pending_visual_test',receipt=str(HERE/'installation_receipt.json'),
        changed_game_files=9,previous_geometry_version='0.1.3',geometry_and_alignment_unchanged=True,
        camo_paints=['Urban','Desert Hex','Brush','Desert Hex Black 2 Electric Boogaloo'],
        github_published=False,previous_published_version='0.1.3')
    for key in ['repository_commit','update_id']:current.pop(key,None)
    status.write_text(json.dumps(current,indent=2))
except Exception:
    for op in reversed(done):
        dst=Path(op['path'])
        if op['backup_path']:shutil.copy2(op['backup_path'],dst)
        elif dst.exists():dst.unlink()
    receipt['state']='rolled_back_after_error'
    (HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
    raise
print(json.dumps(dict(state=receipt['state'],installed_files=len(operations),protected_files_verified=len(protected),
                      paints=current['camo_paints'],game_visual_confirmation=receipt['game_visual_confirmation']),indent=2))
