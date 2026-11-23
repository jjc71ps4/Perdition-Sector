from pathlib import Path
import hashlib,json,re,shutil
HERE=Path(__file__).resolve().parent;ROOT=Path(r'C:\Perdition Sector')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
build=json.loads((HERE/'build_manifest.json').read_text());index=json.loads((HERE/'beta-v2.candidate.json').read_text())
fixture=Path(r'C:\workspace\Perdition_NT4_Camos_Fixture_016');assert not fixture.exists();fixture.mkdir()
previous={f['path']:f for u in index['updates'][:-1] for f in u['files']}
oldpatch=next(p for p in (ROOT/'Development/ModelWorkbench/NT4_Replacement/v0.1.4/Backup').rglob('Perdition_NT4_Repaired.esp')
    if sha(p)=='aec7d2a7b5644843a2d2de04cdabebedf899eccc1931e0100b25645adcda962a')
for name,row in previous.items():
    src=oldpatch if name.endswith('/Perdition_NT4_Repaired.esp') else ROOT/name
    assert sha(src)==row['sha256'],name
    dst=fixture/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
world=fixture/'overwrite/Perdition Sector World.esp';world.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'overwrite/Perdition Sector World.esp',world)
profile=fixture/'profiles/FO4ME';profile.mkdir(parents=True)
for name in ['modlist.txt','plugins.txt','loadorder.txt']:shutil.copy2(ROOT/'profiles/FO4ME'/name,profile/name)
prefs=(ROOT/'profiles/FO4ME/fallout4prefs.ini').read_text()
prefs=re.sub(r'(?im)^iSize W=.*$','iSize W=5120',prefs);prefs=re.sub(r'(?im)^iSize H=.*$','iSize H=1440',prefs)
(profile/'fallout4prefs.ini').write_text(prefs)
(profile/'saves').mkdir();(profile/'saves/keep.fos').write_bytes(b'personal save fixture')
(fixture/'ModOrganizer.exe').write_bytes(b'non-executed fixture')
(HERE/'fixture.json').write_text(json.dumps(dict(root=str(fixture),baseline_files=len(previous)),indent=2))
print('Prepared published-channel fixture with',len(previous),'verified files.')
