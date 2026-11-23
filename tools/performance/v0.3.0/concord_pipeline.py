"""Merge and validate native Concord optimization outputs; stage test package."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json,shutil,struct,sys,os
from stage_concord import *
VISNAME='PSConcordVisBuild.esp'
PACKAGE=HERE/'package'/MOD

def merge_precombine():
    stage=json.loads((BUILD/'stage.json').read_text());path=BUILD/'Data'/NAME;seed=path.read_bytes();assert digest(path)==stage['seed_sha256']
    source=(BUILD/'Data/CombinedObjects.esp').read_bytes();remap=mapper(head_masters(source),'CombinedObjects.esp',stage['order'])
    current={r['fid']:r for r in records(seed) if r['sig']=='CELL'};native={remap(r['fid']):r for r in records(source) if r['sig']=='CELL'}
    assert set(current)==set(native)==set(stage['targets'])
    state=json.loads((AUDIT/'record_state.json').read_text());deleted={k for k,c in state['refs'].items() if c[-1][1]['deleted']};disabled={k for k,c in state['refs'].items() if c[-1][1]['disabled']}
    excluded=deleted|disabled|set(stage['alpha_exclusions']);replacements={};details=[];old_deleted=set();output_refs=set()
    for fid,c in current.items():
        g=native[fid];fields_native=dict(g['fields']);updates={t:mapped_field(t,fields_native[t],remap) for t in ['PCMB','XCRI']}
        n,num=struct.unpack_from('<II',updates['XCRI']);assert num%2==0 and len(updates['XCRI'])==8+4*n+4*num
        refs={canonical(f,stage['order'],NAME) for f,m in struct.iter_unpack('<II',updates['XCRI'][8+4*n:])}
        assert not refs&excluded,('Excluded reference was combined',hex(fid),sorted(refs&excluded)[:5]);output_refs|=refs
        old=dict(c['fields'])['XCRI'];oldn=struct.unpack_from('<I',old)[0]
        old_deleted|={canonical(f,stage['order'],NAME) for f,m in struct.iter_unpack('<II',old[8+4*oldn:])}&deleted
        for m, in struct.iter_unpack('<I',updates['XCRI'][8:8+4*n]):assert (BUILD/f'Data/meshes/precombined/{fid:08X}_{m:08X}_OC.NIF').is_file()
        assert (BUILD/f'Data/meshes/precombined/{fid:08X}_Physics.NIF').is_file()
        assert int.from_bytes(updates['PCMB'],'little')>=max((c[-1][1]['vci1']['value'] for k,c in state['refs'].items() if k in refs),default=0)
        replacements[fid]=replace_fields(c,updates,g['header'][16:20]);details.append({'cell':f'{fid:08X}','meshes':n,'references':num//2,'PCMB':updates['PCMB'].hex()})
    merged=reset_count(transform_tree(seed,replacements,True));path.write_bytes(merged)
    # Retain every material/alpha build override in the geometry seed (a master).
    # A small second seed triggers only the two exterior clusters and interiors.
    merged_cells={r['fid']:r for r in records(merged) if r['sig']=='CELL'}
    triggers={}
    for r in scoped(seed,set(stage['targets'])):
        if r['sig']=='REFR' and r['cell'] in PREVIS_TRIGGERS:triggers.setdefault(r['cell'],r)
    assert set(triggers)==PREVIS_TRIGGERS
    cells={fid:encoded(merged_cells[fid])+group(struct.pack('<I',fid),6,group(struct.pack('<I',fid),9,encoded(triggers[fid]))) for fid in PREVIS_TRIGGERS}
    def filter_tree(start,end):
        out=[]
        while start<end:
            h=merged[start:start+24];sig,size,flags,fid=struct.unpack_from('<4sIII',h)
            if sig==b'GRUP':
                kind=struct.unpack_from('<i',h,12)[0]
                if kind==6:start+=size;continue
                children=filter_tree(start+24,start+size)
                if children:out.append(h[:4]+struct.pack('<I',24+len(children))+h[8:]+children)
                start+=size;continue
            if sig==b'WRLD':out.append(merged[start:start+24+size])
            elif sig==b'CELL' and fid in cells:out.append(cells[fid])
            start+=24+size
        return b''.join(out)
    body=filter_tree(0,len(merged));blob=sub('HEDR',struct.pack('<fII',1.0,walk_count(body),0x800))+sub('CNAM',b'Perdition Sector\0')
    for n in stage['order']+[NAME]:blob+=sub('MAST',n.encode()+b'\0')+sub('DATA',b'\0'*8)
    visseed=struct.pack('<4sIIIIHH',b'TES4',len(blob),0,0,0,131,0)+blob+body
    assert Counter(r['sig'] for r in records(visseed))==Counter({'TES4':1,'WRLD':1,'CELL':4,'REFR':4})
    (BUILD/'Data'/VISNAME).write_bytes(visseed);shutil.copy2(BUILD/'CKBuild.log',BUILD/'precombine-build.log')
    result={'cells':details,'stale_deleted_refs_excluded':len(old_deleted),'alpha_overrides_excluded':len(stage['alpha_exclusions']),'total_combined_references':len(output_refs),'previs_trigger_cells':[f'{x:08X}' for x in sorted(PREVIS_TRIGGERS)]}
    assert result['stale_deleted_refs_excluded']==74,result
    (BUILD/'precombine-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='cells'},indent=2))

def finish():
    from asset_io import nif_header
    stage=json.loads((BUILD/'stage.json').read_text());materials=json.loads((BUILD/'material-validation.json').read_text())['summary'];assert materials['all_variants_verified']
    seed=(BUILD/'Data'/NAME).read_bytes();initial=(BUILD/'source-seed.esp').read_bytes();native=(BUILD/'Data/PreVis.esp').read_bytes()
    remap=mapper(head_masters(native),'PreVis.esp',stage['order']);cells={r['fid']:r for r in records(seed) if r['sig']=='CELL'};original={r['fid']:r for r in records(initial) if r['sig']=='CELL'};generated={remap(r['fid']):r for r in records(native) if r['sig']=='CELL'}
    assert set(generated)==set(cells)==set(stage['targets']),(len(generated),len(cells))
    log=(BUILD/'CKBuild.log').read_text(errors='replace');errors=[s for s in log.splitlines() if any(t in s.lower() for t in ['visibility task did not complete','out of handle array','out of memory','failed to generate','fatal error','failed to save'])];assert not errors,errors[:10]
    replacements={};assets={};details=[];nif_types=Counter();allxpri=set();allrefs=set()
    for fid,c in cells.items():
        g=dict(generated[fid]['fields']);updates={t:mapped_field(t,g[t],remap) for t in ['VISI','RVIS','XPRI'] if t in g};updates.setdefault('XPRI',b'')
        replacements[fid]=replace_fields(c,updates);after=dict(next(records(replacements[fid]))['fields']);before=dict(original[fid]['fields'])
        optimization_fields={'PCMB','XCRI','VISI','RVIS','XPRI'}
        assert set(after)^set(before)<=optimization_fields
        assert {t for t in set(before)&set(after) if after[t]!=before[t]}<=optimization_fields
        assert after['PCMB']==after['VISI']
        center=fid if fid in INTERIORS else struct.unpack('<I',after['RVIS'])[0];assert center in PREVIS_TRIGGERS
        rel=f'vis/fallout4.esm/{center:08X}.uvd';p=BUILD/'Data'/rel;uvd=p.read_bytes();assert len(uvd)>10000 and struct.unpack_from('<I',uvd,8)[0]==len(uvd);assets[rel]=p
        x=after['XCRI'];n,num=struct.unpack_from('<II',x)
        allrefs|={canonical(f,stage['order'],NAME) for f,m in struct.iter_unpack('<II',x[8+4*n:])};allxpri|={canonical(f,stage['order'],NAME) for f, in struct.iter_unpack('<I',after['XPRI'])}
        for m, in struct.iter_unpack('<I',x[8:8+4*n]):
            rel=f'meshes/precombined/{fid:08X}_{m:08X}_OC.NIF';assets[rel]=BUILD/'Data'/rel
        rel=f'meshes/precombined/{fid:08X}_Physics.NIF';assets[rel]=BUILD/'Data'/rel
        details.append({'cell':f'{fid:08X}','name':after.get('EDID',b'').rstrip(b'\0').decode(),'grid':list(struct.unpack_from('<ii',after['XCLC'])) if 'XCLC' in after else None,'meshes':n,'combined_pairs':num//2,'PCMB':after['PCMB'].hex(),'VISI':after['VISI'].hex(),'visibility_refs':len(after['XPRI'])//4})
    assert not (allrefs|allxpri)&set(stage['alpha_exclusions']),'Alpha-sensitive refs were not excluded from optimization'
    final=reset_count(transform_tree(seed,replacements,False));assert Counter(r['sig'] for r in records(final))==Counter({'TES4':1,'WRLD':1,'CELL':20})
    # Independently compare non-optimization fields against their original
    # winning plugins, resolving FormIDs by owner rather than numeric index.
    final_cells={r['fid']:r for r in records(final) if r['sig']=='CELL'}
    form_fields={'LTMP','XCLR','XLCN','RVIS','XCIM','XEZN','XCMO','XCWT','XCCM','XCAS'}
    def semantic_fields(r,ms,name):
        return [(t,tuple(canonical(f,ms,name) for f, in struct.iter_unpack('<I',v)) if t in form_fields else v) for t,v in r['fields'] if t not in {'PCMB','XCRI','VISI','RVIS','XPRI'}]
    sources=defaultdict(set)
    for key,meta in stage['original_cells'].items():sources[meta['plugin']].add(int(key.split(':')[1],16))
    for name,ids in sources.items():
        data=Path(stage['paths'][name]).read_bytes();ms=head_masters(data)
        for r in scoped(data,ids):
            if r['sig']=='CELL':
                assert r['flags']==final_cells[r['fid']]['flags']
                assert semantic_fields(r,ms,name)==semantic_fields(final_cells[r['fid']],stage['order'],NAME),('Non-optimization CELL data changed',name,hex(r['fid']))
    for rel,p in assets.items():
        assert p.is_file()
        if p.suffix.lower()=='.nif':
            n=nif_header(p.read_bytes());nif_types.update(b['type'] for b in n['blocks']);footer=n['footer'];count=struct.unpack_from('<I',footer)[0];assert len(footer)==4+count*4;assert all(-1<=i<len(n['blocks']) for i, in struct.iter_unpack('<i',footer[4:]))
    PACKAGE.mkdir(parents=True,exist_ok=True);(PACKAGE/NAME).write_bytes(final)
    for rel,p in assets.items():
        dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    (PACKAGE/'meta.ini').write_text('[General]\nversion=0.3.0\nnotes=Concord, Museum of Freedom and Civic Access native optimization rebuild, preserving Perdition world edits.\n')
    result={'plugin':NAME,'mod':MOD,'plugin_sha256':digest(PACKAGE/NAME),'cells':details,'source_hashes':stage['source_hashes'],'assets':{rel:{'bytes':p.stat().st_size,'sha256':digest(p)} for rel,p in assets.items()},'nif_types':dict(nif_types),'stale_deleted_refs_excluded':74,'alpha_overrides_preserved':len(stage['alpha_exclusions']),'material_variants':len(stage['material_variants']),'material_validation':materials,'native_build_errors':errors,'final_reference_records':0,'gameplay_or_ini_edits':False,'runtime_tested':False}
    (HERE/'build_manifest.json').write_text(json.dumps(result,indent=2));shutil.copy2(BUILD/'CKBuild.log',BUILD/'previs-build.log');print(json.dumps({k:v for k,v in result.items() if k not in {'source_hashes','assets','cells','nif_types'}},indent=2))

if __name__=='__main__':
    sys.path.insert(0,str(ROOT/'Development/ModelWorkbench/MK18/v0.1.0'))
    {'merge':merge_precombine,'finish':finish}[sys.argv[1]]()
