"""Check material substitutions and replacement meshes in the native output."""
from collections import defaultdict
from stage_concord import *
sys.path.insert(0,str(ROOT/'Development/ModelWorkbench/MK18/v0.1.0'))
from asset_io import BA2,nif_header,plugin_records
def norm(s):return s.lower().replace('\\','/').split('/materials/',1)[-1].removeprefix('materials/')
def shader_names(data):
    n=nif_header(data);names=set()
    for b in n['blocks']:
        if b['type'] in {'BSLightingShaderProperty','BSEffectShaderProperty'}:
            index=struct.unpack_from('<i',b['data'],4 if b['type']=='BSLightingShaderProperty' else 0)[0]
            if 0<=index<len(n['strings']):names.add(norm(n['strings'][index]))
    return names
def main():
    stage=json.loads((BUILD/'stage.json').read_text());keys={v['swap'] for v in stage['material_variants']};swaps={}
    for name in stage['order']:
        for r in plugin_records(BUILD/'Data'/name,{'MSWP'}):
            key=r['key']
            if key.startswith('unresolved:'):key=name.lower()+':'+f'{r["local_id"]&0xffffff:06X}'
            if key not in keys:continue
            swaps[key]={'from':{norm(v.rstrip(b'\0').decode(errors='replace')) for t,v in r['fields'] if t=='BNAM'},'to':{norm(v.rstrip(b'\0').decode(errors='replace')) for t,v in r['fields'] if t=='SNAM'}}
    assert keys<=swaps.keys(),keys-swaps.keys()
    reference_meshes=defaultdict(set)
    data=(BUILD/'Data/CombinedObjects.esp').read_bytes();ms=head_masters(data)
    for r in records(data):
        if r['sig']!='CELL':continue
        x=dict(r['fields'])['XCRI'];n=struct.unpack_from('<I',x)[0]
        for ref,mesh in struct.iter_unpack('<II',x[8+4*n:]):reference_meshes[canonical(ref,ms,'CombinedObjects.esp')].add(BUILD/f'Data/meshes/precombined/{r["fid"]:08X}_{mesh:08X}_OC.NIF')
    archives=[];order_stems={n.rsplit('.',1)[0].lower():i for i,n in enumerate(stage['order'])}
    for p in (BUILD/'Data').glob('*.ba2'):
        with p.open('rb') as f:h=f.read(24)
        if h[8:12]!=b'GNRL':continue
        stem=p.stem.lower();owner=next((s for s in sorted(order_stems,key=len,reverse=True) if stem==s or stem.startswith(s+' - ')),None)
        if owner is not None:archives.append((order_stems[owner],BA2(p)))
    archives.sort(key=lambda a:a[0]);mesh_cache={};source_cache={};results=[]
    for v in stage['material_variants']:
        meshes=reference_meshes.get(v['ref'])
        if not meshes:results.append(dict(v,status='rendered individually'));continue
        actual=set()
        for p in meshes:
            if p not in mesh_cache:mesh_cache[p]=shader_names(p.read_bytes())
            actual|=mesh_cache[p]
        swap=swaps[v['swap']]
        if actual&swap['to']:results.append(dict(v,status='swapped material baked'));continue
        model='meshes/'+v['model'].lower().replace('\\','/')
        if model not in source_cache:
            p=BUILD/'Data'/model
            data=p.read_bytes() if p.exists() else next((a.read(model) for i,a in reversed(archives) if model in a.entries),None)
            assert data is not None,model;source_cache[model]=shader_names(data)
        source=source_cache[model]
        assert not source&swap['from'],('An applicable material substitution is missing',v,sorted(source&swap['from']))
        assert source&actual,('Replacement model materials changed',v,source)
        results.append(dict(v,status='replacement material baked; legacy swap does not apply'))
    counts=dict(Counter(v['status'] for v in results));summary={'all_variants_verified':True,'references':len(results),'counts':counts}
    (BUILD/'material-validation.json').write_text(json.dumps({'summary':summary,'references':results},indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
