const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const {chromium}=require(path.join(process.argv[2],'playwright'));const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});let page;const report={result:'running'},errors=[];
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const fn=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return fn.call(this);};});
  assert.equal((await page.goto(url)).status(),200);const tracks=await(await page.request.get(new URL('tracks.json',url).href)).json();
  assert.equal(tracks.length,6);assert.equal(await page.locator('audio').count(),1);assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));
  report.decoded=[];
  const select=async index=>{const previous=await page.locator('audio').evaluate(a=>a.currentSrc);await page.click('[data-track="'+index+'"]');await page.waitForFunction(previous=>{const a=document.querySelector('audio');return a.currentSrc!==previous&&a.readyState>=2&&!a.seeking;},previous);};
  for(const [i,row] of tracks.entries()){
   const response=await page.request.get(new URL(row.file,url).href);assert.equal(response.status(),200);
   assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'),row.sha256);
   const decoded=await page.evaluate(async file=>{const c=new AudioContext();try{const a=await c.decodeAudioData(await(await fetch(file)).arrayBuffer());return {frames:a.length,channels:a.numberOfChannels};}finally{await c.close();}},row.file);
   assert.equal(decoded.frames,row.frames);assert.equal(decoded.channels,row.channels);report.decoded.push(decoded);
   await select(i);
   await page.locator('audio').evaluate(a=>{a.currentTime=Math.min(.3,a.duration/2);a.volume=.4;});
   await page.waitForFunction(()=>!document.querySelector('audio').seeking&&Math.abs(document.querySelector('audio').currentTime-.3)<.02);
  }
  await select(4);assert.equal(await page.locator('audio').evaluate(a=>a.duration),8);
  await page.locator('audio').evaluate(async a=>{a.currentTime=2.;await a.play();});
  await select(5);await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.duration===8&&!a.paused&&a.currentTime>=2&&a.currentTime<2.8;});
  await page.locator('audio').evaluate(a=>a.pause());assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);
  for(const href of await page.locator('a').evaluateAll(a=>a.map(x=>x.href)))assert.equal((await page.request.get(href)).status(),200);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',six_hashes_and_decodes:true,blob_switch_and_seek:true,playing_switch_position_and_volume_preserved:true,downloads_HTTP200:true,desktop_mobile:true,timbre_accepted:false});
 }catch(e){report.result='failed';report.error=String(e);throw e;}finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
