const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const original=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return original.call(this);};});
  assert.equal((await page.goto(url)).status(),200);
  const record=await(await page.request.get(new URL('report.json',url).href)).json();
  assert.equal(record.timbre_accepted,false);assert.equal(record.spatial_processing,false);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('[data-id]').count(),6);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=2);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay&&a.currentTime===0));
  for(const [file,hash] of Object.entries(record.files)){
   const response=await page.request.get(new URL(file,url).href);assert.equal(response.status(),200);
   assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'),hash);
  }
  report.decoded=[];
  for(const track of record.tracks){
   const decoded=await page.evaluate(async file=>{const ctx=new AudioContext();try{
    const buffer=await ctx.decodeAudioData(await(await fetch(file)).arrayBuffer());
    return {duration:buffer.duration,frames:buffer.length,channels:buffer.numberOfChannels};
   }finally{await ctx.close();}},track.file);
   assert.equal(decoded.frames,track.frames);assert.equal(decoded.channels,track.channels);
   report.decoded.push({file:track.file,...decoded});
  }
  await page.locator('audio').evaluate(a=>{a.currentTime=1.85;a.volume=.4;});
  await page.waitForFunction(()=>!document.querySelector('audio').seeking);
  for(const id of ['original','fixed','timing','continuous','events','reference']){
   const expected=id==='reference'?1.85:.558;await page.click('[data-id="'+id+'"]');
   await page.waitForFunction(({id,expected})=>{const a=document.querySelector('audio');return a.dataset.source===id&&a.readyState>=2&&!a.seeking&&Math.abs(a.currentTime-expected)<.01;},{id,expected});
   assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);
  }
  await page.click('#cue');await page.waitForFunction(()=>!document.querySelector('audio').seeking&&Math.abs(document.querySelector('audio').currentTime-1.65)<.01);
  await page.locator('audio').evaluate(a=>a.play());await page.click('[data-id="fixed"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.dataset.source==='fixed'&&a.readyState>=2&&!a.paused;});
  await page.locator('audio').evaluate(a=>a.pause());
  for(const href of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(href)).status(),200);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',one_player_no_autoplay:true,six_tracks_decode_exact:true,
   relative_marker_seek_preserved:true,volume_and_play_state_preserved:true,cue_button_verified:true,
   HTTP_sha_exact:true,downloads_HTTP200:true,desktop_mobile_no_overflow:true,audio_muted:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
