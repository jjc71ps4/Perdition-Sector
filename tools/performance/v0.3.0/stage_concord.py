"""Stage a twenty-cell Concord rebuild in an independent Creation Kit tree."""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime
import hashlib,json,os,shutil,struct,sys,zlib
ROOT=Path(r'C:\Perdition Sector');GAME=Path(r'C:\_Fallout 4');HERE=Path(__file__).resolve().parent
BUILD=Path(r'C:\workspace\perdition-concord-build-20261123');AUDIT=Path(r'C:\workspace\perdition-concord-audit-20261123')
NAME='PSConcordOptimization.esp';MOD='Perdition Concord Optimization - Test'
INTERIORS={0x17DF7,0x3776D};CENTERS={0xDDBE,0xDE21};PREVIS_TRIGGERS=INTERIORS|CENTERS
sys.path.insert(0,str(HERE.parent/'v0.1.1'))
from build_visibility_test import records,fields,sub,encoded,walk_count
sys.path.insert(0,str(HERE.parent/'v0.2.0'))
from stage_lexington import scoped,group
from merge_lexington import mapped_field,replace_fields,reset_count,transform_tree
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(fid,ms,name):return (ms[fid>>24] if fid>>24<len(ms) else name).lower()+':'+f'{fid&0xffffff:06X}'
def head_masters(data):return [v.rstrip(b'\0').decode() for t,v in next(records(data))['fields'] if t=='MAST']
def mapper(ms,name,order):
    names=[n.lower() for n in order]
    def remap(fid):
        if not fid:return 0
        owner=ms[fid>>24] if fid>>24<len(ms) else name
        return names.index(owner.lower())<<24|fid&0xffffff
    return remap
def map_array(v,remap):return b''.join(struct.pack('<I',remap(x)) for x, in struct.iter_unpack('<I',v))
def remap_record(r,remap,kind):
    singles={'NAME','XMSP','XLYR','XLRL','XLRT','XEZN','XLCN','XEMI','XOWN','XGLB','INAM'} if kind=='REFR' else {'LTMP','XCLR','XLCN','RVIS','XCIM','XEZN','XCMO','XCWT','XCCM','XCAS'} if kind=='CELL' else {'XLCN','CNAM','NAM2','NAM3','ZNAM','WNAM'}
    out=[]
    for t,v in r['fields']:
        if t in singles:v=map_array(v,remap)
        elif kind=='CELL' and t in {'XPRI','XCRI'}:v=mapped_field(t,v,remap)
        elif kind=='REFR' and t=='XLKR':v=map_array(v,remap)
        elif kind=='REFR' and t in {'XESP','XAPR'}:v=struct.pack('<I',remap(struct.unpack_from('<I',v)[0]))+v[4:]
        elif kind=='REFR':
            allowed={'DATA','XSCL','XALP','XIS2','XRDS','XLIG','XPRM','XAPD','XLOD','XRGD','XRGB','XWPG','XWCU','XCVL','XCVR','XHTW','XHLP','XHRT','XCLP','XMBR','XACT','XTRI','XTNM'}
            assert t in allowed,('Unhandled build-only REFR field',hex(r['fid']),t)
        out.append((t,v))
    h=r['header'];fid=remap(r['fid']);h=h[:12]+struct.pack('<I',fid)+h[16:]
    return dict(r,header=h,fid=fid,blob=b''.join(sub(t,v) for t,v in out),fields=out)

