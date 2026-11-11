// Local, seekable comparison playback. No DSP, normalization or autoplay.
class SeekableReviewPlayer {
 constructor(host,button,onError){
  this.host=host;this.button=button;this.onError=onError;this.current=null;this.serial=0;
  button.addEventListener('click',()=>{const a=this.current?.audio;if(!this.current?.ready)return;if(a.paused)a.play().catch(()=>onError('请重试播放'));else a.pause();});
 }
 select(source,preserve){
  source=new URL(source,location.href).href;
  const old=this.current;if(preserve&&old?.ready&&old.audio.dataset.source===source)return;
  const position=preserve&&old?(old.ready?old.audio.currentTime:old.position):0;
  const playing=Boolean(preserve&&old&&(old.ready?!old.audio.paused:old.playing));
  const muted=old?old.audio.muted:false,token=++this.serial;
  if(old){old.controller?.abort();old.audio.pause();old.audio.removeAttribute('src');old.audio.load();if(old.objectUrl)URL.revokeObjectURL(old.objectUrl);}
  const a=document.createElement('audio');a.id='player';a.controls=true;a.preload='metadata';a.muted=muted;a.dataset.source=source;
  this.current={audio:a,ready:false,position,playing,controller:null,objectUrl:null};
  this.host.replaceChildren(a);this.host.setAttribute('aria-busy','true');this.button.disabled=true;this.button.textContent='播放';
  a.addEventListener('loadedmetadata',()=>{
   if(token!==this.serial)return;this.current.ready=true;this.host.setAttribute('aria-busy','false');this.button.disabled=false;
   a.currentTime=Math.min(position,Math.max(0,a.duration-.02));
   if(playing)a.play().catch(e=>{if(token===this.serial&&e.name!=='AbortError')this.onError('请按播放');});
  },{once:true});
  a.addEventListener('play',()=>{if(token===this.serial){this.current.playing=true;this.button.textContent='暂停';}});
  a.addEventListener('pause',()=>{if(token===this.serial&&this.current.ready){this.current.playing=false;this.button.textContent='播放';}});
  a.addEventListener('error',()=>{if(token===this.serial){this.host.setAttribute('aria-busy','false');this.onError('音频加载失败，请检查本地文件');}});
  if(location.protocol==='http:'||location.protocol==='https:'){
   const controller=new AbortController();this.current.controller=controller;
   fetch(source,{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.blob();}).then(blob=>{
    if(token!==this.serial)return;const objectUrl=URL.createObjectURL(blob);this.current.objectUrl=objectUrl;a.src=objectUrl;a.load();
   }).catch(e=>{if(token===this.serial&&e.name!=='AbortError'){this.host.setAttribute('aria-busy','false');this.onError('音频加载失败，请检查本地服务');}});
  }else{a.src=source;a.load();}
 }
}
