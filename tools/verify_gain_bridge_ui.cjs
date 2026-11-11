// Real muted browser playback, not subjective listening.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'renders/gain_bridge_v1');
const file=path.join(root,'research/持续声层过渡试听V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('持续声层过渡试听V1.html'));
  await page.locator('#player').evaluate(a=>{a.muted=true;});
  async function ready(){
   await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert.equal(await page.locator('#player').evaluate(a=>a.muted),true);
   assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);
  }
  await ready();const cases=await page.locator('#case option').evaluateAll(xs=>xs.map(x=>x.value));let loads=0;
  for(const scene of cases){await page.selectOption('#case',scene);for(const method of ['hold','ramp']){await page.click(`[data-method=${method}]`);await ready();loads++;}}
  await page.selectOption('#case','neutral');await page.click('[data-method=hold]');await ready();
  await page.locator('#player').evaluate(a=>{a.currentTime=2.25;});await page.click('[data-method=ramp]');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-2.25)<.03);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('player').currentTime>2.3);
  await page.click('[data-method=hold]');await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  assert.equal(await page.locator('#transport').textContent(),'暂停');
  await page.route('**/audition_neutral_ramp.wav',async route=>{await new Promise(resolve=>setTimeout(resolve,250));await route.continue().catch(()=>{});});
  await page.evaluate(()=>{document.querySelector('[data-method=ramp]').click();document.querySelector('[data-method=hold]').click();document.querySelector('[data-method=ramp]').click();});
  await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  assert((await page.locator('#player').evaluate(a=>a.dataset.source)).endsWith('audition_neutral_ramp.wav'));
  assert(await page.locator('#player').evaluate(a=>a.currentTime>2.25));
  await page.unrouteAll({behavior:'wait'});await page.click('#transport');assert(await page.locator('#player').evaluate(a=>a.paused));
  await page.selectOption('#case','lift');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.01));
  await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('details').nth(1).evaluate(e=>{e.open=true;});await page.waitForFunction(()=>document.querySelector('img').complete&&document.querySelector('img').naturalWidth>0);
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>{a.muted=true;});await ready();
  await page.click('#transport');await page.waitForFunction(()=>document.getElementById('player').currentTime>.05);await page.click('#transport');
  assert.deepEqual(errors,[]);
  const report={result:'pass',cases:4,methods:2,audio_metadata_loads:loads,position_preserved:true,
   actual_muted_playback_and_transport:true,playing_state_preserved:true,obsolete_response_isolation:true,
   case_change_stops_at_zero:true,http_and_file_entry:true,figure_loaded:true,mobile_horizontal_overflow:false,javascript_errors:errors,
   scope:'Actual headless Chrome metadata, muted decoding/playback, seek/control switching and screenshots. No subjective acceptance or physical-array listening.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));process.stdout.write(JSON.stringify(report,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
