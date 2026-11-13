// Own-page browser tests only; playback stays muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const url=process.argv[3],out=process.argv[4];
(async()=>{
 fs.mkdirSync(out,{recursive:false});fs.copyFileSync(__filename,path.join(out,'executed_check.cjs'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let count=0;
 try{
  const page=await browser.newPage({viewport:{width:1080,height:1050}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);await page.locator('#player').evaluate(p=>p.muted=true);
  async function ready(mode,bus,seed){
   await page.waitForFunction(({mode,bus,seed})=>{
    const p=document.querySelector('#player'),status=document.querySelector('#status');
    return p.readyState>=1&&p.currentSrc.startsWith('blob:')&&!p.error&&Number.isFinite(p.duration)&&
     status.textContent.includes(document.querySelector('#mode').selectedOptions[0].textContent)&&
     document.querySelector('#mode').value===mode&&document.querySelector('#bus').value===bus&&document.querySelector('#seed').value===seed;
   },{mode,bus,seed},{timeout:15000});
  }
  for(const mode of ['000','050','100']){
   await page.selectOption('#mode',mode);
   for(const bus of ['mix','detail']){
    await page.selectOption('#bus',bus);
    for(const seed of ['149921','277139','381611']){
     await page.selectOption('#seed',seed);await ready(mode,bus,seed);
     assert(Math.abs(await page.locator('#player').evaluate(p=>p.duration)-12)<.001);count++;
    }
   }
  }
  await page.selectOption('#mode','reference');const selected=await page.locator('#seed').inputValue();await ready('reference','mix',selected);
  assert(await page.locator('#seed').isDisabled());assert(await page.locator('#bus').isDisabled());
  assert(Math.abs(await page.locator('#player').evaluate(p=>p.duration)-3)<.001);count++;
  await page.selectOption('#mode','050');await page.selectOption('#bus','mix');await page.selectOption('#seed','149921');await ready('050','mix','149921');
  await page.locator('#player').evaluate(p=>p.currentTime=1.25);
  await page.waitForFunction(()=>Math.abs(document.querySelector('#player').currentTime-1.25)<.03);
  await page.selectOption('#mode','100');await ready('100','mix','149921');
  await page.waitForFunction(()=>Math.abs(document.querySelector('#player').currentTime-1.25)<.03);
  await page.locator('#player').evaluate(async p=>{p.currentTime=0;await p.play();});
  await page.waitForFunction(()=>document.querySelector('#player').currentTime>.06);
  await page.selectOption('#mode','050');await ready('050','mix','149921');
  await page.waitForFunction(()=>!document.querySelector('#player').paused);await page.locator('#player').evaluate(p=>p.pause());
  assert.equal(await page.locator('audio').count(),1);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  const result={result:'pass',url,metadata_combinations:count,one_player:true,muted_playback:true,
   seek_and_switch_preserved:true,playing_switch_preserved:true,reference_controls_disabled:true,mobile_overflow:false,javascript_errors:errors,
   scope:'Own-page muted browser checks; not listening or native-driver UI acceptance.'};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e.stack||e)})+'\n');throw e;}
 finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
