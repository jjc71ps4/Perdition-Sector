"""FO4 BS130 geometry reader for the editable workbench, not a NIF exporter.

Layout reference: https://github.com/niftools/nifxml/blob/develop/nif.xml
All original blocks remain in Sources for the subsequent game export task.
"""
import math,struct
from asset_io import Reader,nif_header,norm,embedded_paths

SHAPES={'BSTriShape','BSSubIndexTriShape','BSMeshLODTriShape'}
NODES={'NiNode','BSFadeNode','BSOrderedNode','NiSwitchNode','NiBillboardNode','BSLeafAnimNode','BSValueNode'}

def av(block,strings):
    r=Reader(block['data']);name=r.one('i');n=r.one('I');extras=list(r.unpack('i'*n))
    controller=r.one('i');flags=r.one('I');translation=list(r.unpack('fff'))
    rotation=list(r.unpack('9f'));scale=r.one('f');collision=r.one('i')
    obj={'id':block['id'],'type':block['type'],'name':strings[name] if 0<=name<len(strings) else '',
         'flags':flags,'translation':translation,'rotation_column_major':rotation,'scale':scale,
         'extras':extras,'controller':controller,'collision':collision}
    return r,obj

def read_geometry(data):
    nif=nif_header(data);strings=nif['strings'];blocks=nif['blocks'];objects=[];skipped=[]
    for b in blocks:
        if b['type'] in NODES:
            r,obj=av(b,strings);count=r.one('I');obj['children']=list(r.unpack('i'*count));objects.append(obj)
        elif b['type'] in SHAPES:
            r,obj=av(b,strings);obj['bounds']=list(r.unpack('4f'))
            obj['skin'],obj['shader'],obj['alpha']=r.unpack('iii')
            descriptor=r.one('Q');tri_count=r.one('I');vert_count=r.one('H');size=r.one('I')
            stride=(descriptor&15)*4;attributes=descriptor>>44
            obj.update(vertex_descriptor=str(descriptor),vertex_count=vert_count,triangle_count=tri_count,
                       vertex_offset=b['offset']+r.pos,vertex_stride=stride,attributes=attributes,
                       full_precision=bool(attributes&0x400))
            if size==0:
                obj.update(vertices=[],triangles=[],uv=[],normals=[],weights=[],bone_indices=[])
                objects.append(obj);continue
            assert size==stride*vert_count+6*tri_count,(obj['name'],size,stride,vert_count,tri_count)
            assert attributes&1,(obj['name'],'No stored vertex positions')
            vertex_data=r.take(stride*vert_count);triangles=list(r.unpack('H'*(3*tri_count)))
            assert not triangles or max(triangles)<vert_count
            vertices=[];uv=[];normals=[];weights=[];bone_indices=[];colors=[]
            for i in range(vert_count):
                offset=i*stride
                point=struct.unpack_from('<fff' if attributes&0x400 else '<eee',vertex_data,offset)
                assert all(math.isfinite(x) for x in point),(obj['name'],i,point)
                vertices.append(point)
                if attributes&2:uv.append(struct.unpack_from('<ee',vertex_data,offset+4*((descriptor>>8)&15)))
                if attributes&8:
                    pos=offset+4*((descriptor>>16)&15);normal=tuple(v/127.5-1 for v in vertex_data[pos:pos+3]);normals.append(normal)
                if attributes&0x20:
                    pos=offset+4*((descriptor>>24)&15);colors.append(tuple(v/255 for v in vertex_data[pos:pos+4]))
                if attributes&0x40:
                    pos=offset+4*((descriptor>>28)&15)
                    weights.append(struct.unpack_from('<eeee',vertex_data,pos));bone_indices.append(tuple(vertex_data[pos+8:pos+12]))
            obj.update(vertices=vertices,triangles=[triangles[i:i+3] for i in range(0,len(triangles),3)],
                       uv=uv,normals=normals,weights=weights,bone_indices=bone_indices,colors=colors)
            shader=blocks[obj['shader']] if 0<=obj['shader']<len(blocks) else None
            if shader:
                index=struct.unpack_from('<i',shader['data'],4 if shader['type']=='BSLightingShaderProperty' else 0)[0]
                obj['material']=norm(strings[index]) if 0<=index<len(strings) else ''
                obj['shader_texture_paths']=embedded_paths(shader['data'],['dds'])
                if shader['type']=='BSLightingShaderProperty':
                    sr=Reader(shader['data']);sr.take(8);n=sr.one('I');sr.take(4*n+4+24);texset=sr.one('i')
                    if 0<=texset<len(blocks) and blocks[texset]['type']=='BSShaderTextureSet':
                        tr=Reader(blocks[texset]['data']);n=tr.one('I')
                        obj['shader_texture_paths']=[norm(tr.string()) for _ in range(n)]
            if 0<=obj['skin']<len(blocks):
                skin=blocks[obj['skin']]
                assert skin['type']=='BSSkin::Instance',(obj['name'],skin['type'])
                sr=Reader(skin['data']);root,bone_data,count=sr.unpack('iiI');bones=list(sr.unpack('i'*count))
                obj['bone_block_ids']=bones
                obj['bone_names']=[strings[struct.unpack_from('<i',blocks[k]['data'])[0]] if k>=0 else 'NULL' for k in bones]
                assert all(i<len(bones) or w==0 for inds,ws in zip(bone_indices,weights) for i,w in zip(inds,ws))
                obj['skin_metadata']={'root':root,'bone_data_block':bone_data,'original_block_hex':skin['data'].hex(),
                                      'bone_data_hex':blocks[bone_data]['data'].hex() if bone_data>=0 else ''}
            if b['type']=='BSSubIndexTriShape' and size:
                # Preserve segment records as source bytes. The edit handoff
                # exports no game NIF until the changed geometry is reviewed.
                obj['segment_data_hex']=r.take(len(r.data)-r.pos).hex()
            objects.append(obj)
        elif b['type'] in {'NiTriShape','NiTriStrips','BSLODTriShape','BSSegmentedTriShape'}:
            skipped.append({'block':b['id'],'type':b['type']})
    parents={child:obj['id'] for obj in objects for child in obj.get('children',[]) if child>=0}
    for obj in objects:obj['parent']=parents.get(obj['id'])
    connects=[]
    for b in blocks:
        if b['type']=='BSConnectPoint::Parents':
            r=Reader(b['data']);r.take(4);n=r.one('I')
            for _ in range(n):
                parent=r.string();name=r.string();rotation=r.unpack('4f');translation=r.unpack('3f');scale=r.one('f')
                connects.append({'id':b['id'],'parent':parent,'name':name,'rotation':rotation,'translation':translation,'scale':scale})
    return {'objects':objects,'connect_points':connects,'unsupported_geometry':skipped,'block_count':len(blocks)}

if __name__=='__main__':
    from pathlib import Path
    from collections import Counter
    import json
    folder=Path(r'C:\workspace\Perdition_MK18_Workbench');manifest=json.loads((folder/'asset_manifest.json').read_text())
    failures=[];counts=Counter();per_model=[]
    for i,asset in enumerate(manifest['models']):
        try:
            geometry=read_geometry((folder/'Sources'/asset['path']).read_bytes())
            shapes=[o for o in geometry['objects'] if o['type'] in SHAPES]
            item={'path':asset['path'],'shapes':len(shapes),'vertices':sum(len(o['vertices']) for o in shapes),
                  'triangles':sum(len(o['triangles']) for o in shapes),'unsupported':geometry['unsupported_geometry']}
            per_model.append(item)
            for k in ['shapes','vertices','triangles']:counts[k]+=item[k]
            if geometry['unsupported_geometry']:failures.append(item)
        except Exception as e:failures.append({'path':asset['path'],'error':repr(e)})
        if i%100==0:print('Geometry checked',i+1,'/',len(manifest['models']),flush=True)
    result={'models':len(per_model),'totals':dict(counts),'failures':failures,'per_model':per_model}
    (folder/'geometry_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='per_model'},indent=2))
    if failures:raise SystemExit(1)
