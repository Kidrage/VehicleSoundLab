// Own generated page only. All browser playback is muted.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const review=process.argv[3],out=process.argv[4];
const report=JSON.parse(fs.readFileSync(path.join(review,'report.json'),'utf8'));
const data=JSON.parse(fs.readFileSync(path.join(review,'data.json'),'utf8'));
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let combinations=0;
 try{
  const page=await browser.newPage({viewport:{width:1000,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(report.url);await page.waitForFunction(()=>document.querySelector('#audio').readyState>=1);
  await page.locator('#audio').evaluate(p=>p.muted=true);
  assert(await page.locator('#audio').evaluate(p=>p.paused));
  async function change(selector,value){
   await page.locator('#audio').evaluate(p=>{window.__nextMetadata=false;p.addEventListener('loadedmetadata',()=>window.__nextMetadata=true,{once:true});});
   await page.selectOption(selector,value);await page.waitForFunction(()=>window.__nextMetadata&&document.querySelector('#audio').readyState>=1);
  }
  for(const scene of data.scenes){
   await change('#scene',scene.key);
   for(const row of scene.variants){
    await change('#variant',row.key);
    assert(await page.locator('#audio').evaluate((p,d)=>!p.error&&Math.abs(p.duration-d)<.001,row.frames/48000));
    const text=await page.locator('#state').textContent();assert(!text.includes('undefined'));
    if(row.trace){
     const trace=data.traces[row.trace];
     const at=Math.min(600,trace.length-1);await page.locator('#audio').evaluate((p,t)=>{p.currentTime=t;p.dispatchEvent(new Event('timeupdate'));},at/200);
     const actual=await page.locator('#state').textContent(),expected=trace[at];
     assert(actual.includes(Math.round(expected.rpm)+' RPM'));
     assert(actual.includes('细节支持 '+Math.round(100*expected.detail_support)+'%'));
    }else assert(text.includes(scene.info));
    combinations++;
   }
  }
  assert.equal(combinations,report.clip_count);assert.equal(await page.locator('audio').count(),1);
  await change('#scene','shifts');await change('#variant','five_detail');
  await page.locator('#audio').evaluate(async p=>{p.currentTime=6;await p.play()});
  await page.waitForFunction(()=>!document.querySelector('#audio').paused);
  await change('#variant','four_detail');
  assert(await page.locator('#audio').evaluate(p=>p.muted&&!p.paused&&p.currentTime>=6&&p.currentTime<7));
  await page.locator('#audio').evaluate(p=>p.pause());
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('details').evaluate(e=>e.open=true);
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',combinations,all_actual_variant_traces_checked:true,
   single_player:true,defaults_stopped:true,muted_playback_switch_seek:true,mobile_overflow:false,javascript_errors:errors,
   scope:'Own headless browser page; no hearing/native device/physical speaker validation'},null,2)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)},null,2)+'\n');throw e;}
 finally{await browser.close();}
})();