def main():
    assert not (BUILD/'stage.json').exists(),'Already staged'
    state=json.loads((AUDIT/'record_state.json').read_text());order=state['order'];paths={n:Path(p) for n,p in state['paths'].items()};assert len(order)<250
    active=[s[1:] for s in (ROOT/'profiles/FO4ME/plugins.txt').read_text(encoding='utf-8-sig').splitlines() if s.startswith('*')]
    assert {n.lower() for n in active}<={n.lower() for n in order} and len(active)==len(order)-7
    for n,p in paths.items():assert digest(p)==state['source_hashes'][n],'Source changed since Concord audit: '+n
    selected={k:c for k,c in state['cells'].items() if c[-1][1]['grid'] is not None or int(k.split(':')[1],16) in INTERIORS}
    targets={int(k.split(':')[1],16) for k in selected};assert len(targets)==20
    allmasters={};rawrefs={};rawcells={};original_cells={};triggers={}
    affected_bases={chain[-1][1]['base'] for k,chain in state['refs'].items() if chain[-1][1]['parent'] in selected and not chain[-1][1]['deleted'] and not chain[-1][1]['disabled']}
    base_records={};block_previs=None
    # Resolve base material swaps against the same complete active load order.
    for name in order:
        data=paths[name].read_bytes();ms=head_masters(data);allmasters[name]=ms;pos=0
        while pos<len(data):
            h=data[pos:pos+24];sig,size,flags,fid=struct.unpack_from('<4sIII',h)
            if sig==b'GRUP':pos+=24;continue
            k=canonical(fid,ms,name)
            if sig in {b'STAT',b'SCOL'} and k in affected_bases or sig==b'LCRT' and block_previs is None:
                blob=data[pos+24:pos+24+size]
                if flags&0x40000:blob=zlib.decompress(blob[4:])
                d=dict(fields(blob))
                if sig==b'LCRT' and d.get('EDID',b'').rstrip(b'\0').lower() in {b'blockprevis',b'noprecombinereftype'}:block_previs=canonical(fid,ms,name)
                if sig in {b'STAT',b'SCOL'}:
                    swap=struct.unpack('<I',d['MODS'])[0] if len(d.get('MODS',b''))==4 else 0
                    base_records[k]={'sig':sig.decode(),'model':d.get('MODL',b'').rstrip(b'\0').decode(),'swap':canonical(swap,ms,name) if swap else None}
            pos+=24+size
        if name=='Fallout4.esm':
            overridden={k for k,c in state['refs'].items() if any(n!='Fallout4.esm' for n,r in c)}
            for r in scoped(data,targets):
                k=canonical(r['fid'],ms,name)
                if r['sig']=='REFR' and k not in overridden and not r['flags']&(0x20|0x800|0x400):triggers.setdefault(r['cell'],r)
        for r in scoped(data,targets):
            k=canonical(r['fid'],ms,name)
            if r['sig']=='CELL' and k in selected and selected[k][-1][0]==name:rawcells[r['fid']]=remap_record(r,mapper(ms,name,order),'CELL');original_cells[k]={'plugin':name,'fields_sha256':hashlib.sha256(r['blob']).hexdigest()}
            elif r['sig']=='REFR' and k in state['refs'] and state['refs'][k][-1][0]==name:rawrefs[k]=(name,r)
    assert set(rawcells)==targets and set(triggers)==targets
    build_refs=defaultdict(list);variants=[];alpha_exclusions=[]
    for k,(name,r) in rawrefs.items():
        win=state['refs'][k][-1][1]
        if win['parent'] not in selected or win['deleted'] or win['disabled']:continue
        obj=base_records.get(win['base']);d=dict(r['fields'])
        if not obj:continue
        swap=obj['swap'] if not any(d.get('XMSP',b'')) else None
        alpha_override='XALP' in d
        if not swap and not alpha_override:continue
        copy=remap_record(r,mapper(allmasters[name],name,order),'REFR');updates={}
        if swap:
            owner,local=swap.split(':');updates['XMSP']=struct.pack('<I',[n.lower() for n in order].index(owner)<<24|int(local,16))
            variants.append({'ref':k,'cell':win['parent'],'swap':swap,'base':win['base'],'model':obj['model']})
        if alpha_override:
            assert block_previs,'No BlockPrevis location type found';owner,local=block_previs.split(':');updates['XLRT']=struct.pack('<I',[n.lower() for n in order].index(owner)<<24|int(local,16));alpha_exclusions.append(k)
        today=datetime.now();stamp=((today.year-2000)<<9)|(today.month<<5)|today.day
        copy['header']=copy['header'][:16]+struct.pack('<HH',stamp,0)+copy['header'][20:]
        cell=int(win['parent'].split(':')[1],16);build_refs[cell].append((bool(r['flags']&0x400),replace_fields(copy,updates),copy['fid']))
    replacements={}
    for fid,r in rawcells.items():
        temporary=[encoded(triggers[fid])];persistent=[];ids={triggers[fid]['fid']}
        for is_persistent,data,refid in build_refs[fid]:
            if refid in ids:
                assert refid==triggers[fid]['fid'];temporary=[data]
            else:(persistent if is_persistent else temporary).append(data);ids.add(refid)
        children=(group(struct.pack('<I',fid),8,b''.join(persistent)) if persistent else b'')+group(struct.pack('<I',fid),9,b''.join(temporary))
        replacements[fid]=encoded(r)+group(struct.pack('<I',fid),6,children)
    world=paths['Perdition Sector World.esp'].read_bytes();wrld=next(r for r in records(world) if r['sig']=='WRLD' and r['fid']==0x3c)
    wrld=remap_record(wrld,mapper(allmasters['Perdition Sector World.esp'],'Perdition Sector World.esp',order),'WRLD')
    vanilla=paths['Fallout4.esm'].read_bytes()
    def filter_tree(start,end):
        out=[]
        while start<end:
            h=vanilla[start:start+24];sig,size,flags,fid=struct.unpack_from('<4sIII',h)
            if sig==b'GRUP':
                body=filter_tree(start+24,start+size)
                if body:out.append(h[:4]+struct.pack('<I',len(body)+24)+h[8:]+body)
                start+=size;continue
            if sig==b'WRLD' and fid==0x3c:out.append(encoded(wrld))
            elif sig==b'CELL' and fid in replacements:out.append(replacements[fid])
            start+=24+size
        return b''.join(out)
    body=filter_tree(0,len(vanilla));assert sum(r['sig']=='CELL' for r in records(body))==20
    blob=sub('HEDR',struct.pack('<fII',1.0,walk_count(body),0x800))+sub('CNAM',b'Perdition Sector\0')+sub('SNAM',b'Concord museum, Civic Access and exterior optimization rebuild\0')
    for n in order:blob+=sub('MAST',n.encode()+b'\0')+sub('DATA',b'\0'*8)
    seed=struct.pack('<4sIIIIHH',b'TES4',len(blob),0,0,0,131,0)+blob+body
    (BUILD/'Data').mkdir(parents=True,exist_ok=True)
    previous=Path(r'C:\workspace\perdition-lexington-build-20261123')
    for p in previous.iterdir():
        if p.is_file() and (p.suffix.lower() in {'.dll','.database','.pak'} or p.name in {'CreationKit.exe','CreationKit.ini','CreationKitCustom.ini','CreationKitPrefs.ini','CreationKitPlatformExtended.ini','CreationKitPlatformExtendedMessagesBlacklist.txt','steam_appid.txt','Fallout4_Default.ini'}):shutil.copy2(p,BUILD/p.name)
    providers={}
    for mod,folder in state['folders']:
        folder=Path(folder)
        for p in folder.rglob('*'):
            if p.is_file():providers.setdefault(p.relative_to(folder).as_posix().lower(),p)
    copied=0
    for rel,p in providers.items():
        suffix=p.suffix.lower();root=rel.split('/')[0]
        if suffix in {'.esp','.esm','.esl'}:
            if rel in {n.lower() for n in order}:shutil.copy2(p,BUILD/'Data'/p.name);copied+=1
        elif ('/' not in rel and suffix in {'.ba2','.csg','.cdx'} and not any(s in p.name.lower() for s in ['textures','voices','sounds','animations','startup','nvflex'])) or root in {'meshes','materials','vis'}:
            dest=BUILD/'Data'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);copied+=1
    (BUILD/'Data'/NAME).write_bytes(seed);(BUILD/'source-seed.esp').write_bytes(seed)
    for i,n in enumerate(order+[NAME]):os.utime(BUILD/'Data'/n,(1700000000+10*i,1700000000+10*i))
    manifest={'plugin':NAME,'mod':MOD,'order':order,'paths':{n:str(p) for n,p in paths.items()},'source_hashes':state['source_hashes'],'targets':sorted(targets),'interiors':sorted(INTERIORS),'centers':sorted(CENTERS),'seed_sha256':digest(BUILD/'Data'/NAME),'material_variants':variants,'alpha_exclusions':alpha_exclusions,'original_cells':original_cells,'inputs_copied':copied,'linked_inputs':0}
    (BUILD/'stage.json').write_text(json.dumps(manifest,indent=2));(HERE/'build_location.txt').write_text(str(BUILD))
    print(json.dumps({'cells':20,'material_variants':len(variants),'alpha_exclusions':len(alpha_exclusions),'input_files_copied':copied,'seed_bytes':len(seed)},indent=2))

if __name__=='__main__':main()
