from pathlib import Path
import hashlib,json,shutil,subprocess
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'installation_receipt.json').read_text());assert r['state']=='complete'
p=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process Fallout4,ModOrganizer -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],capture_output=True,text=True)
assert not p.stdout.strip(),'Close game and MO2'
for op in r['operations']:assert hashlib.sha256(Path(op['path']).read_bytes()).hexdigest()==op['installed_sha256']
for op in r['operations']:shutil.copy2(op['backup_path'],op['path'])
shutil.copy2(r['status_backup'],HERE.parent/'CURRENT_STATUS.json')
r['state']='rolled_back';(HERE/'installation_receipt.json').write_text(json.dumps(r,indent=2))
print('Restored the previous four camo textures.')
