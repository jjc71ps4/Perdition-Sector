"""Forward base-object material variants into build-only reference overrides.

The CK ignores a STAT's base MODS when combining it. These overrides are inputs
to baking only; they are removed from the final, CELL-only optimization patch.
"""
from stage_lexington import *
from collections import defaultdict

def main():
    issues=json.loads((BUILD/'material-alpha-combined-issues.json').read_text())
    stage=json.loads((BUILD/'stage.json').read_text());targets=set(stage['targets'])
    output_masters=[n.lower() for n in stage['order']]
    seed=(BUILD/'seed-before-native.esp').read_bytes()
    need={r['ref']:r for r in issues};additions=defaultdict(list)
    found=set()
    for name in {r['plugin'] for r in issues}:
        for r in scoped((BUILD/'Data'/name).read_bytes(),targets):
            if r['sig']=='TES4':masters=[v.rstrip(b'\0').decode().lower() for t,v in r['fields'] if t=='MAST']
            elif r['sig']=='REFR':
                index=r['fid']>>24;key=(masters[index] if index<len(masters) else name.lower())+':'+f'{r["fid"]&0xffffff:06X}'
                if key not in need:continue
                assert {t for t,v in r['fields']}<={'NAME','XSCL','DATA'}
                d=dict(r['fields']);assert struct.unpack('<I',d['NAME'])[0]>>24==0
                swap=need[key]['base_object']['MSWP'];owner,local=swap.split(':')
                swapid=output_masters.index(owner)<<24|int(local,16)
                assert not need[key]['material_swap'] and need[key]['alpha'] in {None,1.0}
                r['header']=r['header'][:16]+bytes.fromhex('77350000')+r['header'][20:]
                additions[r['cell']].append(encoded(r,r['blob']+sub('XMSP',struct.pack('<I',swapid))))
                found.add(key)
    assert found==set(need)
    def walk(start,end,cell=None):
        out=[]
        while start<end:
            h=seed[start:start+24];sig,size=struct.unpack_from('<4sI',h)
            if sig==b'GRUP':
                kind=struct.unpack_from('<i',h,12)[0];childcell=struct.unpack_from('<I',h,8)[0] if kind==6 else cell
                body=walk(start+24,start+size,childcell)
                if kind==9:body+=b''.join(additions.pop(cell,[]))
                out.append(h[:4]+struct.pack('<I',len(body)+24)+h[8:]+body);start+=size
            else:out.append(seed[start:start+24+size]);start+=24+size
        return b''.join(out)
    result=walk(0,len(seed));assert not additions
    from merge_lexington import reset_count
    result=reset_count(result)
    # Keep first native outputs as a diagnostic checkpoint, outside the Data tree.
    checkpoint=BUILD/'attempt1';checkpoint.mkdir(exist_ok=True)
    for name in ['CombinedObjects.esp','PreVis.esp']:
        p=BUILD/'Data'/name
        if p.exists():shutil.move(str(p),str(checkpoint/name))
    shutil.copy2(BUILD/'CKBuild.log',checkpoint/'previs-build.log')
    for p in (BUILD/'Data/vis').rglob('*.uvd'):
        dest=checkpoint/'vis'/p.relative_to(BUILD/'Data/vis');dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(p),str(dest))
    (BUILD/'Data'/NAME).write_bytes(result)
    manifest=json.loads((BUILD/'stage.json').read_text());manifest['seed_sha256']=digest(BUILD/'Data'/NAME);manifest['build_only_material_overrides']=len(found);(BUILD/'stage.json').write_text(json.dumps(manifest,indent=2))
    print('Build-only material variants preserved:',len(found))

if __name__=='__main__':main()
