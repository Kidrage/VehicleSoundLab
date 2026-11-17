const path=require('path'),fs=require('fs'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  assert.equal((await page.goto(url)).status(),200);assert.equal(await page.locator('audio').count(),1);
  assert.equal(await page.locator('[data-src]').count(),11);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=2);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay&&a.duration===32));
  await page.locator('audio').evaluate(a=>{a.volume=.4;a.currentTime=1.1;});
  await page.waitForFunction(()=>!document.querySelector('audio').seeking&&Math.abs(document.querySelector('audio').currentTime-1.1)<.01);
  for(const file of ['candidate-mix.wav','original-events.wav','candidate-events.wav']){
   await page.click('[data-src="'+file+'"]');await page.waitForFunction(file=>{const a=document.querySelector('audio');return a.dataset.source===file&&a.readyState>=2&&!a.seeking&&Math.abs(a.currentTime-1.1)<.01;},file);
  }
  await page.locator('audio').evaluate(a=>a.play());await page.click('[data-src="original-mix.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.dataset.source==='original-mix.wav'&&a.readyState>=2&&!a.paused;});
  assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);await page.locator('audio').evaluate(a=>a.pause());
  for(const [file,duration] of [['catch-new.wav',1.2],['source.wav',5.5],['crank-old.wav',1.2]]){
   await page.click('[data-src="'+file+'"]');await page.waitForFunction(([file,d])=>{const a=document.querySelector('audio');return a.dataset.source===file&&a.readyState>=2&&Math.abs(a.duration-d)<1e-6&&a.currentTime<.01;},[file,duration]);
  }
  const record=await(await page.request.get(new URL('report.json',url).href)).json();
  for(const track of record.tracks)assert.equal((await page.request.get(new URL(track.file,url).href)).status(),200);
  for(const link of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(link)).status(),200);
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);Object.assign(report,{result:'passed',HTTP200:true,eleven_tracks:true,one_player_no_autoplay:true,
   same_group_seek_and_play_state_preserved:true,group_change_resets_time:true,volume_preserved:true,
   all_audio_and_downloads_available:true,desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.copyFileSync(__filename,path.join(out,'executed_verification.cjs'));fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
