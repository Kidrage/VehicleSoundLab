const path=require('path'),fs=require('fs'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],url=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  const response=await page.goto(url);assert.equal(response.status(),200);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('[data-src]').count(),3);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay&&Math.abs(a.duration-6)<1e-6));
  const metadata=await(await page.request.get(new URL('report.json',url).href)).json();
  assert.equal(metadata.timbre_accepted,false);assert.equal(metadata.new_timbre_model,false);
  assert.equal(metadata.tracks[0].peak_rpm,1150);assert.equal(metadata.tracks[1].peak_rpm,2000);
  for(const file of Object.keys(metadata.files))assert.equal((await page.request.get(new URL(file,url).href)).status(),200);
  await page.locator('audio').evaluate(a=>{a.volume=.4;a.currentTime=1.1;});
  await page.waitForFunction(()=>Math.abs(document.querySelector('audio').currentTime-1.1)<.01&&!document.querySelector('audio').seeking);
  for(const file of ['flare2000.wav','reference.wav','default.wav']){
   await page.click('[data-src="'+file+'"]');
   await page.waitForFunction(src=>{const a=document.querySelector('audio');return a.readyState>=1&&a.dataset.source===src&&Math.abs(a.currentTime-1.1)<.02;},file);
   assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);
  }
  await page.locator('audio').evaluate(a=>a.play());await page.click('[data-src="flare2000.wav"]');
  await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').readyState>=2);
  await page.locator('audio').evaluate(a=>a.pause());
  await page.evaluate(()=>{for(let k=0;k<12;k++)document.querySelectorAll('[data-src]')[k%3].click();});
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=1&&a.dataset.source==='reference.wav';});
  assert(await page.locator('img').evaluate(a=>a.complete&&a.naturalWidth>100));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);Object.assign(report,{result:'passed',HTTP200:true,one_player:true,no_autoplay:true,
   three_tracks_available:true,seek_and_switch_preserve_time_volume_play_state:true,rapid_switch_last_wins:true,
   native_peaks_verified:true,rpm_plot_loaded:true,desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(error){report.result='failed';report.error=String(error);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw error;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exit(1);});
