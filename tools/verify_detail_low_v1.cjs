//Muted browser QA: loading/position preservation and layout, not timbre acceptance.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'references/analysis/detail_modulation_v1');
const file=path.join(root,'research/持续OSC细节与低频V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('持续OSC细节与低频V1.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  async function ready(){await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});assert(await page.locator('#player').evaluate(a=>a.muted));assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);assert.equal(await page.locator('#player').evaluate(a=>a.duration),8);}
  for(const method of ['detail075','detail100','phasefixed','bass000','bass050','bass100']){await page.click(`[data-method=${method}]`);await ready();}
  await page.locator('summary').click();await page.click('[data-method=solo]');await ready();
  await page.click('[data-method=detail100]');await ready();await page.locator('#player').evaluate(a=>a.currentTime=3.2);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.click('[data-method=phasefixed]');await ready();assert(await page.locator('#player').evaluate(a=>!a.paused&&a.currentTime>=3.2));
  await page.check('#repeat');assert(await page.locator('#player').evaluate(a=>a.loop));await page.click('[data-method=bass100]');await ready();assert(await page.locator('#player').evaluate(a=>a.loop&&!a.paused));
  await page.click('#transport');await page.uncheck('#repeat');await page.locator('summary').click();await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await ready();assert.deepEqual(errors,[]);
  const result={loads:7,muted:true,http_and_file:true,position_and_playback_preserved:true,repeat_control:true,narrow_viewport:true,errors};fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
