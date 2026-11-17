'use strict';
// One owned local blob makes WAV seeking independent of HTTP Range support.
// Each selection owns at most one object URL; abort/token prevent stale loads.
class VslEventPlayer {
 constructor(audio){this.audio=audio;this.serial=0;this.controller=null;this.url=null;}
 stop(){this.serial++;this.controller?.abort();this.controller=null;this.audio.pause();this.audio.removeAttribute('src');this.audio.load();if(this.url){URL.revokeObjectURL(this.url);this.url=null;}}
 async select(source,resume=false){
  this.stop();const serial=this.serial,controller=new AbortController();this.controller=controller;
  try{
   const response=await fetch(source,{signal:controller.signal});if(!response.ok)throw Error('试听音频载入失败：'+response.status);
   const blob=await response.blob();if(serial!==this.serial)return false;
   this.url=URL.createObjectURL(blob);this.audio.src=this.url;this.audio.load();this.controller=null;
   if(resume)await this.audio.play();return true;
  }catch(e){if(serial!==this.serial||e.name==='AbortError')return false;throw e;}
 }
}
window.VslEventPlayer=VslEventPlayer;
