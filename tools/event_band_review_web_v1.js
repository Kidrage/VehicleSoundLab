'use strict';
// Small local review assets use Blob URLs so seeking does not depend on the
// existing static server implementing HTTP Range. No new server is launched.
const player=document.querySelector('audio'),label=document.querySelector('#label');
const cache=new Map(),urls=new Set();let serial=0,loading=false,adopted;
function asset(file){
 if(!cache.has(file))cache.set(file,(async()=>{
  const response=await fetch(file);if(!response.ok)throw Error('音频载入失败：'+response.status);
  const url=URL.createObjectURL(await response.blob());urls.add(url);return url;
 })().catch(error=>{cache.delete(file);throw error;}));
 return cache.get(file);
}
async function select(button){
 const token=++serial;
 const state=loading?adopted:{time:player.currentTime,volume:player.volume,playing:!player.paused};
 adopted=state;loading=true;player.pause();label.textContent=button.textContent+' · 载入中';
 for(const other of document.querySelectorAll('[data-src]'))other.setAttribute('aria-pressed',String(other===button));
 try{
  const url=await asset(button.dataset.src);if(token!==serial)return;
  player.addEventListener('loadedmetadata',()=>{
   if(token!==serial)return;
   player.currentTime=Math.min(state.time,Math.max(0,player.duration-.001));player.volume=state.volume;
   loading=false;label.textContent=button.textContent;if(state.playing)player.play().catch(()=>{});
  },{once:true});
  player.src=url;player.dataset.source=button.dataset.src;player.load();
 }catch(error){if(token===serial){loading=false;label.textContent=error.message;}}
}
for(const button of document.querySelectorAll('[data-src]'))button.onclick=()=>select(button);
select(document.querySelector('[data-src]'));
window.addEventListener('pagehide',()=>{for(const url of urls)URL.revokeObjectURL(url);});
