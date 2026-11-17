// Verify actual HTTP playback, seeking and native-state display on the cycle page.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
fs.copyFileSync(__filename,path.join(out,'executed_verification.cjs'));
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let page,report={result:'running'};const errors=[];
 try{
  page=await browser.newPage({viewport:{width:1200,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
  const response=await page.goto(url);assert.equal(response.status(),200);
  await page.waitForFunction(()=>document.querySelector('#audio').readyState>=1);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('#track option').count(),6);
  assert(await page.locator('#audio').evaluate(a=>a.paused&&!a.autoplay&&a.duration===32));
  assert(await page.locator('.intro').innerText().then(t=>t.includes('E尾排')&&t.includes('待听评')));
  await page.locator('#stages button').filter({hasText:'收油'}).click();
  await page.waitForFunction(()=>Math.abs(document.querySelector('#audio').currentTime-15.5)<.01&&!document.querySelector('#audio').seeking,null,{timeout:5000});
  await page.selectOption('#track','events');
  await page.waitForFunction(()=>{const a=document.querySelector('#audio');return a.dataset.source==='events.wav'&&a.readyState>=2&&!a.seeking&&Math.abs(a.currentTime-15.5)<.01;},null,{timeout:5000});
  await page.locator('#audio').evaluate(a=>{a.volume=.4;return a.play();});
  await page.selectOption('#track','mix');
  await page.waitForFunction(()=>{const a=document.querySelector('#audio');return a.dataset.source==='mix.wav'&&a.readyState>=2&&!a.paused&&a.currentTime>=15.5&&a.currentTime<17;});
  assert.equal(await page.locator('#audio').evaluate(a=>a.volume),.4);
  await page.locator('#audio').evaluate(a=>a.pause());
  await page.locator('#stages button').filter({hasText:'停车怠速'}).click();
  await page.locator('#audio').evaluate(a=>{a.currentTime=28.5;});
  await page.waitForFunction(()=>document.querySelector('#state').textContent.includes('怠速')&&Number(document.querySelector('#rpm').textContent.replaceAll(',',''))===850);
  await page.locator('#audio').evaluate(a=>{a.currentTime=31.5;});
  await page.waitForFunction(()=>document.querySelector('#state').textContent.includes('熄火')&&document.querySelector('#rpm').textContent==='0');
  await page.evaluate(()=>{const s=document.querySelector('#track');for(const id of ['events','low','detail','mix','dna']){s.value=id;s.dispatchEvent(new Event('change'));}});
  await page.waitForFunction(()=>{const a=document.querySelector('#audio');return a.dataset.source==='dna.wav'&&a.readyState>=2&&!a.seeking&&Math.abs(a.currentTime-31.5)<.01;});
  const metadata=await(await page.request.get(new URL('verification.json',url).href)).json();
  assert.equal(metadata.passed,true);assert.equal(metadata.afterfire_starts.length,1);
  for(const link of await page.locator('a').evaluateAll(a=>a.map(v=>v.href)))assert.equal((await page.request.get(link)).status(),200);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',HTTP200:true,one_player:true,no_autoplay:true,tracks:6,
   HTTP_seek_works:true,same_time_event_switch:true,playing_switch_and_volume:true,rapid_switch_last_wins:true,
   native_idle_and_off_telemetry:true,local_candidate_status_visible:true,desktop_mobile_no_overflow:true,automated_audio_muted:true});
 }catch(error){report.result='failed';report.error=String(error);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw error;}
 finally{report.errors=errors;report.verifier_sha256=require('crypto').createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
