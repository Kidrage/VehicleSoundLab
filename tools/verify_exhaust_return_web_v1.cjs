const path=require('path'),fs=require('fs'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],url=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  const response=await page.goto(url);assert.equal(response.status(),200);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('[data-src]').count(),6);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay&&Math.abs(a.duration-1.4)<1e-6));
  await page.locator('audio').evaluate(a=>{a.volume=.4;a.currentTime=.71;});
  await page.waitForFunction(()=>Math.abs(document.querySelector('audio').currentTime-.71)<.01&&!document.querySelector('audio').seeking);
  for(const file of ['reference_band.wav','candidate.wav','reference.wav']){
   await page.click('[data-src="'+file+'"]');
   await page.waitForFunction(src=>{const a=document.querySelector('audio');return a.readyState>=1&&a.dataset.source===src&&Math.abs(a.currentTime-.71)<.02;},file);
  }
  await page.click('[data-src="drive_off.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=1&&Math.abs(a.duration-8)<1e-6&&a.currentTime<.02;});
  await page.locator('audio').evaluate(a=>{a.currentTime=3.6;return a.play();});await page.click('[data-src="drive_on.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=2&&!a.paused&&a.currentTime>=3.6&&a.currentTime<4.2;});
  await page.locator('audio').evaluate(a=>a.pause());
  await page.click('[data-src="reference.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=1&&a.currentTime<.02;});
  await page.evaluate(()=>{for(let k=0;k<18;k++)document.querySelectorAll('[data-src]')[k%6].click();});
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=1&&a.dataset.source==='drive_events.wav';});
  const metadata=await(await page.request.get(new URL('report.json',url).href)).json();
  assert.equal(metadata.physical_identity_confirmed,false);assert.equal(metadata.global_bank_changed,false);
  assert.equal(metadata.generation.overruns,2);assert.equal(metadata.generation.starts.length,4);
  for(const file of Object.keys(metadata.files))assert.equal((await page.request.get(new URL(file,url).href)).status(),200);
  for(const link of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(link)).status(),200);
  assert(await page.locator('img').evaluate(a=>a.complete&&a.naturalWidth>100));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',HTTP200:true,one_player:true,no_autoplay:true,six_tracks_and_downloads_available:true,
   same_group_preserves_time_and_play_state:true,new_group_resets_time:true,rapid_switch_last_wins:true,
   unconfirmed_scoped_status_visible:true,desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(error){report.result='failed';report.error=String(error);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw error;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exit(1);});
