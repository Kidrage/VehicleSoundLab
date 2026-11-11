// This project's local player; browser runs muted, never drives other apps.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'references/analysis/reference_osc_v2');
const file=path.join(root,'research/旧64OSC高频V2.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('旧64OSC高频V2.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  async function ready(){await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert(await page.locator('#player').evaluate(a=>a.muted));assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);assert(await page.locator('#exterior').isEnabled());}
  let loads=0;
  for(const method of ['base','high25','high50']){await page.click(`[data-method=${method}]`);await ready();loads++;}
  await page.locator('details').first().locator('summary').click();
  for(const method of ['pitch90','unity','pitch110']){await page.click(`[data-method=${method}]`);await ready();loads++;assert.equal(await page.locator('#player').evaluate(a=>a.duration),6);}
  await page.click('[data-method=base]');await ready();await page.click('[data-method=base]');assert(await page.locator('#exterior').isEnabled());
  await page.click('#exterior');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('player').currentTime>=2.6);
  await page.click('#transport');const position=await page.locator('#player').evaluate(a=>a.currentTime);
  await page.click('[data-method=high25]');await ready();assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-position)<.04);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused);await page.click('[data-method=high50]');await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);await page.click('#transport');
  await page.locator('details').first().locator('summary').click();await page.click('[data-method=base]');await ready();
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await ready();
  await page.click('[data-method=high50]');await ready();await page.click('#exterior');await page.waitForFunction(()=>!document.getElementById('player').paused);await page.click('#transport');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify({loads,muted:true,http_and_file:true,position_and_playback_preserved:true,exterior_jump:true,active_button_stable:true,six_second_pitch_cases:true,narrow_viewport:true,errors},null,2));
  process.stdout.write('Six clips decoded; exterior jump,active-button,position,playback,file/HTTP,mobile passed.\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
