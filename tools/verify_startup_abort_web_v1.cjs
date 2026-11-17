const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
fs.copyFileSync(__filename,path.join(out,'executed_verification.cjs'));
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let page,report={result:'running'};const errors=[];
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  assert.equal((await page.goto(url)).status(),200);assert.equal(await page.locator('audio').count(),1);
  assert.equal(await page.locator('[data-src]').count(),5);
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.readyState>=2&&a.duration===4;});
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));
  await page.locator('audio').evaluate(a=>{a.currentTime=1.25;a.volume=.4;});
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return !a.seeking&&Math.abs(a.currentTime-1.25)<.01;});
  for(const file of ['new-mix.wav','old-events.wav','new-events.wav']){
   await page.click('[data-src="'+file+'"]');
   await page.waitForFunction(file=>{const a=document.querySelector('audio');return a.dataset.source===file&&a.readyState>=2&&!a.seeking&&Math.abs(a.currentTime-1.25)<.01;},file);
  }
  await page.locator('audio').evaluate(a=>a.play());await page.click('[data-src="old-events.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.dataset.source==='old-events.wav'&&!a.paused&&a.currentTime>=1.25&&a.currentTime<2;});
  assert.equal(await page.locator('audio').evaluate(a=>a.volume),.4);await page.locator('audio').evaluate(a=>a.pause());
  await page.click('[data-src="A-reference.wav"]');
  await page.waitForFunction(()=>{const a=document.querySelector('audio');return a.dataset.source==='A-reference.wav'&&a.readyState>=1&&a.duration===5.5&&a.currentTime<.01;});
  const record=await(await page.request.get(new URL('report.json',url).href)).json();
  assert(record.old.has_event_tail_after_OFF&&!record.new.has_event_tail_after_OFF);
  for(const file of Object.keys(record.files))assert.equal((await page.request.get(new URL(file,url).href)).status(),200);
  for(const link of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(link)).status(),200);
  assert(await page.locator('img').evaluate(i=>i.complete&&i.naturalWidth>100));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',HTTP200:true,one_player:true,no_autoplay:true,HTTP_seek_and_switch:true,
   playing_switch_and_volume:true,reference_resets_time:true,all_audio_downloads_and_image_available:true,
   desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(error){report.result='failed';report.error=String(error);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw error;}
 finally{report.errors=errors;report.verifier_sha256=crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
