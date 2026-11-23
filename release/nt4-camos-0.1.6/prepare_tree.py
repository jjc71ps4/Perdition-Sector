from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;PUBLIC=HERE/'Public';PREFIX='release/nt4-camos-0.1.6/'
validation=json.loads((HERE/'validation.json').read_text(encoding='utf-8-sig'));assert validation['passed']
for name in ['validation.json','prepare_fixture.py','Test-Channel.ps1','prepare_tree.py']:
    p=PUBLIC/(PREFIX+name);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text((HERE/name).read_text(encoding='utf-8-sig'),encoding='utf-8',newline='\n')
packets=[];packet=[];size=0;allpaths=[]
for p in sorted(PUBLIC.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(PUBLIC).as_posix()
    assert rel.startswith(('release/nt4-camos-0.1.6/','tools/nt4/')) or rel=='release/revisions-0.2.3/transport.json'
    assert p.suffix.lower() in {'.py','.ps1','.md','.json'}
    row=dict(path=rel,mode='100644',type='blob',content=p.read_text(encoding='utf-8'))
    length=len(json.dumps(row));assert length<900000
    if packet and size+length>700000:packets.append(packet);packet=[];size=0
    packet.append(row);size+=length;allpaths.append(rel)
if packet:packets.append(packet)
for i,packet in enumerate(packets):(HERE/('tree_packet_'+str(i)+'.json')).write_text(json.dumps(packet),encoding='utf-8',newline='\n')
summary=dict(files=len(allpaths),packets=len(packets),paths=allpaths,game_assets_in_tree=False,
    installer_changes=False,publisher_and_workflow_changes=False)
(HERE/'tree_manifest.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(dict(files=len(allpaths),packets=len(packets),game_assets_in_tree=False),indent=2))
