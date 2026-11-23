"""Install the texture-only aspect correction with exact-version backups."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=Path(r'C:\Perdition Sector');MOD=ROOT/'mods/MK18 Deluxe (Faust Edit)'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not (HERE/'installation_receipt.json').exists(),'Inspect existing installation before rerunning'
running=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process Fallout4,ModOrganizer -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],capture_output=True,text=True)
assert not running.stdout.strip(),'Close game and MO2 before replacing textures'
manifest=json.loads((HERE/'staged_manifest.json').read_text());assert manifest['texture_only']
changes={str((MOD/r['relative_path']).resolve()).lower() for r in manifest['files']}
protected={str(p):sha(p) for folder in ['Meshes/Weapons/MK18/Attachments','Materials/Weapons/MK18/NT4_Repaired',
    'Materials/Weapons/MK18/Attachments','Textures/Weapons/MK18/NT4_Repaired'] for p in (MOD/folder).rglob('*')
    if p.is_file() and str(p.resolve()).lower() not in changes}
protected[str(MOD/'Perdition_NT4_Repaired.esp')]=sha(MOD/'Perdition_NT4_Repaired.esp')
for name in ['modlist.txt','plugins.txt','loadorder.txt','Fallout4.ini','Fallout4Prefs.ini','Fallout4Custom.ini']:
    p=ROOT/'profiles/FO4ME'/name
    if p.exists():protected[str(p)]=sha(p)
mods=[s[1:] for s in (ROOT/'profiles/FO4ME/modlist.txt').read_text().splitlines() if s.startswith('+')]
def winner(rel):
    p=ROOT/'overwrite'/rel
    if p.exists():return p
    return next((ROOT/'mods'/m/rel for m in mods if (ROOT/'mods'/m/rel).is_file()),None)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%SZ')
backup=HERE/'Backup'/stamp;backup.mkdir(parents=True)
status=HERE.parent/'CURRENT_STATUS.json';current=json.loads(status.read_text());assert current['version']=='0.1.4'
shutil.copy2(status,backup/'CURRENT_STATUS.json')
operations=[]
for row in manifest['files']:
    rel=row['relative_path'];src=HERE/'Staged'/rel;dst=MOD/rel
    assert dst.resolve().is_relative_to(MOD.resolve()) and src.exists()
    assert sha(src)==row['sha256'] and sha(dst)==row['before_sha256']
    assert winner(rel)==dst,str(winner(rel))
    saved=backup/rel;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,saved)
    operations.append(dict(path=str(dst),relative_path=rel,staged=str(src),backup_path=str(saved),
        before_sha256=row['before_sha256'],installed_sha256=row['sha256']))
receipt=dict(version='0.1.5',state='prepared',installed_utc=stamp,operations=operations,protected_hashes=protected,
    previous_receipt=str(HERE.parent/'v0.1.4/installation_receipt.json'),status_backup=str(backup/'CURRENT_STATUS.json'),
    user_feedback_on_0_1_4='Near perfect colors; requested all pattern aspect ratios be preserved and matched to rifle',
    texture_only=True,aspect_validation=json.loads((HERE/'aspect_validation.json').read_text()),
    game_visual_confirmation='pending user test',github_published=False)
(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
done=[]
try:
    for op in operations:
        dst=Path(op['path']);tmp=dst.with_name(dst.name+'.aspect_install.tmp');assert not tmp.exists()
        shutil.copy2(op['staged'],tmp);os.replace(tmp,dst);done.append(op)
        assert sha(dst)==op['installed_sha256'] and winner(op['relative_path'])==dst
    for p,h in protected.items():assert sha(Path(p))==h,p
    receipt['state']='complete';(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
    current.update(version='0.1.5',status='installed_locally_pending_aspect_visual_test',receipt=str(HERE/'installation_receipt.json'),
        changed_game_files=4,previous_finish_version='0.1.4',texture_only=True,source_rifle_metric_matched=True,
        geometry_and_alignment_unchanged=True,github_published=False)
    status.write_text(json.dumps(current,indent=2))
except Exception:
    for op in reversed(done):shutil.copy2(op['backup_path'],op['path'])
    shutil.copy2(backup/'CURRENT_STATUS.json',status)
    receipt['state']='rolled_back_after_error';(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
    raise
print(json.dumps(dict(installed_files=len(operations),protected_files_verified=len(protected),
    texture_only=True,game_visual_confirmation=receipt['game_visual_confirmation']),indent=2),flush=True)
