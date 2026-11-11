// Local evidence viewer QA; video playback always muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),out=path.join(root,'references/analysis/state_context_v1');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const response=await page.goto(encodeURI('http://127.0.0.1:8789/research/状态证据审阅V1.html'));
  assert.equal(response.status(),200);
  await page.locator('#video').evaluate(v=>{v.muted=true});
  await page.waitForFunction(()=>document.getElementById('video').readyState>=1);
  const contexts=await page.locator('#context option').evaluateAll(xs=>xs.map(x=>x.value));
  let imageLoads=0;
  for(const id of contexts){
   await page.selectOption('#context',id);
   try{await page.waitForFunction(id=>{const c=data.contexts.find(c=>c.id===id),v=document.getElementById('video');return v.paused&&!v.seeking&&Math.abs(v.currentTime-c.seconds[0])<.04},id,{timeout:10000})}
   catch(e){process.stderr.write(JSON.stringify(await page.locator('#video').evaluate(v=>({context:document.getElementById('context').value,time:v.currentTime,paused:v.paused,seeking:v.seeking,ready:v.readyState,network:v.networkState,duration:v.duration,error:v.error&&v.error.message,seekable:[...Array(v.seekable.length)].map((_,i)=>[v.seekable.start(i),v.seekable.end(i)])})))+'\n');throw e}
   await page.waitForFunction(()=>[...document.querySelectorAll('#frames img')].every(i=>i.complete&&i.naturalWidth>0));
   imageLoads+=await page.locator('#frames img').count();
  }
  await page.selectOption('#context','rev');await page.click('#play');
  await page.waitForFunction(()=>{const v=document.getElementById('video');return !v.paused&&v.currentTime>238.05});
  await page.selectOption('#context','moving');
  await page.waitForFunction(()=>{const v=document.getElementById('video');return v.paused&&!v.seeking&&Math.abs(v.currentTime-316)<.04});
  await page.locator('#video').evaluate(v=>{v.currentTime=319.4});
  await page.waitForFunction(()=>!document.getElementById('video').seeking);
  await page.click('#play');
  await page.waitForFunction(()=>{const v=document.getElementById('video');return v.paused&&v.currentTime>=319.5&&v.currentTime<319.9});
  for(let i=0;i<8;++i){
   await page.selectOption('#state',String(i));
   assert.equal(await page.locator('#stateTable tr.active').count(),1);
   assert.equal(await page.locator('#stateTable tr.active').getAttribute('data-state'),String(i));
   const actual=await page.locator('#stateTable tr.active td').allTextContents();
   const expected=await page.evaluate(i=>data.native.operating[i].level.map(x=>x.toFixed(2)),i);
   assert.deepEqual(actual.slice(1),expected);
  }
  await page.selectOption('#context','rev');await page.selectOption('#state','1');
  await page.screenshot({path:path.join(out,'review_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'review_mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  const result={result:'pass',contexts:contexts.length,image_metadata_loads:imageLoads,
   all_eight_C_coefficient_rows_match:true,actual_muted_video_playback:true,context_switch_pauses_and_seeks:true,
   segment_end_stops_playback:true,mobile_horizontal_overflow:false,javascript_errors:errors,
   scope:'Browser operation and evidence display only; no subjective or A/V alignment judgement.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(result,null,2));
  process.stdout.write(JSON.stringify(result,null,2));
 }finally{await browser.close()}
})().catch(error=>{process.stderr.write(String(error.stack));process.exit(1)});
