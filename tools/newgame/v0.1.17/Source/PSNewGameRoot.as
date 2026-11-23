package {
    import flash.display.MovieClip;
    import flash.display.Sprite;
    import flash.display.StageAlign;
    import flash.display.StageScaleMode;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.events.KeyboardEvent;
    import flash.events.TextEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.text.TextFormatAlign;
    import flash.text.TextFieldType;
    import flash.ui.Keyboard;
    import flash.geom.Rectangle;
    import flash.geom.Point;
    import flash.utils.getDefinitionByName;

    [SWF(width="1920", height="1080", backgroundColor="#10191f", frameRate="30")]
    public dynamic class PSNewGameRoot extends MovieClip {
        public var BackgroundAlpha:Number = 1.0;
        private var backdrop:Sprite;
        public var BackgroundReady:Boolean = false;
        private var content:Sprite;
        private var api:Object;
        private var nameInput:TextField;
        private var status:TextField;
        private var male:Sprite;
        private var female:Sprite;
        private var deploy:Sprite;
        private var sex:int = 0;
        private var busy:Boolean = false;
        private var ready:Boolean = false;
        private var updatingFrames:int = 0;
        private var frameReadySent:Boolean = false;
        private var ownsTextInput:Boolean = false;
        private var firstKeySeen:Boolean = false;
        private var firstTextSeen:Boolean = false;
        private var coverageReported:Boolean = false;
        private var layoutViewport:Rectangle;
        private var viewportSource:String = "stage-fallback";

        public function PSNewGameRoot() {
            super();
            // Use the same solid Graphics fill as the working menu panels.
            // Keep path coordinates small; resize through the transform.
            backdrop=new Sprite();backdrop.mouseEnabled=false;backdrop.mouseChildren=false;
            backdrop.graphics.beginFill(0x10191F,1.0);
            backdrop.graphics.drawRect(0,0,512,512);
            backdrop.graphics.endFill();addChild(backdrop);
            content=new Sprite();addChild(content);
            background();
            text("PERDITION",150,230,1050,140,108,0xD9DEDC,true);
            text("SECTOR",156,357,1050,105,78,0xB1B9B6,true);
            text("ENTER THE FOG",160,493,820,40,22,0x8D9A96);
            var panel:Sprite=new Sprite();
            panel.graphics.beginFill(0x0A1012,1.0);panel.graphics.drawRect(1190,165,570,720);panel.graphics.endFill();content.addChild(panel);
            content.graphics.lineStyle(2,0x8A9D94,0.7);content.graphics.moveTo(1230,195);content.graphics.lineTo(1720,195);
            text("NEW CAMPAIGN",1230,229,500,55,32,0xD9DEDC,true);
            text("NAME",1230,334,480,32,18,0x9EAAA5);
            nameInput=text("",1245,385,460,54,29,0xE2E7E4);
            nameInput.type=TextFieldType.INPUT;nameInput.selectable=true;nameInput.mouseEnabled=true;nameInput.maxChars=32;
            nameInput.multiline=false;nameInput.wordWrap=false;nameInput.tabEnabled=true;nameInput.tabIndex=1;
            nameInput.restrict="A-Za-z0-9 ._'\\-";
            nameInput.background=true;nameInput.backgroundColor=0x141D20;
            nameInput.border=true;nameInput.borderColor=0x52665C;
            nameInput.addEventListener(MouseEvent.MOUSE_UP,onNameClick);
            nameInput.addEventListener(TextEvent.TEXT_INPUT,onTextInput);
            nameInput.addEventListener(Event.CHANGE,onNameChanged);
            text("GENDER",1230,489,480,30,18,0x9EAAA5);
            male=button("MALE",1230,539,235,64,onMale);
            female=button("FEMALE",1485,539,235,64,onFemale);
            deploy=button("BEGIN CAMPAIGN",1230,680,490,74,onSubmit);
            status=text("Preparing campaign...",1230,784,490,50,17,0x91A39A);
            choose(0);
            if(stage != null) onAdded(null);
            else addEventListener(Event.ADDED_TO_STAGE,onAdded);
            addEventListener(Event.REMOVED_FROM_STAGE,onRemoved);
            addEventListener(Event.ENTER_FRAME,pollApi);
        }

        private function onAdded(event:Event):void {
            removeEventListener(Event.ADDED_TO_STAGE,onAdded);
            if(stage != null) {
                stage.scaleMode=StageScaleMode.NO_SCALE;
                stage.align=StageAlign.TOP_LEFT;
                stage.addEventListener(Event.RESIZE,onResize);
                resizeLayout();
                stage.stageFocusRect=false;
                stage.addEventListener(KeyboardEvent.KEY_DOWN,onKey,true,100);
                stage.addEventListener(KeyboardEvent.KEY_UP,onKeyUp,true,100);
            }
        }

        private function onRemoved(event:Event):void {
            ReleaseInput();
            if(stage != null) stage.removeEventListener(Event.RESIZE,onResize);
        }

        private function onResize(event:Event):void {resizeLayout();}

        private function getLocalViewport():Rectangle {
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

        private function pollApi(event:Event):void {
            // Native viewport offsets can settle after ADDED_TO_STAGE/RESIZE.
            resizeLayout();
            if(api == null && this.hasOwnProperty("f4se") && this["f4se"] != null) onF4SEObjCreated(this["f4se"]);
            if(api != null && stage != null && visible && alpha > 0 && !frameReadySent) {
                updatingFrames++;
                if(updatingFrames >= 2) {
                    resizeLayout();
                    if(BackgroundReady) {
                        frameReadySent=true;
                        diagnostic("background-coverage-confirmed; width="+backdrop.width+"; height="+backdrop.height);
                        api.SendExternalEvent("PS_NewGameFrameReady");
                        FocusNameInput();
                    } else if(updatingFrames == 2) {
                        diagnostic("background-invalid-bounds; opening fade retained");
                    }
                }
            }
            if(ready && !busy && stage != null && stage.focus == null) FocusNameInput();
        }

        public function onF4SEObjCreated(value:Object):void {
            api=value;
            resizeLayout();
            if(!ready) {ready=true;SetState("Enter your name to begin.");}
            FocusNameInput();
            api.SendExternalEvent("PS_NewGameMenuReady");
        }

        public function FocusNameInput():void {
            if(!ready || busy || api == null || stage == null) return;
            if(!ownsTextInput) {api.AllowTextInput(true);ownsTextInput=true;}
            nameInput.type=TextFieldType.INPUT;
            nameInput.selectable=true;
            var changed:Boolean=stage.focus != nameInput;
            stage.focus=nameInput;
            nameInput.setSelection(nameInput.length,nameInput.length);
            if(changed) diagnostic("name-field-focused");
        }

        private function diagnostic(phase:String):void {
            if(api != null) api.SendExternalEvent("PS_NewGameUiTrace",phase,nameInput.length);
        }

        private function onNameClick(event:MouseEvent):void {FocusNameInput();}
        private function onTextInput(event:TextEvent):void {
            if(!firstTextSeen) {firstTextSeen=true;diagnostic("text-input-received");}
        }
        private function onNameChanged(event:Event):void {
            if(nameInput.length == 1) diagnostic("first-character-entered");
        }

        public function SetState(message:String):void {if(status != null) status.text=message;}

        public function Notify(modName:String,settingId:String):void {
            if(api != null) {
                api.SendExternalEvent("OnMCMSettingChange",modName,settingId);
                api.SendExternalEvent("OnMCMSettingChange|"+modName,modName,settingId);
            }
        }

        public function NativeRefresh(plugin:String,functionName:String):void {
            if(api != null && api.plugins != null && api.plugins[plugin] != null) {
                var handler:Object=api.plugins[plugin];
                if(handler[functionName] is Function) handler[functionName].apply(handler,[]);
            }
        }

        public function ReleaseInput():void {
            if(api != null && ownsTextInput) {api.AllowTextInput(false);ownsTextInput=false;}
            if(stage != null) {
                stage.removeEventListener(KeyboardEvent.KEY_DOWN,onKey,true);
                stage.removeEventListener(KeyboardEvent.KEY_UP,onKeyUp,true);
            }
        }

        private function onKey(event:KeyboardEvent):void {
            if(!firstKeySeen) {firstKeySeen=true;diagnostic("keyboard-event-received");}
            if(event.keyCode == Keyboard.ESCAPE && !busy) {
                if(api != null) api.SendExternalEvent("PS_NewGameCancel");
                event.preventDefault();event.stopImmediatePropagation();return;
            }
            if(event.keyCode == Keyboard.ENTER) {submit();event.preventDefault();event.stopImmediatePropagation();}
        }

        private function onKeyUp(event:KeyboardEvent):void {
            if(event.keyCode == Keyboard.ENTER || event.keyCode == Keyboard.ESCAPE) {
                event.preventDefault();event.stopImmediatePropagation();
            }
        }

        public function ProcessUserEvent(control:String,isDown:Boolean):Boolean {
            if(isDown && control == "Cancel" && !busy && api != null) {
                api.SendExternalEvent("PS_NewGameCancel");return true;
            }
            if(isDown && (control == "Accept" || control == "Activate") && !busy) submit();
            return true;
        }
        private function onMale(event:MouseEvent):void {choose(0);FocusNameInput();}
        private function onFemale(event:MouseEvent):void {choose(1);FocusNameInput();}
        private function onSubmit(event:MouseEvent):void {submit();}

        private function submit():void {
            if(busy || !ready || api == null) return;
            var chosen:String=nameInput.text.replace(/^\s+|\s+$/g,"");
            if(chosen.length == 0) {status.text="Please enter your name.";FocusNameInput();diagnostic("empty-name-blocked");return;}
            diagnostic("submitting");
            busy=true;male.mouseEnabled=false;female.mouseEnabled=false;deploy.mouseEnabled=false;nameInput.type=TextFieldType.DYNAMIC;
            status.text="Preparing your campaign...";
            if(ownsTextInput) {api.AllowTextInput(false);ownsTextInput=false;}
            api.SendExternalEvent("PS_NewGameSubmit",chosen,sex == 0 ? "male" : "female");
        }

        private function choose(value:int):void {
            if(busy) return;
            sex=value;male.alpha=value == 0 ? 1 : 0.45;female.alpha=value == 1 ? 1 : 0.45;
        }

        private function text(value:String,xValue:Number,yValue:Number,w:Number,h:Number,size:int,color:uint,bold:Boolean=false):TextField {
            var field:TextField=new TextField();field.x=xValue;field.y=yValue;field.width=w;field.height=h;
            field.defaultTextFormat=new TextFormat("$MAIN_Font",size,color,bold);
            field.text=value;field.selectable=false;field.mouseEnabled=false;content.addChild(field);return field;
        }

        private function button(label:String,xValue:Number,yValue:Number,w:Number,h:Number,action:Function):Sprite {
            var sprite:Sprite=new Sprite();sprite.x=xValue;sprite.y=yValue;sprite.buttonMode=true;sprite.mouseChildren=false;
            sprite.graphics.lineStyle(1,0x799186);sprite.graphics.beginFill(0x263A31,0.96);sprite.graphics.drawRect(0,0,w,h);sprite.graphics.endFill();
            var field:TextField=new TextField();field.x=15;field.y=18;field.width=w-30;field.height=40;
            field.defaultTextFormat=new TextFormat("$MAIN_Font",22,0xE1E7E3,true,null,null,null,null,TextFormatAlign.CENTER);
            field.text=label;field.selectable=false;sprite.addChild(field);
            sprite.addEventListener(MouseEvent.CLICK,action);content.addChild(sprite);return sprite;
        }

        private function background():void {
            resizeLayout();
        }
    }
}
