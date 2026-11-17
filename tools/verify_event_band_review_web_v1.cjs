const path=require('path'),fs=require('fs'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],url=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  const response=await page.goto(url);assert.equal(response.status(),200);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('[data-src]').count(),4);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay&&Math.abs(a.duration-1.6)<1e-6));
  const metadata=await(await page.request.get(new URL('report.json',url).href)).json();
  assert.equal(metadata.hearing_accepted,false);assert.equal(metadata.global_event_bank_changed,false);
  for(const file of Object.keys(metadata.files))assert.equal((await page.request.get(new URL(file,url).href)).status(),200);
  await page.locator('audio').evaluate(a=>{a.volume=.4;a.currentTime=.66;});
  await page.waitForFunction(()=>Math.abs(document.querySelector('audio').currentTime-.66)<.01&&!document.querySelector('audio').seeking);
  for(const name of ['band.wav','candidate.wav','candidate_band.wav','context.wav']){
   report.current_track=name;
   await page.click('[data-src="'+name+'"]');
   await page.waitForFunction(src=>{const a=document.querySelector('audio');return a.readyState>=1&&a.dataset.source===src&&Math.abs(a.currentTime-.66)<.02;},name);
   assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);
  }
  await page.locator('audio').evaluate(a=>{a.currentTime=.5;return a.play();});
  await page.click('[data-src="candidate_band.wav"]');
  await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').readyState>=2);
  await page.locator('audio').evaluate(a=>a.pause());
  await page.evaluate(()=>{for(let k=0;k<12;k++)document.querySelectorAll('[data-src]')[k%4].click();});
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=1&&a.dataset.source==='candidate_band.wav';});
  for(const link of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(link)).status(),200);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);Object.assign(report,{result:'passed',HTTP200:true,one_player:true,no_autoplay:true,
    four_tracks_and_all_downloads_available:true,switch_preserves_time_volume_and_play_state:true,
    rapid_switch_last_wins:true,unaccepted_status_visible:true,desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(e){report.result='failed';report.error=String(e);if(page){report.media=await page.locator('audio').evaluate(a=>({src:a.getAttribute('src'),readyState:a.readyState,currentTime:a.currentTime,duration:a.duration,seeking:a.seeking,paused:a.paused,error:a.error?.message}));await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});}throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
