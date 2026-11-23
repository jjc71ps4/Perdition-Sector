"""Package only the user-confirmed Lexington and Concord runtime assets."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,struct,zipfile
ROOT=Path(r'C:\Perdition Sector');HERE=Path(__file__).resolve().parent;TAG='updates-2026.11.23.1'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    baseline_bytes=(HERE/'Remote/beta-v2.json').read_bytes();baseline=json.loads(baseline_bytes)
    assert hashlib.sha1(b'blob '+str(len(baseline_bytes)).encode()+b'\0'+baseline_bytes).hexdigest()=='9d68b0933550da81bb33b4670bbfe87772395aef'
    inventory=json.loads((ROOT/'Development/Distribution/Private/Beta-2026.11.20.1/snapshot_inventory.json').read_text());published={r['path'].lower():r for r in inventory}
    for update in baseline['updates']:
        for row in update['files']:published[row['path'].lower()]=row
    additions=[];artifacts=[];proof=[]
    for version,area in [('0.2.0','Lexington'),('0.3.0','Concord')]:
        work=ROOT/'Development/Performance'/('v'+version);build=json.loads((work/'build_manifest.json').read_text());receipt=json.loads((work/'installation.json').read_text());mod=ROOT/'mods'/build['mod'];assert sha((mod/build['plugin']).read_bytes())==build['plugin_sha256']
        acceptance={'version':version,'user_confirmed':True,'confirmation':'confirmed you fixed lexington' if area=='Lexington' else 'fixes confirmed, can we push these to the git','recorded_utc':datetime.now(timezone.utc).isoformat(),'plugin_sha256':build['plugin_sha256'],'numeric_fps_benchmark_supplied':False}
        (work/'user_acceptance.json').write_text(json.dumps(acceptance,indent=2))
        files=[];archive=HERE/f'Perdition_{area}_Repair_v{version}.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for p in sorted(mod.rglob('*')):
                if not p.is_file():continue
                rel=p.relative_to(ROOT).as_posix();inside=p.relative_to(mod).as_posix();data=p.read_bytes()
                assert rel.lower() not in published,'Unexpected pre-existing published path: '+rel
                if inside not in {build['plugin'],'meta.ini'}:assert inside in build['assets'] and sha(data)==build['assets'][inside]['sha256'],inside
                info=zipfile.ZipInfo(rel,(2026,11,23,12,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
                files.append({'path':rel,'bytes':len(data),'sha256':sha(data),'previous_sha256':''});published[rel.lower()]=files[-1]
        with zipfile.ZipFile(archive) as z:assert z.testzip() is None
        data=archive.read_bytes();chunks=[]
        for offset in range(0,len(data),3*1024**2):
            chunk=data[offset:offset+3*1024**2];chunks.append({'offset':offset,'bytes':len(chunk),'sha256':sha(chunk),'git_sha':hashlib.sha1(b'blob '+str(len(chunk)).encode()+b'\0'+chunk).hexdigest()})
        update={'id':area.lower()+'-repair-'+version,'name':f'Confirmed {area} geometry and visibility repair','minimum_updater_version':'0.2.3-beta.1','url':f'https://github.com/jjc71ps4/Perdition-Sector/releases/download/{TAG}/{archive.name}','bytes':len(data),'sha256':sha(data),'files':files,'profile_changes':{'schema_version':1,'enable_mods':[build['mod']],'disable_mods':[],'enable_plugins':[build['plugin']],'settings':[]}}
        additions.append(update);artifacts.append({'filename':archive.name,'bytes':len(data),'sha256':sha(data),'chunks':chunks})
        proof.append({'area':area,'cells':len(build['cells']),'plugin_sha256':build['plugin_sha256'],'user_confirmed':True,'asset_count':len(build['assets']),'native_build_errors':build['native_build_errors'] if 'native_build_errors' in build else [],'gameplay_or_ini_edits':False})
    channel={**baseline,'updates':baseline['updates']+additions};(HERE/'beta-v2.candidate.json').write_text(json.dumps(channel,indent=2)+'\n')
    allowed={Path(p).name.lower() for p in published if p.endswith(('.esp','.esm','.esl'))}|{n.lower() for n in ['Fallout4.esm','DLCRobot.esm','DLCworkshop01.esm','DLCCoast.esm','DLCworkshop02.esm','DLCworkshop03.esm','DLCNukaWorld.esm']}
    import sys
    sys.path.insert(0,str(ROOT/'Development/Performance/v0.1.1'));from build_visibility_test import records
    for update in additions:
        plugin=next(r for r in update['files'] if r['path'].endswith('.esp'));header=next(records((ROOT/plugin['path']).read_bytes()));masters=[v.rstrip(b'\0').decode() for t,v in header['fields'] if t=='MAST'];assert {m.lower() for m in masters}<=allowed,sorted({m.lower() for m in masters}-allowed)
    result={'tag':TAG,'base_snapshot_reuploaded':False,'installer_update_required':False,'minimum_updater':'0.2.3-beta.1','previous_channel_sha256':sha(baseline_bytes),'repairs':proof,'update_ids':[u['id'] for u in additions],'artifacts':artifacts,'payload_files':sum(len(u['files']) for u in additions),'all_plugin_masters_available_in_published_chain':True,'ultrawide_menu_included':False}
    (HERE/'build_manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in {'artifacts','repairs'}},indent=2));print('archives',[(a['filename'],a['bytes'],len(a['chunks'])) for a in artifacts])
if __name__=='__main__':main()
