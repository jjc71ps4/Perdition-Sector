"""Install the validated, reversible Concord candidate into the FO4ME profile."""
from datetime import datetime,timezone
import hashlib,json,os,shutil
from stage_concord import *
from concord_pipeline import PACKAGE
PROFILE=ROOT/'profiles/FO4ME'
def atomic(path,data):
    temp=path.with_name(path.name+'.concord.tmp');temp.write_bytes(data);os.replace(temp,path)
def install():
    assert not (HERE/'installation.json').exists(),'Candidate is already installed'
    build=json.loads((HERE/'build_manifest.json').read_text());stage=json.loads((BUILD/'stage.json').read_text())
    assert build['material_validation']['all_variants_verified'] and build['stale_deleted_refs_excluded']==74
    assert len(build['cells'])==20 and not build['native_build_errors'] and build['final_reference_records']==0
    assert digest(PACKAGE/NAME)==build['plugin_sha256']
    for rel,meta in build['assets'].items():assert digest(PACKAGE/rel)==meta['sha256']
    lex=json.loads((HERE.parent/'v0.2.0/build_manifest.json').read_text());assert not set(lex['assets'])&set(build['assets']),'Concord assets overlap the accepted Lexington repair'
    for n,expected in build['source_hashes'].items():assert digest(Path(stage['paths'][n]))==expected,'An input plugin changed during the rebuild: '+n
    paths=[PROFILE/n for n in ['modlist.txt','plugins.txt','loadorder.txt']];before={p:p.read_bytes() for p in paths};after={}
    for p,data in before.items():
        assert NAME.encode() not in data and MOD.encode() not in data
        assert b'PSLexingtonOptimization.esp' in before[PROFILE/'plugins.txt']
        nl=b'\r\n' if b'\r\n' in data else b'\n'
        if p.name=='modlist.txt':
            lines=data.splitlines(keepends=True);assert lines[0].startswith(b'#');after[p]=lines[0]+b'+'+MOD.encode()+nl+b''.join(lines[1:])
        else:after[p]=data.rstrip(b'\r\n')+nl+(b'*' if p.name=='plugins.txt' else b'')+NAME.encode()+nl
    protected=list(PROFILE.glob('*.ini'))+list((PROFILE/'saves').glob('*.fos'))+[ROOT/'overwrite/Perdition Sector World.esp',ROOT/'mods/Perdition Lexington Optimization - Test/PSLexingtonOptimization.esp',ROOT/'mods/Perdition North End Visibility - Test/Perdition North End Visibility - Test.esp']
    hashes={str(p):digest(p) for p in protected};stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ');backup=ROOT/'Development/Performance/Backups'/('Concord_'+stamp);dest=ROOT/'mods'/MOD
    assert not dest.exists() and dest.resolve().is_relative_to((ROOT/'mods').resolve());backup.mkdir(parents=True)
    for p,data in before.items():(backup/p.name).write_bytes(data)
    try:
        shutil.copytree(PACKAGE,dest)
        for p,data in after.items():assert p.read_bytes()==before[p];atomic(p,data)
        for p,expected in hashes.items():assert digest(Path(p))==expected,p
        for rel,meta in build['assets'].items():assert digest(dest/rel)==meta['sha256'],rel
        assert digest(dest/NAME)==build['plugin_sha256']
        result={'mod':MOD,'plugin':NAME,'plugin_sha256':build['plugin_sha256'],'installed_utc':stamp,'profile':'FO4ME','backup':str(backup),'enabled':True,'plugin_last':True,'cells':20,'assets':len(build['assets']),'source_world_and_saves_unchanged':True,'lexington_and_north_end_unchanged':True,'protected_files':hashes,'profile_before':{p.name:hashlib.sha256(v).hexdigest() for p,v in before.items()},'profile_after':{p.name:digest(p) for p in paths},'runtime_tested':False}
        (HERE/'installation.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in {'protected_files','profile_before','profile_after'}},indent=2))
    except BaseException:
        for p,data in before.items():atomic(p,data)
        if dest.exists():shutil.move(str(dest),str(backup/'IncompleteCandidate'))
        raise
if __name__=='__main__':install()
