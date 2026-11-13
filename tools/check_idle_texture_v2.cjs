// Headless checks for our own comparison page. Audio remains muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const url=process.argv[3],out=process.argv[4];
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let count=0;
 try{
  const page=await browser.newPage({viewport:{width:1080,height:1000}});
  page.on('pageerror',e=>errors.push(String(e)));await page.goto(url);
  await page.locator('#player').evaluate(p=>p.muted=true);
  async function ready(mode,band,seed){
   await page.waitForFunction(({mode,band,seed})=>{
    const p=document.querySelector('#player'),status=document.querySelector('#status');
    return p.readyState>=1&&p.currentSrc.startsWith('blob:')&&!p.error&&Number.isFinite(p.duration)&&
     status.textContent.includes(document.querySelector('#mode').selectedOptions[0].textContent)&&
     document.querySelector('#mode').value===mode&&document.querySelector('#band').value===band&&
     document.querySelector('#seed').value===seed;
   },{mode,band,seed},{timeout:15000});
  }
  for(const mode of ['original','fine','dynamic','reference']){
   await page.selectOption('#mode',mode);
   for(const band of ['whole','mid','high']){
    await page.selectOption('#band',band);
    for(const seed of mode==='reference'?['149921']:['149921','277139','381611']){
     if(mode!=='reference')await page.selectOption('#seed',seed);
     // Reference disables seed and retains whichever value was last selected.
     const selected=await page.locator('#seed').inputValue();await ready(mode,band,selected);
     const duration=await page.locator('#player').evaluate(p=>p.duration);
     assert(Math.abs(duration-(mode==='reference'?3:12))<.001);count++;
    }
   }
  }
  await page.selectOption('#mode','fine');await page.selectOption('#band','whole');
  await page.selectOption('#seed','149921');await ready('fine','whole','149921');
  await page.locator('#player').evaluate(p=>p.currentTime=1.25);
  await page.waitForFunction(()=>Math.abs(document.querySelector('#player').currentTime-1.25)<.03);
  await page.selectOption('#mode','dynamic');await ready('dynamic','whole','149921');
  await page.waitForFunction(()=>Math.abs(document.querySelector('#player').currentTime-1.25)<.03);
  await page.locator('#player').evaluate(async p=>{p.currentTime=0;await p.play();});
  await page.waitForFunction(()=>document.querySelector('#player').currentTime>.06);
  await page.selectOption('#mode','original');await ready('original','whole','149921');
  await page.waitForFunction(()=>!document.querySelector('#player').paused);
  await page.locator('#player').evaluate(p=>p.pause());
  assert.equal(await page.locator('audio').count(),1);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  const result={result:'pass',url,metadata_combinations:count,one_player:true,muted_playback:true,
   seek_and_switch_preserved:true,playing_switch_preserved:true,mobile_overflow:false,javascript_errors:errors,
   scope:'Own-page headless playback/control/layout tests, not subjective listening or native UI verification.'};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)})+'\n');throw e;}
 finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
