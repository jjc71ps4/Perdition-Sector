"""Install a validated Lexington candidate without altering the source world mod."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,shutil
from stage_lexington import ROOT,HERE,GAME,BASE,NAME,digest
from finish_lexington import MOD,PACKAGE
PROFILE=ROOT/'profiles/FO4ME'

def atomic(path,data):
    temp=path.with_name(path.name+'.lexington.tmp');temp.write_bytes(data);os.replace(temp,path)
def install():
    assert not (HERE/'installation.json').exists(),'Already installed'
    build=json.loads((HERE/'build_manifest.json').read_text())
    assert build['material_variant_checks']['all_190_resolved']
    assert digest(PACKAGE/NAME)==build['plugin_sha256']
    for rel,meta in build['assets'].items():assert digest(PACKAGE/rel)==meta['sha256'],rel
    for p in [PROFILE/'modlist.txt',PROFILE/'plugins.txt',PROFILE/'loadorder.txt']:assert MOD.encode() not in p.read_bytes() and NAME.encode() not in p.read_bytes()
    enabled=[s[1:] for s in (PROFILE/'modlist.txt').read_text(encoding='utf-8-sig').splitlines() if s.startswith('+')]
    providers={}
    for folder in [ROOT/'overwrite']+[ROOT/'mods'/n for n in enabled]+[GAME/'Data']:
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in {'.esm','.esp','.esl'}:providers.setdefault(p.name.lower(),p)
    for name,expected in build['source_hashes'].items():assert digest(providers[name.lower()])==expected,'Source changed during rebuild: '+name
    protected=[p for p in PROFILE.glob('*.ini')]+list((PROFILE/'saves').glob('*.fos'))
    protected += [ROOT/'overwrite/Perdition Sector World.esp',ROOT/'mods/Perdition North End Visibility - Test/Perdition North End Visibility - Test.esp']
    hashes={str(p):digest(p) for p in protected}
    paths=[PROFILE/n for n in ['modlist.txt','plugins.txt','loadorder.txt']];before={p:p.read_bytes() for p in paths};after={}
    for p,data in before.items():
        nl=b'\r\n' if b'\r\n' in data else b'\n'
        if p.name=='modlist.txt':
            lines=data.splitlines(keepends=True);assert lines[0].startswith(b'#');after[p]=lines[0]+b'+'+MOD.encode()+nl+b''.join(lines[1:])
        else:after[p]=data.rstrip(b'\r\n')+nl+(b'*' if p.name=='plugins.txt' else b'')+NAME.encode()+nl
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ');backup=ROOT/'Development/Performance/Backups'/('Lexington_'+stamp);dest=ROOT/'mods'/MOD
    assert not dest.exists() and dest.resolve().is_relative_to((ROOT/'mods').resolve())
    backup.mkdir(parents=True)
    for p,data in before.items():(backup/p.name).write_bytes(data)
    try:
        shutil.copytree(PACKAGE,dest)
        for p,data in after.items():
            assert p.read_bytes()==before[p],'Profile changed during installation';atomic(p,data)
        for p,expected in hashes.items():assert digest(Path(p))==expected,'Protected file changed: '+p
        assert digest(dest/NAME)==build['plugin_sha256']
        for rel,meta in build['assets'].items():assert digest(dest/rel)==meta['sha256'],rel
        receipt={'mod':MOD,'plugin':NAME,'installed_utc':stamp,'backup':str(backup),'plugin_sha256':build['plugin_sha256'],'enabled':True,'plugin_last':True,'assets':len(build['assets']),'cells':len(build['cells']),'runtime_tested':False,'original_world_and_saves_unchanged':True,'protected_files':hashes,'profile_before':{p.name:__import__('hashlib').sha256(v).hexdigest() for p,v in before.items()},'profile_after':{p.name:digest(p) for p in paths}}
        (HERE/'installation.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps({k:v for k,v in receipt.items() if k not in {'protected_files','profile_before','profile_after'}},indent=2))
    except BaseException:
        for p,data in before.items():atomic(p,data)
        if dest.exists():shutil.move(str(dest),str(backup/'IncompleteCandidate'))
        raise

if __name__=='__main__':install()
