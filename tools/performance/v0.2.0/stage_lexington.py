"""Create an isolated CK input tree. Never edit or hardlink mutable source plugins."""
from pathlib import Path
import hashlib,json,os,shutil,struct,sys,zlib
ROOT=Path(r'C:\Perdition Sector')
GAME=Path(r'C:\_Fallout 4')
HERE=Path(__file__).resolve().parent
BUILD=Path(r'C:\workspace\perdition-lexington-build-20261123')
sys.path.insert(0,str(HERE.parent/'v0.1.1'))
from build_visibility_test import records,fields,sub,encoded,walk_count
NAME='PSLexingtonOptimization.esp'
BASE=['Fallout4.esm','DLCRobot.esm','DLCworkshop01.esm','DLCCoast.esm','DLCworkshop02.esm','DLCworkshop03.esm','DLCNukaWorld.esm']

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def group(label,kind,body):return struct.pack('<4sI4siIHH',b'GRUP',24+len(body),label,kind,0,0,0)+body
def scoped(data,targets):
    """Yield raw records belonging to selected cells, skipping other payloads."""
    pos=0;stack=[];cell=None
    while pos<len(data):
        while stack and pos>=stack[-1][0]:stack.pop()
        h=data[pos:pos+24];sig,size,flags,fid=struct.unpack_from('<4sIII',h)
        if sig==b'GRUP':
            typ=struct.unpack_from('<i',h,12)[0]
            stack.append((pos+size,typ,struct.unpack_from('<I',h,8)[0]));pos+=24;continue
        cell=next((v for _,t,v in reversed(stack) if t==6),None)
        if sig==b'TES4' or sig==b'CELL' and fid in targets or cell in targets and sig==b'REFR':
            blob=data[pos+24:pos+24+size]
            if flags&0x40000:blob=zlib.decompress(blob[4:])
            yield {'sig':sig.decode(),'fid':fid,'flags':flags,'header':h,'blob':blob,'fields':list(fields(blob)),'cell':cell}
        pos+=24+size
    assert pos==len(data)

