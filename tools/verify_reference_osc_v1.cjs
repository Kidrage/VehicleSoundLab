// Muted functional QA of this project's comparison player.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'references/analysis/reference_osc_v1');
const file=path.join(root,'research/素材OSC回查V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('素材OSC回查V1.html'));
  await page.locator('#player').evaluate(a=>a.muted=true);
  async function ready(){
   await page.waitForFunction(()=>{const a=document.getElementById('player');return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});
   assert(await page.locator('#player').evaluate(a=>a.muted));
   assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);
  }
  let loads=0;
  for(const scene of ['archive','moving','blips','low']){
   await page.selectOption('#scene',scene);
   for(const method of await page.locator('[data-method]').evaluateAll(bs=>bs.map(b=>b.dataset.method))){await page.click(`[data-method=${method}]`);await ready();loads++;}
  }
  await page.selectOption('#scene','moving');await ready();
  await page.locator('#player').evaluate(a=>a.currentTime=.8);await page.click('[data-method=high35]');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-.8)<.03);
  await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused&&document.getElementById('player').currentTime>.85);
  await page.click('[data-method=base]');await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.selectOption('#scene','archive');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.01));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>a.muted=true);await ready();
  await page.click('[data-method=c]');await ready();await page.click('#transport');await page.waitForFunction(()=>!document.getElementById('player').paused);await page.click('#transport');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify({loads,muted:true,http_and_file:true,position_and_playback_preserved:true,scene_reset:true,narrow_viewport:true,errors},null,2));
  process.stdout.write('13 clips decoded; transport,position,file/HTTP,mobile passed.\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
