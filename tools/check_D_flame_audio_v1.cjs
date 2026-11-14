// Muted checks of this generated project page only.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const root=process.argv[3],out=process.argv[4];
(async()=>{fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const info=JSON.parse(fs.readFileSync(path.join(root,'report.json'),'utf8'));
 const data=JSON.parse(fs.readFileSync(path.join(root,'data.json'),'utf8'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{const page=await browser.newPage({viewport:{width:1000,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(info.url);await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(p=>p.paused));assert.equal(await page.locator('audio').count(),1);
  await page.locator('audio').evaluate(p=>p.muted=true);
  for(const row of data.clips){
   await page.selectOption('#clip',row.key);await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
   assert(await page.locator('audio').evaluate((p,d)=>p.paused&&!p.error&&Math.abs(p.duration-d)<.001,row.frames/48000));
   await page.locator('audio').evaluate(async p=>{p.currentTime=.5;await p.play()});
   await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').currentTime>=.5);
   await page.locator('audio').evaluate(p=>{p.pause();p.dispatchEvent(new Event('timeupdate'))});
   assert((await page.locator('#clock').textContent()).includes('当前片段 '+row.source_seconds.join('–')));
   const seconds=row.source_seconds[0]+await page.locator('audio').evaluate(p=>p.currentTime);
   const nearest=data.frames.reduce((a,b)=>Math.abs(a.source_seconds-seconds)<Math.abs(b.source_seconds-seconds)?a:b);
   await page.waitForFunction(()=>{const im=document.querySelector('#picture');return im.complete&&im.naturalWidth>0});
   assert((await page.locator('#picture').getAttribute('src')).endsWith(nearest.file));
   assert((await page.locator('#clock').textContent()).includes(seconds.toFixed(3)+' s'));
   assert((await page.locator('#caption').textContent()).includes(nearest.source_seconds.toFixed(3)+' s'));
  }
  await page.selectOption('#clip','primary');await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('details').evaluate(e=>e.open=true);
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',clips:4,muted:true,one_player:true,paused_switch:true,
    source_clock_and_picture_checked:true,mobile_overflow:false,hearing:false,errors},null,2)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)},null,2)+'\n');throw e;}
 finally{await browser.close()}
})();
