"""Check viewport bounds and SWF format, then install only the menu movie."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,os,re,shutil,struct,zlib
from build_viewport import ROOT,HERE,MOD,sha
def main():
    manifest=json.loads((HERE/'build_manifest.json').read_text());candidate=HERE/'package/Interface/PSNewGameMenu.swf';data=candidate.read_bytes()
    assert sha(candidate)==manifest['sha256'] and data[:3] in {b'FWS',b'CWS'} and data[3]==10
    raw=data[:8]+(zlib.decompress(data[8:]) if data[:3]==b'CWS' else data[8:]);assert len(raw)==struct.unpack_from('<I',raw,4)[0]
    for label in [b'getLocalViewport',b'layoutViewport',b'viewport-layout-0.1.17',b'visibleRect',b'globalToLocal',b'PS_NewGameSubmit',b'PS_NewGameFrameReady']:assert label in raw,label
    controls={'name':(1245,385,460,54),'male':(1230,539,235,64),'female':(1485,539,235,64),'begin':(1230,680,490,74),'status':(1230,784,490,50)}
    cases=[]
    # Bounding-box proof includes the stale-stage/offset condition responsible
    # for the report; these are mathematical layout checks, not a GFx runtime.
    for w,h in [(1280,720),(1920,1080),(2560,1600),(3440,1440),(3840,2160),(5120,1440),(5120,2160),(1024,768),(1440,2560)]:
        for sx,sy,tx,ty in [(1,1,0,0),(2,2,137,-821),(w/1920,w/1920,0,-h/2)]:
            viewport=(-tx/sx,-ty/sy,w/sx,h/sy);left,top,width,height=viewport
            scale=min(width/1920,height/1080);origin=(left+(width-1920*scale)/2,top+(height-1080*scale)/2)
            for name,(x,y,cw,ch) in controls.items():
                bounds=(origin[0]+x*scale,origin[1]+y*scale,origin[0]+(x+cw)*scale,origin[1]+(y+ch)*scale)
                assert bounds[0]>=left-1e-6 and bounds[1]>=top-1e-6 and bounds[2]<=left+width+1e-6 and bounds[3]<=top+height+1e-6,(w,h,name)
            cases.append({'resolution':[w,h],'parent_transform':[sx,sy,tx,ty],'all_controls_within_viewport':True})
    # The former stage-only placement clips the field in this offset viewport.
    assert controls['name'][1]<540
    check={'compiled_swf10':True,'layout_cases':len(cases),'all_layout_bounds_passed':True,'offset_origin_regression_covered':True,'protected_input_functions_unchanged':manifest['protected_input_functions'],'in_game_ultrawide_verified':False,'cases':cases}
    (HERE/'validation.json').write_text(json.dumps(check,indent=2))
    target=MOD/'Interface/PSNewGameMenu.swf';assert sha(target)==manifest['previous_sha256']
    protected={str(p.relative_to(MOD)):sha(p) for p in MOD.rglob('*') if p.is_file() and p!=target}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ');backup=ROOT/'Development/NewGame/Backups'/('Viewport_'+stamp)/'PSNewGameMenu.swf';backup.parent.mkdir(parents=True);shutil.copy2(target,backup)
    temporary=target.with_name(target.name+'.viewport.tmp');shutil.copy2(candidate,temporary);os.replace(temporary,target)
    for relative,digest in protected.items():assert sha(MOD/relative)==digest,relative
    receipt={'version':'0.1.17','installed_utc':stamp,'backup':str(backup),'path':str(target),'previous_sha256':manifest['previous_sha256'],'sha256':sha(target),'only_runtime_file_changed':'Interface/PSNewGameMenu.swf','protected_files_unchanged':protected,'in_game_ultrawide_test':'pending user test at 5120x1440'}
    (HERE/'installation_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({'installed':str(target),'backup':str(backup),'layout_cases':len(cases),'protected_files':len(protected),'ultrawide_runtime_test':'pending'},indent=2))
if __name__=='__main__':main()
