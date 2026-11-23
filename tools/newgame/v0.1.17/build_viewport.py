"""Build the viewport-only correction from the installed approved menu source."""
from pathlib import Path
import hashlib,json,re,subprocess,datetime
ROOT=Path(r'C:\Perdition Sector');HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent/'v0.1.10';MOD=ROOT/'mods/Perdition New Game - Test'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert sha(MOD/'Interface/PSNewGameMenu.swf')==sha(PRIOR/'package/Interface/PSNewGameMenu.swf'),'Installed menu differs from the approved source baseline'
    source=(PRIOR/'Source/PSNewGameRoot.as').read_text()
    source=source.replace('private var coverageReported:Boolean = false;','private var coverageReported:Boolean = false;\n        private var layoutViewport:Rectangle;\n        private var viewportSource:String = "stage-fallback";')
    start=source.index('        private function resizeLayout():void {')
    end=source.index('        private function pollApi(',start)
    replacement='''        private function getLocalViewport():Rectangle {
            var w:Number=stage != null && stage.stageWidth > 0 ? stage.stageWidth : 1920;
            var h:Number=stage != null && stage.stageHeight > 0 ? stage.stageHeight : 1080;
            var visible:Rectangle=new Rectangle(0,0,w,h);
            viewportSource="stage-fallback";
            if(stage != null) {
                try {
                    var extensions:Object=getDefinitionByName("scaleform.gfx.Extensions");
                    extensions.enabled=true;
                    var actual:Rectangle=extensions.visibleRect as Rectangle;
                    if(actual != null && isFinite(actual.x) && isFinite(actual.y) &&
                       isFinite(actual.width) && isFinite(actual.height) &&
                       actual.width > 0 && actual.height > 0) {
                        visible=actual.clone();viewportSource="scaleform-visibleRect";
                    }
                } catch(error:Error) {}
            }
            // visibleRect is in stage coordinates; content is a root child.
            // Include its origin and the root/parent transform in both axes.
            var corners:Array=[
                globalToLocal(new Point(visible.left,visible.top)),
                globalToLocal(new Point(visible.right,visible.top)),
                globalToLocal(new Point(visible.left,visible.bottom)),
                globalToLocal(new Point(visible.right,visible.bottom))];
            var left:Number=Number.POSITIVE_INFINITY;
            var top:Number=Number.POSITIVE_INFINITY;
            var right:Number=Number.NEGATIVE_INFINITY;
            var bottom:Number=Number.NEGATIVE_INFINITY;
            for each(var corner:Point in corners) {
                left=Math.min(left,corner.x);top=Math.min(top,corner.y);
                right=Math.max(right,corner.x);bottom=Math.max(bottom,corner.y);
            }
            if(!isFinite(left) || !isFinite(top) || !isFinite(right) || !isFinite(bottom) ||
               right <= left || bottom <= top) {
                return layoutViewport != null ? layoutViewport.clone() : new Rectangle(0,0,1920,1080);
            }
            return new Rectangle(left,top,right-left,bottom-top);
        }

        private function resizeLayout():void {
            var viewport:Rectangle=getLocalViewport();
            var changed:Boolean=layoutViewport == null ||
                Math.abs(viewport.x-layoutViewport.x) > 0.01 ||
                Math.abs(viewport.y-layoutViewport.y) > 0.01 ||
                Math.abs(viewport.width-layoutViewport.width) > 0.01 ||
                Math.abs(viewport.height-layoutViewport.height) > 0.01;
            if(changed) {
                var fit:Number=Math.min(viewport.width/1920,viewport.height/1080);
                content.scaleX=fit;content.scaleY=fit;
                content.x=viewport.left+(viewport.width-1920*fit)/2;
                content.y=viewport.top+(viewport.height-1080*fit)/2;
                resizeBackground(viewport);
                layoutViewport=viewport.clone();
            }
            if(api != null && stage != null && !coverageReported) {
                coverageReported=true;
                diagnostic("viewport-layout-0.1.17; source="+viewportSource+
                    "; viewport="+viewport.x+","+viewport.y+","+viewport.width+","+viewport.height+
                    "; content="+content.x+","+content.y+","+content.scaleX);
            }
        }

        private function resizeBackground(viewport:Rectangle):void {
            // Keep the approved small solid shape and transform-based overscan.
            var padX:Number=Math.max(256,viewport.width);
            var padY:Number=Math.max(256,viewport.height);
            backdrop.x=viewport.left-padX;backdrop.y=viewport.top-padY;
            backdrop.scaleX=(viewport.width+padX*2)/512;
            backdrop.scaleY=(viewport.height+padY*2)/512;
            backdrop.alpha=1.0;backdrop.visible=true;
            var bounds:Rectangle=backdrop.getBounds(this);
            BackgroundReady=isFinite(bounds.width) && isFinite(bounds.height) &&
                bounds.width > 0 && bounds.height > 0 &&
                bounds.left <= viewport.left && bounds.top <= viewport.top &&
                bounds.right >= viewport.right && bounds.bottom >= viewport.bottom;
        }

'''
    source=source[:start]+replacement+source[end:]
    source=source.replace('private function pollApi(event:Event):void {','private function pollApi(event:Event):void {\n            // Native viewport offsets can settle after ADDED_TO_STAGE/RESIZE.\n            resizeLayout();')
    (HERE/'Source').mkdir(parents=True,exist_ok=True);(HERE/'package/Interface').mkdir(parents=True,exist_ok=True)
    (HERE/'Source/PSNewGameRoot.as').write_text(source)
    previous=(PRIOR/'Source/PSNewGameRoot.as').read_text()
    protected=['FocusNameInput','ReleaseInput','onSubmit','choose','button','text','onKey','onKeyUp','submit','Notify','NativeRefresh','onF4SEObjCreated','onAdded','onRemoved']
    for name in protected:
        pat=r'(?ms)^        (?:public|private) function '+name+r'\(.*?^        }'
        assert re.search(pat,source).group()==re.search(pat,previous).group(),name
    tools=HERE.parent/'v0.1.0/Tools';java=next((tools/'JRE').glob('*/bin/java.exe'));flex=tools/'ApacheFlex'
    output=HERE/'package/Interface/PSNewGameMenu.swf'
    command=[str(java),'-Dflexlib='+str(flex/'frameworks'),'-jar',str(flex/'lib/mxmlc.jar'),'-load-config=','-target-player=10.1','-swf-version=10','-static-link-runtime-shared-libraries=true','-external-library-path='+str(tools/'FFDec/flashlib/playerglobal32_0.swc'),'-debug=false','-output='+str(output),str(HERE/'Source/PSNewGameRoot.as')]
    run=subprocess.run(command,text=True,capture_output=True,timeout=60);(HERE/'menu_compile.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
    result={'version':'0.1.17','previous_sha256':sha(MOD/'Interface/PSNewGameMenu.swf'),'sha256':sha(output),'bytes':output.stat().st_size,'changed_runtime_files':['Interface/PSNewGameMenu.swf'],'protected_input_functions':protected,'scope':'Shared actual visible viewport for background and content, including nonzero origins and root transforms; cached relayout also follows late native viewport changes.','in_game_ultrawide_confirmation':False}
    (HERE/'build_manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
