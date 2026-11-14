// Check only this project's review page; all playback is muted.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const root=process.argv[3],out=process.argv[4];
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const report=JSON.parse(fs.readFileSync(path.join(root,'report.json'),'utf8')),data=JSON.parse(fs.readFileSync(path.join(root,'data.json'),'utf8'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1024,height:900}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(report.url);await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('#case option').count(),5);
  assert(await page.locator('audio').evaluate(p=>p.paused&&!p.autoplay&&!p.loop));
  await page.locator('audio').evaluate(p=>p.muted=true);
  for(const item of data.cases){
   await page.selectOption('#case',item.key);
   for(const mode of ['native','common']){
    await page.locator('#common').setChecked(mode==='common');
    const available=data.clips.filter(v=>v.case_key===item.key&&v.mode===mode);
    assert.equal(await page.locator('#clip option').count(),available.length);
    for(const clip of available){
     await page.selectOption('#clip',clip.key);
     await page.waitForFunction(key=>document.querySelector('audio').dataset.clipKey===key&&document.querySelector('audio').readyState>=1,clip.key);
     assert(await page.locator('audio').evaluate((p,d)=>p.paused&&!p.error&&Math.abs(p.duration-d)<.001,clip.frames/48000));
     await page.locator('audio').evaluate(async p=>{p.currentTime=.05;await p.play()});
     await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').currentTime>=.05);
    }
   }
  }
  // Changing only the case preserves the chosen generated sequence, then pauses.
  await page.selectOption('#case','case1');
  await page.waitForFunction(()=>document.querySelector('audio').dataset.clipKey==='case1_common_seed61927'&&document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(p=>p.paused));
  // Rapid changes cannot let a stale fetch replace the latest choice.
  await page.evaluate(()=>{const c=document.querySelector('#case'),m=document.querySelector('#common');c.value='case3';c.dispatchEvent(new Event('change'));m.checked=false;m.dispatchEvent(new Event('change'));c.value='case5';c.dispatchEvent(new Event('change'))});
  await page.waitForFunction(()=>document.querySelector('audio').dataset.clipKey==='case5_native_seed61927'&&document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(p=>p.paused));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.locator('details').evaluate(p=>p.open=true);
  await page.waitForFunction(()=>document.querySelector('img').complete&&document.querySelector('img').naturalWidth>0);
  await page.screenshot({path:path.join(out,'desktop_details.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',cases:5,clips:45,single_player:true,paused_switch:true,stale_fetch_prevented:true,muted:true,hearing:false,duration_and_seek:true,mobile_overflow:false,errors},null,2)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)},null,2)+'\n');throw e}
 finally{await browser.close()}
})();