def main():
    assert not (BUILD/'stage.json').exists(),'Already staged'
    facts=json.loads(Path(r'C:\workspace\perdition-lexington-audit-20261123\findings.json').read_text())
    targets={int(c['cell'].split(':')[1],16) for c in facts['cells']}
    enabled=[s[1:] for s in (ROOT/'profiles/FO4ME/modlist.txt').read_text(encoding='utf-8-sig').splitlines() if s.startswith('+')]
    active=[s[1:] for s in (ROOT/'profiles/FO4ME/plugins.txt').read_text(encoding='utf-8-sig').splitlines() if s.startswith('*')]
    order=BASE+[n for n in active if n.lower() not in {s.lower() for s in BASE}]
    assert len(order)<250
    folders=[ROOT/'overwrite']+[ROOT/'mods'/n for n in enabled]+[GAME/'Data']
    providers={}
    for folder in folders:
        for p in folder.rglob('*'):
            if p.is_file():providers.setdefault(p.relative_to(folder).as_posix().lower(),p)
    paths={n:providers[n.lower()] for n in order}
    # A copied, otherwise untouched vanilla reference triggers each selected CELL.
    # Choose references that no active non-vanilla plugin overrides.
    overrides=set()
    for n in order[len(BASE):]:
        for r in scoped(paths[n].read_bytes(),targets):
            if r['sig']=='TES4':
                masters=[v.rstrip(b'\0').decode().lower() for t,v in r['fields'] if t=='MAST']
            elif r['sig']=='REFR' and r['fid']>>24<len(masters) and masters[r['fid']>>24]=='fallout4.esm':overrides.add(r['fid']&0xffffff)
    triggers={}
    for r in scoped(paths[BASE[0]].read_bytes(),targets):
        if r['sig']=='REFR' and r['fid'] not in overrides and not r['flags']&(0x20|0x800):triggers.setdefault(r['cell'],r)
    assert set(triggers)==targets
    source_cache={}
    replacements={}
    for c in facts['cells']:
        p=paths[c['winner']]
        if p not in source_cache:source_cache[p]={r['fid']:r for r in scoped(p.read_bytes(),targets) if r['sig']=='CELL'}
        r=source_cache[p][int(c['cell'].split(':')[1],16)]
        # Audited CELL FormID fields all belong to Fallout4.esm (index zero).
        for t,v in r['fields']:
            if t in {'RVIS','LTMP','XCLR','XLCN','XPRI'}:
                assert all(x>>24==0 for x, in struct.iter_unpack('<I',v)),(c['cell'],t)
            if t=='XCRI':
                meshes,count=struct.unpack_from('<II',v)
                assert all(x>>24==0 for x,y in struct.iter_unpack('<II',v[8+meshes*4:])),c['cell']
        replacements[r['fid']]=encoded(r)+group(struct.pack('<I',r['fid']),6,group(struct.pack('<I',r['fid']),9,encoded(triggers[r['fid']])))
    world=paths['Perdition Sector World.esp'].read_bytes()
    wrld=next(r for r in records(world) if r['sig']=='WRLD' and r['fid']==0x3c)
    for t,v in wrld['fields']:
        if t in {'XLCN','CNAM','NAM2','NAM3','ZNAM'}:assert struct.unpack('<I',v)[0]>>24==0
    boston=paths['BostonFPSFixAIO.esp'].read_bytes()
    def filter_tree(start,end):
        out=[]
        while start<end:
            h=boston[start:start+24];sig,size,flags,fid=struct.unpack_from('<4sIII',h)
            if sig==b'GRUP':
                body=filter_tree(start+24,start+size)
                if body:out.append(h[:4]+struct.pack('<I',24+len(body))+h[8:]+body)
                start+=size;continue
            if sig==b'WRLD' and fid==0x3c:out.append(encoded(wrld))
            elif sig==b'CELL' and fid in replacements:out.append(replacements[fid])
            start+=24+size
        return b''.join(out)
    body=filter_tree(0,len(boston))
    assert sum(r['sig']=='CELL' for r in records(body))==18
    blob=sub('HEDR',struct.pack('<fII',1.,walk_count(body),0x800))+sub('CNAM',b'Perdition Sector\0')+sub('SNAM',b'Lexington optimization rebuild; preserve current world geometry\0')
    for n in order:blob+=sub('MAST',n.encode()+b'\0')+sub('DATA',b'\0'*8)
    seed=struct.pack('<4sIIIIHH',b'TES4',len(blob),0,0,0,131,0)+blob+body
    (BUILD/'Data').mkdir(parents=True,exist_ok=True)
    # Native tool binaries/configuration are independent copies. No ENB/F4SE hooks.
    dlls=['bink2w64.dll','cudart64_75.dll','d3dcompiler_46.dll','d3dcompiler_46e.dll','flexExtRelease_x64.dll','flexRelease_x64.dll','flowchartx32.dll','flowchartx64.dll','GFSDK_GodraysLib.x64.dll','GFSDK_SSAO_D3D11.win64.dll','msvcp110.dll','msvcr110.dll','nvToolsExt64_1.dll','ssce5564.dll','steam_api64.dll','VoltekLib.Detours.dll','VoltekLib.MemoryManager.dll','VoltekLib.RelocationDatabase.dll','VoltekLib.UnicodeConverter.dll','winhttp.dll']
    names=['CreationKit.exe','CreationKit.ini','CreationKitCustom.ini','CreationKitPrefs.ini','CreationKitPlatformExtended.ini','Fallout4_Default.ini']+dlls
    names += [p.name for p in GAME.glob('CreationKitPlatformExtended*.pak')]
    names += [p.name for p in GAME.glob('CreationKitPlatformExtended*.database')]
    names += ['CreationKitPlatformExtendedMessagesBlacklist.txt','ckpe_loader.exe']
    for n in names:
        if (GAME/n).is_file():shutil.copy2(GAME/n,BUILD/n)
    pe=BUILD/'CreationKitPlatformExtended.ini'
    text=pe.read_text();text=text.replace('bBSPointerHandleExtremly=false','bBSPointerHandleExtremly=true').replace('sOutputFile=none','sOutputFile=CKBuild.log').replace('bShowWindow=true','bShowWindow=false');pe.write_text(text)
    (BUILD/'steam_appid.txt').write_text('1946160\n')
    # Independent geometry/material input copies. Texture archives are excluded
    # for memory/disk headroom; visibility generation does not need textures.
    linked=0;copied=0
    for rel,p in providers.items():
        suffix=p.suffix.lower()
        if suffix in {'.esm','.esp','.esl'}:
            if rel in {n.lower() for n in order}:shutil.copy2(p,BUILD/'Data'/p.name);copied+=1
            continue
        root=rel.split('/')[0]
        texture_archive='textures' in p.name.lower() and suffix=='.ba2'
        voice_archive=any(s in p.name.lower() for s in ['voices','sounds','animations','startup','nvflex']) and suffix=='.ba2'
        if ('/' not in rel and suffix in {'.ba2','.csg','.cdx'} and not texture_archive and not voice_archive) or root in {'meshes','materials'}:
            dest=BUILD/'Data'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest);copied+=1
    (BUILD/'Data'/NAME).write_bytes(seed)
    # Copied plugin timestamps express the exact active priority to the editor.
    for i,n in enumerate(order+[NAME]):os.utime(BUILD/'Data'/n,(1700000000+i*10,1700000000+i*10))
    (BUILD/'plugins.txt').write_text('\n'.join('*'+n for n in order+[NAME])+'\n')
    manifest={'plugin':NAME,'source_hashes':{n:digest(p) for n,p in paths.items()},'order':order,'targets':sorted(targets),'trigger_refs':{f'{k:08X}':f'{r["fid"]:08X}' for k,r in triggers.items()},'linked_readonly_assets':linked,'copied_inputs':copied,'seed_sha256':digest(BUILD/'Data'/NAME)}
    (BUILD/'stage.json').write_text(json.dumps(manifest,indent=2))
    (HERE/'build_location.txt').write_text(str(BUILD)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in {'source_hashes','order'}},indent=2))

if __name__=='__main__':main()
