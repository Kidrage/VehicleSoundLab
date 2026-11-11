// Muted browser QA of the local C-rendered audition page.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const workspace=path.resolve(process.argv[3]);
 const out=path.join(workspace,'references/analysis/dna_scene_v1');
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(String(error)));
  const response=await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('DNA空间接入V1.html'));
  assert(response.ok());
  await page.locator('audio').evaluateAll(items=>items.forEach(a=>a.muted=true));
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.readyState>=1&&Number.isFinite(a.duration)&&!a.error));
  const durations=await page.locator('audio').evaluateAll(items=>items.map(a=>a.duration));
  assert.equal(durations.length,8);assert(durations.every(d=>d===8));
  await page.locator('#reference').evaluate(a=>a.play());
  await page.locator('#room').evaluate(a=>a.play());
  await page.waitForFunction(()=>document.querySelector('#reference').paused&&!document.querySelector('#room').paused);
  await page.locator('#room').evaluate(a=>a.pause());
  await page.screenshot({path:path.join(out,'review_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'review_mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  const report={status:'pass',muted:true,loaded_players:durations.length,durations,one_player_at_a_time:true,narrow_viewport:true,errors};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
