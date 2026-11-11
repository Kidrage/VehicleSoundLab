// Test this local project's player in a headless, muted browser.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'renders/firing_pulse_v1');
const file=path.join(root,'research/逐缸压力源试听V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1050,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('逐缸压力源试听V1.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  await page.locator('#reference').evaluate(a=>a.muted=true);
  async function ready(){
   await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert(await page.locator('#player').evaluate(a=>a.muted));
   assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);
  }
  const cases=['mid','high','neutral'],methods=['original','steady','varying'];let loads=0;
  for(const scene of cases){await page.selectOption('#case',scene);for(const method of methods){await page.click(`[data-method=${method}]`);await ready();loads++;}}
  await page.selectOption('#case','mid');await page.click('[data-method=original]');await ready();
  await page.locator('#player').evaluate(a=>a.currentTime=.8);await page.click('[data-method=varying]');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-.8)<.03);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('player').currentTime>.85);
  await page.click('[data-method=steady]');await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.selectOption('#case','neutral');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.01));
  await page.locator('details').nth(1).locator('summary').click();
  await page.locator('#reference').evaluate(a=>a.play());await page.waitForFunction(()=>!document.getElementById('reference').paused);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('reference').paused);
  await page.locator('#reference').evaluate(a=>a.play());await page.waitForFunction(()=>!document.getElementById('reference').paused&&document.getElementById('player').paused);
  await page.locator('#reference').evaluate(a=>a.pause());
  await page.locator('details').nth(1).locator('summary').click();
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await ready();
  await page.click('[data-method=varying]');await ready();await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused);await page.click('#transport');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify({loads,muted:true,http_and_file:true,position_and_playback_preserved:true,scene_reset:true,reference_exclusion:true,narrow_viewport:true,errors},null,2));
  process.stdout.write('Nine files decoded; transport,position,reference exclusion,file/HTTP,mobile passed.\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
