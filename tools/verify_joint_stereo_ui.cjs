// Browser QA of the local research listening tool; browser playback stays muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const assert=require('assert');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'references/analysis/joint_stereo_v1');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try {
  const page=await browser.newPage({viewport:{width:1100,height:1000}});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'research/立体声OSC试听.html')).href);
  await page.locator('audio').evaluate(a=>{a.muted=true;});
  const cases=await page.locator('#case option').evaluateAll(xs=>xs.map(x=>x.value));
  const methods=await page.locator('[data-method]').evaluateAll(xs=>xs.map(x=>x.dataset.method));
  assert.equal(cases.length,6);assert.equal(methods.length,6);
  let checked=0;
  for(const id of cases){
   await page.selectOption('#case',id);
   for(const method of methods){
    await page.click(`[data-method="${method}"]`);
    await page.waitForFunction(({id,method})=>{
     const a=document.getElementById('player');
     return a.readyState>=1&&Number.isFinite(a.duration)&&a.duration>=3&&a.duration<=4.01&&
      a.currentSrc.includes(id+'_'+method+'_rms_matched.wav')&&!a.error;
    },{id,method},{timeout:10000});
    assert.equal(await page.locator('[aria-pressed="true"]').count(),1);
    checked++;
   }
  }
  await page.selectOption('#case','A_revs_check');
  await page.click('[data-method="reference"]');
  await page.waitForFunction(()=>document.getElementById('player').readyState>=1);
  await page.locator('audio').evaluate(a=>{a.currentTime=1.25;});
  await page.click('[data-method="joint64"]');
  await page.waitForFunction(()=>{
   const a=document.getElementById('player');return a.readyState>=1&&a.currentSrc.includes('_joint64_')&&Math.abs(a.currentTime-1.25)<.03;
  });
  await page.locator('audio').evaluate(async a=>{a.currentTime=0;await a.play();});
  await page.waitForFunction(()=>document.getElementById('player').currentTime>.05);
  await page.click('[data-method="joint64_low28"]');
  await page.waitForFunction(()=>{
   const a=document.getElementById('player');return a.readyState>=2&&a.currentSrc.includes('_joint64_low28_')&&!a.paused;
  });
  await page.locator('audio').evaluate(a=>{a.pause();a.currentTime=0;});
  await page.click('[data-method="reference"]');
  await page.waitForFunction(()=>document.getElementById('player').readyState>=1);
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  const result={result:'pass',cases:cases.length,methods:methods.length,metadata_loads:checked,
   position_preserved:true,muted_playback_switch_preserved:true,mobile_horizontal_overflow:false,
   javascript_errors:errors,scope:'Headless Chrome local-file metadata, muted playback and interaction; no subjective audio or speaker verification.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(result,null,2));
  process.stdout.write(JSON.stringify(result,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
