// Headless checks of this project's own generated page; all playback muted.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const review=process.argv[3],out=process.argv[4],report=JSON.parse(fs.readFileSync(path.join(review,'report.json'),'utf8'));
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let combinations=0;
 try{
  const page=await browser.newPage({viewport:{width:1000,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(report.url);await page.waitForFunction(()=>document.querySelector('#audio').readyState>=1);
  await page.locator('#audio').evaluate(p=>p.muted=true);assert(await page.locator('#audio').evaluate(p=>p.paused));
  async function change(id,value){
   await page.locator('#audio').evaluate(p=>{window.__nextMetadata=false;p.addEventListener('loadedmetadata',()=>{window.__nextMetadata=true},{once:true});});
   await page.selectOption(id,value);await page.waitForFunction(()=>window.__nextMetadata&&document.querySelector('#audio').readyState>=1);
  }
  async function check(key){const row=report.clips.find(r=>r.key===key);assert(row,key);
   assert(await page.locator('#audio').evaluate((p,seconds)=>!p.error&&Math.abs(p.duration-seconds)<.001,row.frames/48000));combinations++;
  }
  for(const scene of ['1','2','3']){
   await change('#scene',scene);await change('#variant','original');await check(scene+'_original_mix');
   assert(await page.locator('#seed').isDisabled());assert(await page.locator('#bus').isDisabled());
   await change('#variant','reference');await check(scene+'_reference_mix');
   await change('#variant','candidate');
   for(const bus of ['mix','detail']){await change('#bus',bus);
    for(const seed of ['8121907','23117','61927']){await change('#seed',seed);await check(scene+'_candidate_'+bus+'_'+seed);}
   }
  }
  for(const scene of ['neutral','shifts']){
   await change('#scene',scene);assert(await page.locator('#seed').isDisabled());
   assert(await page.locator('#variant option[value="reference"]').isDisabled());
   await change('#variant','original');await check(scene+'_original_mix');
   await change('#variant','candidate');await change('#bus','mix');await check(scene+'_candidate_mix');
   await change('#bus','detail');await check(scene+'_candidate_detail');
  }
  await change('#bus','mix');await page.locator('#audio').evaluate(p=>{p.currentTime=6;p.dispatchEvent(new Event('timeupdate'));});
  const expected=await page.evaluate(()=>data.traces.shifts[1200].rpm);assert((await page.locator('#state').textContent()).includes(Math.round(expected)+' RPM'));
  const supported=await page.evaluate(()=>{const at=data.traces.shifts.findIndex(r=>r.detail_support>.5),p=document.querySelector('#audio');p.currentTime=at/200;p.dispatchEvent(new Event('timeupdate'));return Math.round(100*data.traces.shifts[at].detail_support)});
  assert((await page.locator('#state').textContent()).includes('细节支持 '+supported+'%'));
  await change('#variant','original');assert((await page.locator('#state').textContent()).includes('细节支持 0%'));
  await change('#variant','candidate');await page.locator('#audio').evaluate(p=>{p.currentTime=6;p.dispatchEvent(new Event('timeupdate'));});
  await page.locator('#audio').evaluate(async p=>{await p.play()});
  await page.waitForFunction(()=>!document.querySelector('#audio').paused);await change('#variant','original');
  assert(await page.locator('#audio').evaluate(p=>p.muted&&!p.paused&&p.currentTime>=6&&p.currentTime<7));
  await page.locator('#audio').evaluate(p=>p.pause());assert.equal(await page.locator('audio').count(),1);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('details').evaluate(e=>e.open=true);
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',combinations,defaults_stopped:true,single_player:true,
   muted_playback:true,playing_switch_and_seek:true,actual_telemetry_display_checked:true,mobile_overflow:false,
   javascript_errors:errors,scope:'Own generated browser page only; no human hearing or native device acceptance.'},null,2)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)},null,2)+'\n');throw e;}
 finally{await browser.close();}
})();
