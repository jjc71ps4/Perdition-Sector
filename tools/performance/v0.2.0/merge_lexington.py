"""Merge native CK optimization fields while preserving the current CELL data."""
from pathlib import Path
import json,shutil,struct,sys
from stage_lexington import BUILD,HERE,NAME,group,digest
sys.path.insert(0,str(HERE.parent/'v0.1.1'))
from build_visibility_test import records,sub,encoded,fields,walk_count
CENTERS={0xDEE1,0xDEDE}

def masters(data):return [v.rstrip(b'\0').decode() for t,v in next(records(data))['fields'] if t=='MAST']
def fid_remapper(source,target):
    def remap(fid):
        if not fid:return 0
        index=fid>>24;assert index<len(source),(hex(fid),len(source))
        return target.index(source[index])<<24|fid&0xffffff
    return remap
def mapped_field(tag,value,remap):
    if tag in {'XPRI','RVIS'}:return b''.join(struct.pack('<I',remap(x)) for x, in struct.iter_unpack('<I',value))
    if tag=='XCRI':
        meshes,values=struct.unpack_from('<II',value);assert len(value)==8+meshes*4+values*4 and values%2==0
        return value[:8+meshes*4]+b''.join(struct.pack('<II',remap(ref),mesh) for ref,mesh in struct.iter_unpack('<II',value[8+meshes*4:]))
    return value
def replace_fields(record,updates,date=None):
    existing={t for t,v in record['fields']}
    blob=b''.join(sub(t,updates.get(t,v)) for t,v in record['fields'])
    blob+=b''.join(sub(t,v) for t,v in updates.items() if t not in existing)
    changed=dict(record)
    if date is not None:changed['header']=record['header'][:16]+date+record['header'][20:]
    return encoded(changed,blob)
def transform_tree(data,replacements,keep_refs=True):
    def walk(start,end,cell=None):
        out=[]
        while start<end:
            h=data[start:start+24];sig,size,flags,fid=struct.unpack_from('<4sIII',h)
            if sig==b'GRUP':
                kind=struct.unpack_from('<i',h,12)[0];childcell=struct.unpack_from('<I',h,8)[0] if kind==6 else cell
                children=walk(start+24,start+size,childcell)
                if children:out.append(h[:4]+struct.pack('<I',24+len(children))+h[8:]+children)
                start+=size;continue
            if sig==b'CELL' and fid in replacements:out.append(replacements[fid])
            elif sig!=b'REFR' or keep_refs is True or keep_refs and cell in keep_refs:out.append(data[start:start+24+size])
            start+=24+size
        assert start==end
        return b''.join(out)
    return walk(0,len(data))
def reset_count(data):
    recs=iter(records(data));r=next(recs);f=dict(r['fields']);version,old,nextid=struct.unpack('<fII',f['HEDR'])
    body=data[24+struct.unpack_from('<I',data,4)[0]:]
    return replace_fields(r,{'HEDR':struct.pack('<fII',version,walk_count(body),nextid)})+body

def precombine():
    path=BUILD/'Data'/NAME;original=path.read_bytes();assert digest(path)==json.loads((BUILD/'stage.json').read_text())['seed_sha256']
    shutil.copy2(path,BUILD/'seed-before-native.esp')
    result=(BUILD/'Data/CombinedObjects.esp').read_bytes()
    target=masters(original);source=masters(result);remap=fid_remapper(source,target)
    cells={r['fid']:r for r in records(original) if r['sig']=='CELL'}
    native={remap(r['fid']):r for r in records(result) if r['sig']=='CELL'}
    assert set(native)==set(cells)
    findings=json.loads(Path(r'C:\workspace\perdition-lexington-audit-20261123\findings.json').read_text())
    deleted={int(v['key'].split(':')[1],16) for v in findings['world_edits'] if v['winning_deleted']}
    replacements={};details=[]
    for fid,current in cells.items():
        generated=native[fid];g=dict(generated['fields']);updates={t:mapped_field(t,g[t],remap) for t in ['PCMB','XCRI']}
        meshes,values=struct.unpack_from('<II',updates['XCRI']);pairs=list(struct.iter_unpack('<II',updates['XCRI'][8+4*meshes:]))
        assert not {r for r,m in pairs}&deleted,(hex(fid),'Deleted reference in new combined geometry')
        for mesh, in struct.iter_unpack('<I',updates['XCRI'][8:8+4*meshes]):
            assert (BUILD/f'Data/meshes/precombined/{fid:08X}_{mesh:08X}_OC.NIF').is_file(),(hex(fid),hex(mesh))
        assert int.from_bytes(updates['PCMB'],'little')>=0x311f
        replacements[fid]=replace_fields(current,updates,generated['header'][16:20])
        details.append({'cell':f'{fid:08X}','meshes':meshes,'combined_refs':len(pairs),'PCMB':updates['PCMB'].hex()})
    merged=reset_count(transform_tree(original,replacements,CENTERS))
    for r in records(merged):
        if r['sig']=='CELL':
            before=dict(cells[r['fid']]['fields']);after=dict(r['fields']);assert {t for t in before if before[t]!=after[t]}<={'PCMB','XCRI'}
    path.write_bytes(merged)
    shutil.copy2(BUILD/'CKBuild.log',BUILD/'precombine-build.log')
    (BUILD/'precombine-validation.json').write_text(json.dumps({'cells':details,'deleted_references_excluded':len(deleted),'native_cells':len(native),'mesh_files':len(list((BUILD/'Data/meshes/precombined').glob('*.NIF'))),'seed_sha256':digest(path)},indent=2))
    print(json.dumps({'native_cells':len(native),'mesh_files':len(list((BUILD/'Data/meshes/precombined').glob('*.NIF'))),'deleted_references_excluded':len(deleted),'previs_triggers':[f'{x:08X}' for x in CENTERS]},indent=2))

if __name__=='__main__':precombine()
