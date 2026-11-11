// Actual muted browser decoding/transport; no subjective listening claim.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'renders/event_color_v1');
const file=path.join(root,'research/主排气逐次形状试听V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('主排气逐次形状试听V1.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  await page.locator('#reference').evaluate(a=>a.muted=true);
  async function ready(){
   await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert(await page.locator('#player').evaluate(a=>a.muted));
   assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);
  }
  await ready();const cases=await page.locator('#case option').evaluateAll(xs=>xs.map(x=>x.value));let loads=0;
  assert.equal(cases.length,7);
  for(const scene of cases){await page.selectOption('#case',scene);for(const method of ['fixed','half','full']){await page.click(`[data-method=${method}]`);await ready();loads++;}}
  await page.selectOption('#case','mid');await page.click('[data-method=fixed]');await ready();
  await page.locator('#player').evaluate(a=>a.currentTime=2.25);await page.click('[data-method=full]');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-2.25)<.03);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('player').currentTime>2.3);
  await page.click('[data-method=half]');await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.route('**/audition_mid_full.wav',async route=>{await new Promise(resolve=>setTimeout(resolve,250));await route.continue().catch(()=>{});});
  await page.evaluate(()=>{document.querySelector('[data-method=full]').click();document.querySelector('[data-method=fixed]').click();document.querySelector('[data-method=full]').click();});
  await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  assert((await page.locator('#player').evaluate(a=>a.dataset.source)).endsWith('audition_mid_full.wav'));
  await page.unrouteAll({behavior:'wait'});await page.click('#transport');assert(await page.locator('#player').evaluate(a=>a.paused));
  await page.selectOption('#case','lift');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.01));
  const refs=await page.locator('#referenceCase option').evaluateAll(xs=>xs.map(x=>x.value));assert.equal(refs.length,2);
  for(const ref of refs){await page.selectOption('#referenceCase',ref);await page.waitForFunction(()=>{const a=document.getElementById('reference');return a.readyState>=1&&Number.isFinite(a.duration)&&!a.error&&a.currentSrc===new URL(referenceSource(),location.href).href;});}
  await page.locator('#reference').evaluate(a=>a.play());await page.waitForFunction(()=>!document.getElementById('reference').paused&&document.getElementById('reference').currentTime>.05);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('reference').paused);
  await page.locator('#reference').evaluate(a=>a.play());await page.waitForFunction(()=>!document.getElementById('reference').paused&&document.getElementById('player').paused);
  await page.locator('#reference').evaluate(a=>a.pause());
  await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await page.locator('#reference').evaluate(a=>a.muted=true);await ready();
  await page.click('#transport');await page.waitForFunction(()=>document.getElementById('player').currentTime>.05);await page.click('#transport');
  assert.deepEqual(errors,[]);
  const report={result:'pass',cases:7,methods:3,audio_metadata_loads:loads,reference_loads:2,reference_and_synth_mutual_exclusion:true,position_preserved:true,
   actual_muted_playback_and_transport:true,playing_state_preserved:true,obsolete_response_isolation:true,
   case_change_stops_at_zero:true,http_and_file_entry:true,mobile_horizontal_overflow:false,javascript_errors:errors,
   scope:'Actual Chrome metadata, muted decoding/playback, controls and screenshots. No subjective acceptance or device-array listening.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));process.stdout.write(JSON.stringify(report,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
