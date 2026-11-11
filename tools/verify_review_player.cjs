// Reusable local comparison-player QA. All automated playback stays muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),pageFile=path.resolve(root,process.argv[3]),out=path.resolve(root,process.argv[4]);
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(pageFile).href);
  await page.locator('#player').evaluate(a=>{a.muted=true;});
  const cases=await page.locator('#case option').evaluateAll(xs=>xs.map(x=>x.value));
  const methods=await page.locator('[data-method]').evaluateAll(xs=>xs.map(x=>x.dataset.method));
  let checked=0;
  async function ready(id,method){
   await page.waitForFunction(({id,method})=>{
    const a=document.getElementById('player'),expected=new URL(data[id].takes[method],location.href).href;
    return a.readyState>=1&&a.currentSrc===expected&&Number.isFinite(a.duration)&&a.duration>=1&&!a.error;
   },{id,method},{timeout:10000});
  }
  for(const id of cases){
   await page.selectOption('#case',id);
   for(const method of methods){
    if(await page.locator(`[data-method="${method}"]`).isDisabled()){
     assert.equal(await page.evaluate(({id,method})=>Boolean(data[id].takes[method]),{id,method}),false);continue;
    }
    await page.click(`[data-method="${method}"]`);await ready(id,method);
    assert.equal(await page.locator('[aria-pressed="true"]').count(),1);checked++;
   }
  }
  const id=cases[0];await page.selectOption('#case',id);
  await page.click(`[data-method="${methods[0]}"]`);await ready(id,methods[0]);
  await page.locator('#player').evaluate(a=>{a.currentTime=1.25;});
  await page.click(`[data-method="${methods[1]}"]`);await ready(id,methods[1]);
  await page.waitForFunction(()=>Math.abs(document.getElementById('player').currentTime-1.25)<.03);
  await page.locator('#player').evaluate(async a=>{a.currentTime=0;await a.play();});
  await page.waitForFunction(()=>document.getElementById('player').currentTime>.05);
  await page.click(`[data-method="${methods[0]}"]`);await ready(id,methods[0]);
  await page.waitForFunction(()=>!document.getElementById('player').paused);
  await page.locator('#player').evaluate(a=>{a.pause();a.currentTime=0;});
  await page.click(`[data-method="${methods[1]}"]`);await ready(id,methods[1]);
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  const references=await page.locator('audio[data-reference]').count();
  for(let i=0;i<references;i++){
   const ref=page.locator('audio[data-reference]').nth(i);await ref.evaluate(a=>{a.muted=true;a.load();});
   await page.waitForFunction(i=>{const a=document.querySelectorAll('audio[data-reference]')[i];return a.readyState>=1&&Number.isFinite(a.duration)&&!a.error;},i);
   await page.locator('#player').evaluate(async a=>{a.currentTime=0;await a.play();});
   await ref.evaluate(async a=>{a.currentTime=0;await a.play();});
   await page.waitForFunction(()=>document.getElementById('player').paused);
   assert.equal(await ref.evaluate(a=>a.paused),false);
   await page.locator('#player').evaluate(async a=>{await a.play();});
   await page.waitForFunction(i=>document.querySelectorAll('audio[data-reference]')[i].paused,i);
   await page.locator('#player').evaluate(a=>a.pause());
  }
  const report={result:'pass',page:path.relative(root,pageFile),cases:cases.length,methods:methods.length,reference_metadata_loads:references,
   metadata_loads:checked,position_preserved:true,muted_playback_switch_preserved:true,
   reference_playback_mutual_exclusion:references?true:null,
   mobile_horizontal_overflow:false,javascript_errors:errors,
   scope:'Real headless browser local metadata, muted playback and controls. No subjective listening or physical array validation.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));
  process.stdout.write(JSON.stringify(report,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
