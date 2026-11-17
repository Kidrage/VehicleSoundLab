// Actual browser decoding, switching and downloads for this new source review.
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  assert.equal((await page.goto(url)).status(),200);
  const record=await(await page.request.get(new URL('report.json',url).href)).json();
  assert.equal(record.timbre_accepted,false);assert.equal(record.spatial_processing,false);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('[data-src]').count(),4);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=2);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay&&Math.abs(a.duration-.95)<1e-6));
  for(const [file,expected] of Object.entries(record.files)){
   const response=await page.request.get(new URL(file,url).href);assert.equal(response.status(),200);
   assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'),expected);
  }
  report.decoded=[];
  for(const track of record.tracks){
   const decoded=await page.evaluate(async file=>{
    const context=new AudioContext();try{
     const a=await context.decodeAudioData(await(await fetch(file)).arrayBuffer());
     return {duration:a.duration,channels:a.numberOfChannels,frames:a.length};
    }finally{await context.close();}
   },track.file);
   assert(Math.abs(decoded.duration-track.duration)<1e-6);report.decoded.push({file:track.file,...decoded});
  }
  await page.locator('audio').evaluate(a=>{a.currentTime=.3;a.volume=.4;});
  await page.waitForFunction(()=>!document.querySelector('audio').seeking&&Math.abs(document.querySelector('audio').currentTime-.3)<.01);
  for(const file of ['held.wav','decay.wav','reference.wav']){
   await page.click('[data-src="'+file+'"]');
   await page.waitForFunction(file=>{const a=document.querySelector('audio');return a.dataset.source===file&&a.readyState>=2&&!a.seeking&&Math.abs(a.currentTime-.3)<.01;},file);
  }
  await page.locator('audio').evaluate(a=>a.play());await page.click('[data-src="held.wav"]');
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=2&&!document.querySelector('audio').paused);
  assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);await page.locator('audio').evaluate(a=>a.pause());
  await page.click('[data-src="context.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.dataset.source==='context.wav'&&a.readyState>=2&&a.currentTime<.01;});
  for(const href of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(href)).status(),200);
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',one_player_no_autoplay:true,four_tracks_decoded:true,
   same_group_seek_volume_play_state_preserved:true,context_switch_resets:true,
   files_HTTP_sha_exact:true,all_downloads_HTTP200:true,desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
