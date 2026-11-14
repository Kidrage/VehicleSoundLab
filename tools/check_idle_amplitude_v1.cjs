// Check only the finite comparison page; all test audio stays muted.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.argv[2]+'/playwright');
const url=process.argv[3],out=process.argv[4];
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let combinations=0;const errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1000,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);assert(await page.locator('#player').evaluate(p=>p.paused));await page.locator('#player').evaluate(p=>p.muted=true);
  async function ready(seconds){await page.waitForFunction(seconds=>{const p=document.querySelector('#player'),s=document.querySelector('#status');return p.readyState>=1&&!p.error&&p.currentSrc.startsWith('blob:')&&Math.abs(p.duration-seconds)<.001&&!s.textContent.includes('准备')&&!s.textContent.includes('失败');},seconds,{timeout:20000});}
  for(const mode of ['0.0','0.5','1.0']){
   await page.selectOption('#mode',mode);
   for(const bus of ['mix','main']){
    await page.selectOption('#bus',bus);
    for(const seed of ['149921','277139','381611']){await page.selectOption('#seed',seed);await ready(24);combinations++;}
   }
  }
  for(const part of ['train','check']){
   await page.selectOption('#mode','reference_'+part);await ready(3);combinations++;
   assert(await page.locator('#bus').isDisabled());assert(await page.locator('#seed').isDisabled());
  }
  await page.selectOption('#mode','0.0');await ready(24);
  await page.locator('#player').evaluate(p=>{p.currentTime=5;p.muted=true;return p.play();});
  await page.selectOption('#mode','0.5');await ready(24);
  await page.waitForFunction(()=>!document.querySelector('#player').paused);
  const at=await page.locator('#player').evaluate(p=>p.currentTime);assert(at>=5&&at<7);
  await page.locator('#player').evaluate(p=>p.pause());
  await page.selectOption('#mode','1.0');await ready(24);
  const still=await page.locator('#player').evaluate(p=>({at:p.currentTime,paused:p.paused,muted:p.muted}));
  assert(still.paused&&still.muted&&Math.abs(still.at-at)<.1);
  assert.strictEqual(await page.locator('audio').count(),1);assert.strictEqual(combinations,20);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);assert(!overflow);assert.deepStrictEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',url,metadata_combinations:combinations,
   one_player:true,defaults_stopped:true,muted_playback:true,playing_switch_preserved:true,paused_seek_preserved:true,mobile_overflow:overflow,
   javascript_errors:errors,scope:'Generated page only; not human listening, native C or device acceptance.'},null,2));
  process.stdout.write('20 combinations, muted playback/switch/seek/mobile passed.\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',combinations,error:String(e),javascript_errors:errors},null,2));throw e;}
 finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e)+'\n');process.exitCode=1;});
