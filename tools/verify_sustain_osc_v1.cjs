// Muted local audition QA, not a human naturalness check.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'references/analysis/sustain_osc_v1');
const file=path.join(root,'research/持续OSC统计声源V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:950}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('持续OSC统计声源V1.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  async function ready(){await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert(await page.locator('#player').evaluate(a=>a.muted));assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);}
  let loads=0;
  for(const method of ['reference','generated','mean']){await page.click(`[data-method=${method}]`);await ready();loads++;}
  await page.locator('summary').click();
  for(const method of ['other_seed','pitch_change']){await page.click(`[data-method=${method}]`);await ready();loads++;assert.equal(await page.locator('#player').evaluate(a=>a.duration),8);}
  await page.click('[data-method=generated]');await ready();await page.locator('#player').evaluate(a=>a.currentTime=3.2);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.click('[data-method=mean]');await ready();assert(await page.locator('#player').evaluate(a=>!a.paused&&a.currentTime>=3.2));
  await page.click('[data-method=reference]');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.04&&a.duration>1&&a.duration<1.3));
  await page.check('#repeat');assert(await page.locator('#player').evaluate(a=>a.loop));
  await page.click('[data-method=generated]');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.04&&a.loop));
  await page.uncheck('#repeat');assert(await page.locator('#player').evaluate(a=>!a.loop));
  await page.locator('summary').click();await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await ready();
  await page.click('[data-method=reference]');await ready();assert.deepEqual(errors,[]);
  const result={loads,muted:true,http_and_file:true,synth_position_playback_preserved:true,short_reference_resets:true,repeat_control:true,narrow_viewport:true,errors};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
