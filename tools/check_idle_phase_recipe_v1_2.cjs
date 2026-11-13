// Only this project's generated page; audio remains muted throughout UI verification.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.argv[2]+'/playwright');
const url=process.argv[3],out=process.argv[4];
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let combinations=0;
 try{
  const page=await browser.newPage({viewport:{width:1050,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);await page.locator('#player').evaluate(p=>p.muted=true);await page.locator('summary').click();
  async function ready(seconds){await page.waitForFunction(seconds=>{const p=document.querySelector('#player'),s=document.querySelector('#status');return p.readyState>=1&&!p.error&&p.currentSrc.startsWith('blob:')&&Math.abs(p.duration-seconds)<.001&&!s.textContent.includes('准备')&&!s.textContent.includes('失败');},seconds,{timeout:20000});}
  for(const method of ['static','post','relation_q','relation_full']){
   await page.selectOption('#mode',method==='relation_q'?'relation_full':method);
   if(method.startsWith('relation'))await page.locator('#diagnostic').setChecked(method==='relation_q');
   for(const bus of ['mix','detail']){
    await page.selectOption('#bus',bus);
    for(const seed of ['149921','277139','381611']){await page.selectOption('#seed',seed);await ready(24);combinations++;}
   }
  }
  for(const method of ['static','post','relation_q','relation_full']){
   await page.selectOption('#mode',method==='relation_q'?'relation_full':method);
   if(method.startsWith('relation'))await page.locator('#diagnostic').setChecked(method==='relation_q');
   await page.selectOption('#length','long');await ready(180);
   assert(await page.locator('#seed').isDisabled());assert(await page.locator('#bus').isDisabled());combinations++;
  }
  for(const part of ['training','check']){
   await page.selectOption('#mode','reference_'+part);await ready(3);
   assert(await page.locator('#length').isDisabled());assert(await page.locator('#seed').isDisabled());combinations++;
  }
  await page.selectOption('#mode','static');await page.selectOption('#length','short');await page.selectOption('#bus','mix');await ready(24);
  await page.locator('#player').evaluate(p=>p.currentTime=1.25);
  await page.selectOption('#mode','post');await ready(24);
  assert(Math.abs(await page.locator('#player').evaluate(p=>p.currentTime)-1.25)<.03);
  await page.locator('#player').evaluate(async p=>{p.currentTime=0;await p.play();});
  await page.waitForFunction(()=>document.querySelector('#player').currentTime>.06);
  await page.selectOption('#mode','relation_full');await page.locator('#diagnostic').setChecked(false);await ready(24);
  await page.waitForFunction(()=>!document.querySelector('#player').paused);
  await page.locator('#player').evaluate(p=>p.pause());assert.equal(await page.locator('audio').count(),1);
  await page.locator('summary').click();await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  const result={result:'passed',url,metadata_combinations:combinations,one_player:true,muted_playback:true,seek_preserved:true,playing_switch_preserved:true,javascript_errors:errors,mobile_overflow:false,scope:'Generated page only; not human listening, native C or device acceptance.'};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)})+'\n');throw e;}
 finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
