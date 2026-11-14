const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const root=process.argv[3],out=process.argv[4];
(async()=>{fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const report=JSON.parse(fs.readFileSync(path.join(root,'report.json'),'utf8')),data=JSON.parse(fs.readFileSync(path.join(root,'data.json'),'utf8'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{const page=await browser.newPage({viewport:{width:1024,height:900}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(report.url);await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('#bank option').count(),2);
  assert(await page.locator('audio').evaluate(p=>p.paused&&!p.loop&&!p.autoplay));
  await page.locator('audio').evaluate(p=>p.muted=true);
  for(const bank of data.banks){await page.selectOption('#bank',bank.key);for(const clip of data.clips.filter(v=>v.bank_key===bank.key)){
   await page.selectOption('#clip',clip.key);
   await page.waitForFunction(key=>document.querySelector('audio').dataset.clipKey===key&&document.querySelector('audio').readyState>=1,clip.key);
   assert(await page.locator('audio').evaluate(p=>p.paused&&!p.error&&Math.abs(p.duration-12)<.001));
   await page.locator('audio').evaluate(async p=>{p.currentTime=6;await p.play()});
   await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').currentTime>=6);
  }}
  await page.evaluate(()=>{const b=document.querySelector('#bank');b.value='bank1';b.dispatchEvent(new Event('change'));b.value='bank2';b.dispatchEvent(new Event('change'))});
  await page.waitForFunction(()=>document.querySelector('audio').dataset.clipKey==='bank2_mid_61927'&&document.querySelector('audio').readyState>=1);
  assert(await page.locator('audio').evaluate(p=>p.paused));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.locator('details').evaluate(p=>p.open=true);
  await page.waitForFunction(()=>document.querySelector('img').complete&&document.querySelector('img').naturalWidth>0);
  const response=await page.request.get(new URL(await page.locator('details a').getAttribute('href'),page.url()).href);assert(response.ok());
  await page.screenshot({path:path.join(out,'desktop_details.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',banks:2,clips:12,muted:true,hearing:false,single_player:true,duration_and_seek:true,paused_switch:true,stale_fetch_prevented:true,reference_link:true,mobile_overflow:false,errors},null,2)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)},null,2)+'\n');throw e}
 finally{await browser.close()}
})();
