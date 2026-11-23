"""Validate native outputs and stage a reversible, CELL-only Lexington patch."""
from pathlib import Path
from collections import Counter
import hashlib,json,shutil,struct,sys
from stage_lexington import BUILD,HERE,ROOT,NAME,digest
from merge_lexington import masters,fid_remapper,mapped_field,replace_fields,transform_tree,reset_count
sys.path.insert(0,str(HERE.parent/'v0.1.1'))
from build_visibility_test import records
sys.path.insert(0,str(ROOT/'Development/ModelWorkbench/MK18/v0.1.0'))
from asset_io import nif_header
MOD='Perdition Lexington Optimization - Test'
PACKAGE=HERE/'package'/MOD

def build():
    stage=json.loads((BUILD/'stage.json').read_text());pre=json.loads((BUILD/'precombine-validation.json').read_text())
    seed=(BUILD/'Data'/NAME).read_bytes();original=(BUILD/'seed-before-native.esp').read_bytes()
    native=(BUILD/'Data/PreVis.esp').read_bytes();source=masters(native);target=masters(seed);remap=fid_remapper(source,target)
    targets=set(stage['targets']);cells={r['fid']:r for r in records(seed) if r['sig']=='CELL'}
    initial={r['fid']:r for r in records(original) if r['sig']=='CELL'}
    generated={remap(r['fid']):r for r in records(native) if r['sig']=='CELL'}
    assert targets<=generated.keys()
    log=(BUILD/'CKBuild.log').read_text(errors='replace')
    forbidden=['visibility task did not complete','out of handle array','out of memory','failed to generate','fatal error','unable to create visibility','failed to save']
    failures=[s for s in log.splitlines() if any(p in s.lower() for p in forbidden)]
    assert not failures,failures[:10]
    replacements={};details=[];assets={};date=None;mesh_total=0;reference_total=0
    for fid,current in cells.items():
        generated_cell=generated[fid];g=dict(generated_cell['fields'])
        updates={t:mapped_field(t,g[t],remap) for t in ['VISI','RVIS','XPRI'] if t in g}
        # XPRI can be absent when the cell has no eligible non-combined objects.
        updates.setdefault('XPRI',b'')
        replacements[fid]=replace_fields(current,updates)
        result=next(records(replacements[fid]));after=dict(result['fields']);before=dict(initial[fid]['fields'])
        assert set(after)==set(before)
        assert {t for t in before if after[t]!=before[t]}<={'PCMB','XCRI','VISI','RVIS','XPRI'}
        assert result['flags']==initial[fid]['flags']
        assert int.from_bytes(after['VISI'],'little')>=0x3577 and int.from_bytes(after['PCMB'],'little')>=0x3577
        assert after['PCMB']==after['VISI']
        center=struct.unpack('<I',after['RVIS'])[0];assert center in {0xDEE1,0xDEDE}
        uv=BUILD/f'Data/vis/Fallout4.esm/{center:08X}.uvd';assert uv.is_file() and uv.stat().st_size>100000
        head=uv.read_bytes()[:40];assert struct.unpack_from('<I',head,8)[0]==uv.stat().st_size
        assets[uv.relative_to(BUILD/'Data').as_posix()]=uv
        v=after['XCRI'];n,num=struct.unpack_from('<II',v);mesh_total+=n;reference_total+=num//2
        for mesh, in struct.iter_unpack('<I',v[8:8+4*n]):
            rel=f'meshes/precombined/{fid:08X}_{mesh:08X}_OC.NIF';assets[rel]=BUILD/'Data'/rel
        rel=f'meshes/precombined/{fid:08X}_Physics.NIF';assets[rel]=BUILD/'Data'/rel
        details.append({'cell':f'{fid:08X}','grid':list(struct.unpack_from('<ii',after['XCLC'])),'center':f'{center:08X}','meshes':n,'combined_references':num//2,'visibility_references':len(after['XPRI'])//4,'VISI':after['VISI'].hex(),'PCMB':after['PCMB'].hex(),'changed_fields':[t for t in before if after[t]!=before[t]]})
    final=reset_count(transform_tree(seed,replacements,False))
    recs=list(records(final));assert Counter(r['sig'] for r in recs)==Counter({'TES4':1,'WRLD':1,'CELL':18})
    assert masters(final)==stage['order']
    # Check every generated NIF block table and root reference, not just filenames.
    block_types=Counter();materials=set()
    for rel,p in assets.items():
        assert p.is_file(),str(p)
        if p.suffix.lower()!='.nif':continue
        nif=nif_header(p.read_bytes());block_types.update(b['type'] for b in nif['blocks'])
        footer=nif['footer'];count=struct.unpack_from('<I',footer)[0];assert len(footer)==4+4*count
        assert all(-1<=i<len(nif['blocks']) for i, in struct.iter_unpack('<i',footer[4:]))
        materials.update(s.lower().replace('\\','/') for s in nif['strings'] if s.lower().endswith(('.bgsm','.bgem')))
    PACKAGE.mkdir(parents=True,exist_ok=True)
    (PACKAGE/NAME).write_bytes(final)
    for rel,p in assets.items():
        dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    (PACKAGE/'meta.ini').write_text('[General]\nversion=0.2.0\nnotes=Lexington 18-cell native precombine/previs rebuild, retaining Perdition scenery deletions and material variants.\n')
    receipt={'mod':MOD,'plugin':NAME,'plugin_sha256':digest(PACKAGE/NAME),'cells':details,'meshes':mesh_total,'physics_meshes':18,'combined_references':reference_total,'build_only_material_variants':stage['build_only_material_overrides'],'deleted_lexington_references_excluded':pre['deleted_references_excluded'],'source_hashes':stage['source_hashes'],'assets':{rel:{'bytes':p.stat().st_size,'sha256':digest(p)} for rel,p in assets.items()},'nif_block_types':dict(block_types),'material_paths':len(materials),'native_build_errors':failures,'reference_records_in_final_plugin':0,'gameplay_scripts_or_ini_edits':False,'runtime_tested':False,'validation':'18 CELL scope; exact preservation outside optimization fields; native PCMB/VISI pair; 26 deleted references excluded; all referenced meshes and physics present; all NIF block tables and roots validated; two UVD sizes verified'}
    (HERE/'build_manifest.json').write_text(json.dumps(receipt,indent=2))
    shutil.copy2(BUILD/'CKBuild.log',BUILD/'previs-build.log')
    print(json.dumps({k:v for k,v in receipt.items() if k not in {'source_hashes','assets','cells','nif_block_types'}},indent=2))

if __name__=='__main__':build()
