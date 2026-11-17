// Bounded headless browser test of local static artifacts; no persistent server.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),{pathToFileURL}=require('url');
const folder=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let report={result:'running'};
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1050}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(folder,'index.html')).href);
  await page.waitForFunction(()=>document.querySelector('#audio').readyState>=1);
  assert.equal(await page.locator('audio').count(),1);
  assert(await page.locator('#audio').evaluate(a=>a.paused&&!a.autoplay&&Math.abs(a.duration-32)<1e-8));
  assert.equal(await page.locator('#track option').count(),6);assert.equal(await page.locator('#stages button').count(),7);
  await page.locator('#audio').evaluate(a=>{a.currentTime=7.5;});
  await page.waitForFunction(()=>Number(document.querySelector('#rpm').textContent.replaceAll(',',''))>1500);
  await page.selectOption('#track','dna');
  await page.waitForFunction(()=>document.querySelector('#audio').currentSrc.endsWith('/dna.wav')&&Math.abs(document.querySelector('#audio').currentTime-7.5)<.001);
  assert.equal(await page.locator('#audio').evaluate(a=>a.volume),1);
  await page.locator('#audio').evaluate(a=>{a.muted=true;a.volume=.4;return a.play();});
  await page.waitForTimeout(200);await page.selectOption('#track','events');
  await page.waitForFunction(()=>document.querySelector('#audio').currentSrc.endsWith('/events.wav')&&!document.querySelector('#audio').paused);
  assert.equal(await page.locator('#audio').evaluate(a=>a.volume),.4);
  await page.locator('#audio').evaluate(a=>a.pause());
  for(const id of ['low','detail','mix','idle','events','dna','mix'])await page.selectOption('#track',id);
  await page.waitForFunction(()=>document.querySelector('#audio').currentSrc.endsWith('/mix.wav')&&document.querySelector('#audio').readyState>=1);
  await page.locator('#stages button').filter({hasText:'制动降挡'}).click();
  await page.waitForFunction(()=>Math.abs(document.querySelector('#audio').currentTime-18)<.001);
  await page.locator('#audio').evaluate(a=>{a.currentTime=7.5;a.volume=1;});
  await page.waitForFunction(()=>document.querySelector('#throttle').value>.9);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(80);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  report={result:'passed',one_player:true,no_autoplay:true,tracks:6,seek_and_switch_preserve_time:true,
    playing_switch_continues:true,volume_preserved:true,rapid_switch_stable:true,actual_telemetry:true,
    desktop_mobile_no_overflow:true,errors,extra_monitor_gain:await page.evaluate(()=>VSL_LIFECYCLE.extra_monitor_gain),
    spatial_processing:await page.evaluate(()=>VSL_LIFECYCLE.spatial_processing)};
 }finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack));console.error(e);process.exitCode=1;});
