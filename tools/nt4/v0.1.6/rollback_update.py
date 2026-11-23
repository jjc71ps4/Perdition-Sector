from pathlib import Path
import hashlib,json,shutil,subprocess
HERE=Path(__file__).resolve().parent
receipt=json.loads((HERE/'installation_receipt.json').read_text());assert receipt['state']=='complete'
running=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process Fallout4,ModOrganizer -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],capture_output=True,text=True)
assert not running.stdout.strip(),'Close Fallout 4 and MO2'
for op in receipt['operations']:assert hashlib.sha256(Path(op['path']).read_bytes()).hexdigest()==op['installed_sha256']
for op in reversed(receipt['operations']):
    if op['backup_path']:shutil.copy2(op['backup_path'],op['path'])
    else:Path(op['path']).unlink()
shutil.copy2(receipt['status_backup'],HERE.parent/'CURRENT_STATUS.json')
receipt['state']='rolled_back';(HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2))
print('Restored previous paint mappings and removed the two Splinter assets.')
