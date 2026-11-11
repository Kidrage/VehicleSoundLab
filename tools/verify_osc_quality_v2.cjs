// Muted, local-page QA. Does not claim a subjective audio result.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'references/analysis/osc_quality_v2');
const file=path.join(root,'research/OSC完整度对照V2.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('OSC完整度对照V2.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  async function ready(){await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert(await page.locator('#player').evaluate(a=>a.muted));assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);assert(await page.locator('#exterior').isEnabled());}
  let loads=0;
  for(const method of ['reference','legacy','rank64']){await page.click(`[data-method=${method}]`);await ready();loads++;assert.equal(await page.locator('#player').evaluate(a=>a.duration),6);}
  await page.locator('summary').click();
  for(const method of ['complete','rank16']){await page.click(`[data-method=${method}]`);await ready();loads++;}
  await page.click('[data-method=legacy]');await ready();await page.click('[data-method=legacy]');assert(await page.locator('#exterior').isEnabled());
  await page.click('#exterior');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('player').currentTime>=2.6);
  await page.click('#transport');const position=await page.locator('#player').evaluate(a=>a.currentTime);
  await page.click('[data-method=rank64]');await ready();assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-position)<.04);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.click('[data-method=complete]');await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);await page.click('#transport');
  await page.click('[data-method=rank64]');await ready();
  await page.locator('summary').click();await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await ready();
  await page.click('[data-method=rank64]');await ready();
  assert.deepEqual(errors,[]);
  const result={loads,muted:true,http_and_file:true,position_and_playback_preserved:true,exterior_jump:true,active_button_stable:true,narrow_viewport:true,errors};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
