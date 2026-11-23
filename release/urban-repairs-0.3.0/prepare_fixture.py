from pathlib import Path
import hashlib,json,re,shutil,zipfile
ROOT=Path(r'C:\Perdition Sector');HERE=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    build=json.loads((HERE/'build_manifest.json').read_text());index=json.loads((HERE/'beta-v2.candidate.json').read_text())
    menu_path='mods/Perdition New Game - Test/Interface/PSNewGameMenu.swf'
    data=(ROOT/menu_path).read_bytes();before='95fec9e0119674b0c3f52458d9f55beeebfe1f232c2507abb4342d16b80bc955'
    assert sha(data)=='aa302b7c89b9fdb2ee9d2d0f829e0748588140ead4bc581fca8607f7424b349b'
    archive=HERE/'Perdition_Intro_Viewport_v0.1.17.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        info=zipfile.ZipInfo(menu_path,(2026,11,23,12,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
    payload=archive.read_bytes();blob=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
    update={'id':'intro-viewport-0.1.17','name':'Intro menu visible-viewport layout correction','minimum_updater_version':'0.2.3-beta.1','url':f'https://github.com/jjc71ps4/Perdition-Sector/releases/download/{build["tag"]}/{archive.name}','bytes':len(payload),'sha256':sha(payload),'files':[{'path':menu_path,'bytes':len(data),'sha256':sha(data),'previous_sha256':before}]}
    index['updates']=[u for u in index['updates'] if u['id']!=update['id']]+[update]
    build['artifacts']=[a for a in build['artifacts'] if a['filename']!=archive.name]+[{'filename':archive.name,'bytes':len(payload),'sha256':sha(payload),'chunks':[{'offset':0,'bytes':len(payload),'sha256':sha(payload),'git_sha':blob}]}]
    build['ultrawide_menu_included']=True;build['ultrawide_native_test']='pending 5120x1440 in-game confirmation';build['update_ids']=[u['id'] for u in index['updates'][3:]];build['payload_files']=sum(len(u['files']) for u in index['updates'][3:])
    (HERE/'build_manifest.json').write_text(json.dumps(build,indent=2)+'\n');(HERE/'beta-v2.candidate.json').write_text(json.dumps(index,indent=2)+'\n')
    fixture=Path(r'C:\workspace\Perdition_Urban_Update_Fixture_030');assert not fixture.exists();fixture.mkdir()
    published={f['path']:f for u in index['updates'][:3] for f in u['files']}
    for rel,row in published.items():
        src=ROOT/rel;assert sha(src.read_bytes())==row['sha256'],rel;dest=fixture/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    old_menu=ROOT/'Development/NewGame/Backups/Viewport_20261123_160551Z/PSNewGameMenu.swf';assert sha(old_menu.read_bytes())==before
    dest=fixture/menu_path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old_menu,dest)
    profile=fixture/'profiles/FO4ME';profile.mkdir(parents=True);backup=ROOT/'Development/Performance/Backups/Lexington_20261123_150526Z'
    for name in ['modlist.txt','plugins.txt','loadorder.txt']:shutil.copy2(backup/name,profile/name)
    prefs=(ROOT/'profiles/FO4ME/fallout4prefs.ini').read_text();prefs=re.sub(r'(?im)^iSize W=.*$', 'iSize W=5120',prefs);prefs=re.sub(r'(?im)^iSize H=.*$','iSize H=1440',prefs);(profile/'fallout4prefs.ini').write_text(prefs)
    (profile/'saves').mkdir();(profile/'saves/keep.fos').write_bytes(b'personal save fixture');(fixture/'ModOrganizer.exe').write_bytes(b'non-executed fixture')
    (HERE/'fixture.json').write_text(json.dumps({'root':str(fixture),'previous_updates_already_current':True,'menu_expected_predecessor_verified':True},indent=2))
    print('Fixture ready; channel entries',len(index['updates']),'payload files',build['payload_files'])
if __name__=='__main__':main()
