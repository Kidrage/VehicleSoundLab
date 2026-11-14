// Muted checks of this project's local one-player candidate review only.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const url=process.argv[3],out=process.argv[4];
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running',metadata_checks:0,muted:true};
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);await page.locator('audio').evaluate(a=>a.muted=true);
  const data=await page.locator('#data').evaluate(e=>JSON.parse(e.textContent));
  async function ready(key){await page.waitForFunction(key=>{const a=document.querySelector('audio');return a.dataset.clipKey===key&&a.readyState>=1&&!a.error&&Number.isFinite(a.duration)},key,{timeout:15000});}
  for(const bank of data.banks){
   await page.selectOption('#bank',bank.key);
   for(const clip of data.clips.filter(c=>c.bank_key===bank.key)){
    await page.selectOption('#clip',clip.key);await ready(clip.key);
    const state=await page.locator('audio').evaluate(a=>({duration:a.duration,paused:a.paused,loop:a.loop}));
    assert(Math.abs(state.duration-clip.seconds)<.001);assert(state.paused);assert(!state.loop);report.metadata_checks++;
   }
  }
  await page.selectOption('#bank',data.banks[0].key);
  const first=data.clips.find(c=>c.bank_key===data.banks[0].key&&c.variant==='original');
  await page.selectOption('#clip',first.key);await ready(first.key);
  await page.locator('audio').evaluate(async a=>{a.currentTime=1.25;await a.play()});
  await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').currentTime>1.25);
  const next=data.clips.find(c=>c.bank_key===data.banks[0].key&&c.variant==='fixed_phase');
  await page.selectOption('#clip',next.key);await ready(next.key);
  assert(await page.locator('audio').evaluate(a=>a.paused));
  await page.locator('#clip').evaluate(e=>{for(const o of [...e.options].slice(0,6)){e.value=o.value;e.dispatchEvent(new Event('change',{bubbles:true}))}});
  const key=await page.locator('#clip').inputValue();await ready(key);
  assert.equal(await page.locator('audio').count(),1);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  Object.assign(report,{result:'pass',one_player:true,all_selections_pause:true,rapid_selection_latest_wins:true,seek_and_muted_play_verified:true,
   mobile_overflow:false,javascript_errors:errors,source_reference_not_looped:true,hearing:false});
 }catch(e){Object.assign(report,{result:'failed',error:String(e.stack||e)});throw e}
 finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');await browser.close();console.log(JSON.stringify(report));}
})().catch(e=>{console.error(e);process.exitCode=1;});
