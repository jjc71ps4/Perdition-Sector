"""Build the Windows setup executable and a small, reproducible setup ZIP.

Authoring tool only. End users do not need Python. Bulk game/mod data is kept
separate and is prepared with Build-Payload.ps1.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile

HERE=Path(__file__).resolve().parent

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    manifest=json.loads((HERE/'release.json').read_text(encoding='utf-8-sig'))
    if manifest.get('full_package_verification',True) is False and manifest.get('status') not in {'debug_test_candidate','beta_snapshot'}:
        raise RuntimeError('Production releases must enable full package verification')
    if sha(HERE/'RootOverlay.zip')!=manifest['root_overlay_sha256']:
        raise RuntimeError('The gameplay overlay does not match this setup release')
    csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    automation=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/assembly/GAC_MSIL/System.Management.Automation/v4.0_3.0.0.0__31bf3856ad364e35/System.Management.Automation.dll'
    subprocess.run([str(csc),'/nologo','/target:winexe','/platform:x64','/optimize+',
                    '/reference:System.Windows.Forms.dll','/reference:'+str(automation),'/out:'+str(HERE/'PerditionSetup.exe'),
                    str(HERE/'SetupBootstrap.cs')],check=True)
    files=[]
    for name in ['PerditionSetup.exe','Setup.ps1','SetupBootstrap.cs','Build-Payload.ps1',
                 'build_release.py','README.md','release.json','RootOverlay.zip',
                 'update_source.json','Update existing Perdition.cmd']:
        files.append(HERE/name)
    for folder in ['Core','Tools','Documentation']:
        files.extend(path for path in (HERE/folder).rglob('*') if path.is_file())
    files.extend(path for path in (HERE/'Tests').glob('*.ps1') if path.is_file())
    for path in files:
        if not path.is_file():raise FileNotFoundError(path)
    if manifest.get('status')=='beta_snapshot':
        source=HERE/'package_source.json'
        if not source.is_file():raise RuntimeError('The beta installer must include its completed snapshot download manifest')
        package=json.loads(source.read_text(encoding='utf-8-sig'))
        if package['version']!=manifest.get('payload_version',manifest['version']) or not package['parts']:
            raise RuntimeError('The beta download manifest does not match the installer version')
        files.append(source)
    output=args.output or HERE/('Perdition_Sector_Installer_v'+manifest['version']+'_Beta.zip')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(files):archive.write(path,path.relative_to(HERE))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise RuntimeError('Setup ZIP verification failed')
    result={'archive':str(output),'bytes':output.stat().st_size,'sha256':sha(output),
            'runtime':manifest['runtime'],'f4se':manifest['f4se'],'enb_default':False,
            'full_package_verification':manifest.get('full_package_verification',True),
            'complete_authenticated_install_tested':False}
    output.with_suffix('.receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
