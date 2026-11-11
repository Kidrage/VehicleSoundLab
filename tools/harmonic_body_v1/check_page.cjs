// Muted browser checks of the local authored comparison, no external media.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),assert=require('assert');
(async()=>{
 const root=path.resolve(process.argv[3]),browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);
  await page.locator('audio').evaluateAll(items=>items.forEach(a=>a.muted=true));
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.readyState>=1&&!a.error));
  const durations=await page.locator('audio').evaluateAll(items=>items.map(a=>a.duration));
  assert.equal(durations.length,3);assert(durations.every(d=>d===16));
  await page.locator('#zero').evaluate(a=>a.play());await page.locator('#layered').evaluate(a=>a.play());
  await page.waitForFunction(()=>document.querySelector('#zero').paused&&!document.querySelector('#layered').paused);
  await page.locator('#layered').evaluate(a=>a.pause());
  await page.click('#seek');
  assert(await page.locator('audio').evaluateAll(items=>items.every(a=>a.currentTime>0)));
  await page.screenshot({path:path.join(root,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(root,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  const report={result:'pass',muted:true,durations,one_player_at_a_time:true,seek:true,narrow_viewport:true,errors};
  fs.writeFileSync(path.join(root,'browser_qa.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
