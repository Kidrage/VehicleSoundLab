const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],reviewBase=process.argv[4],workbenchBase=process.argv[5];
const fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--mute-audio']});
 const errors=[],report={result:'running'};
 try{
  const page=await browser.newPage({viewport:{width:1280,height:980}});
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(reviewBase+'/index.html');
  await page.waitForFunction(()=>document.querySelector('#audio').readyState>=1);
  assert.equal(await page.locator('audio').count(),1);
  assert(await page.locator('#audio').evaluate(a=>a.paused&&!a.autoplay&&a.duration===36));
  assert((await page.textContent('.intro')).includes('已移除被否决的E回火参考'));
  assert(!(await page.textContent('#stages')).includes('undefined'));
  assert.equal(await page.locator('#stages button').count(),7);
  const checked=await page.evaluate(async()=>{
   const context=new AudioContext({sampleRate:48000}),rows=[];
   try{for(const t of VSL_LIFECYCLE.tracks){
    const response=await fetch(t.file);if(!response.ok)throw Error(t.file);
    const bytes=await response.arrayBuffer();
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');
    const decoded=await context.decodeAudioData(bytes.slice(0));
    let afterStartPeak=0;
    if(t.id==='events')for(let c=0;c<decoded.numberOfChannels;c++)for(const v of decoded.getChannelData(c).subarray(4*48000))afterStartPeak=Math.max(afterStartPeak,Math.abs(v));
    rows.push({id:t.id,hash,expected:t.sha256,frames:decoded.length,channels:decoded.numberOfChannels,afterStartPeak});
   }}finally{await context.close();}
   return rows;
  });
  assert.equal(checked.length,6);
  for(const r of checked){assert.equal(r.hash,r.expected);assert.equal(r.frames,36*48000);assert.equal(r.channels,2);}
  assert.equal(checked.find(r=>r.id==='events').afterStartPeak,0);
  await page.locator('#stages button').filter({hasText:'停车怠速'}).click();
  await page.waitForFunction(()=>Math.abs(document.querySelector('#audio').currentTime-30)<.001);
  for(const t of checked){
   await page.selectOption('#track',t.id);
   await page.waitForFunction(file=>document.querySelector('#audio').dataset.source===file&&document.querySelector('#audio').readyState>=1,t.id+'.wav');
   assert(Math.abs(await page.locator('#audio').evaluate(a=>a.currentTime)-30)<.01);
  }
  await page.selectOption('#track','mix');
  await page.waitForFunction(()=>document.querySelector('#audio').dataset.source==='mix.wav'&&document.querySelector('#audio').readyState>=1);
  await page.locator('#audio').evaluate(a=>{a.currentTime=8;a.muted=true;a.volume=.4;return a.play();});
  await page.selectOption('#track','dna');
  await page.waitForFunction(()=>document.querySelector('#audio').dataset.source==='dna.wav'&&!document.querySelector('#audio').paused);
  assert.equal(await page.locator('#audio').evaluate(a=>a.volume),.4);
  await page.locator('#audio').evaluate(a=>a.pause());
  const download=page.waitForEvent('download');
  await page.locator('a[href="controller-preset.json"]').click();
  await(await download).saveAs(path.join(out,'controller-preset.json'));
  const preset=JSON.parse(fs.readFileSync(path.join(out,'controller-preset.json'),'utf8'));
  assert(!preset.event_overrides.afterfire&&preset.event_overrides.crank&&preset.event_overrides.catch);
  await page.screenshot({path:path.join(out,'review-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'review-mobile.png'),fullPage:true});
  report.review={tracks:checked,one_player:true,no_autoplay:true,all_tracks_seek_preserved:true,playing_switch:true,
    download_excludes_rejected_profile:true,no_afterfire_audio_after_startup:true,desktop_mobile:true};
  const wb=await browser.newPage({viewport:{width:1440,height:1000}});
  wb.on('pageerror',e=>errors.push(String(e)));
  const response=await wb.request.post(workbenchBase+'/api/events/new',{data:{package:fixture.document}});
  assert(response.ok());let project=await response.json();
  if(project.job){
   const job=project.job,deadline=Date.now()+30000;
   for(;;){
    assert(Date.now()<deadline,'Event creation job timed out');
    const state=await(await wb.request.get(workbenchBase+'/api/job/'+job)).json();
    if(state.status==='error')throw Error(state.error);
    if(state.status==='done'){project=state.result;break;}
    await wb.waitForTimeout(100);
   }
  }
  assert.equal(project.material_review.decision,'reject_reference');
  await wb.addInitScript(id=>localStorage.setItem('vslEventProject',id),project.id);
  await wb.goto(workbenchBase+'/events.html');
  await wb.waitForFunction(()=>document.querySelector('#analysisInfo').textContent.includes('已排除作为回火参考'));
  assert(await wb.locator('#render').isEnabled());
  await wb.click('#render');
  await wb.waitForFunction(()=>!document.querySelector('#render').disabled&&document.querySelector('#downloads a'));
  const current=await(await wb.request.get(workbenchBase+'/api/events/project/'+project.id)).json();
  const exported=await(await wb.request.get(workbenchBase+current.downloads+'parameters.json')).json();
  assert.equal(exported.material_review.decision,'reject_reference');
  assert(exported.status.includes('historical experiment'));
  const header=await(await wb.request.get(workbenchBase+current.downloads+'profile.h')).text();
  assert(header.includes('Historical experiment: source rejected'));
  await wb.locator('#analysisInfo').scrollIntoViewIfNeeded();
  await wb.screenshot({path:path.join(out,'workbench-desktop.png')});
  await wb.reload();
  await wb.waitForFunction(()=>document.querySelector('#analysisInfo').textContent.includes('已排除作为回火参考'));
  await wb.setViewportSize({width:412,height:915});
  await wb.locator('#analysisInfo').scrollIntoViewIfNeeded();
  await wb.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  await wb.screenshot({path:path.join(out,'workbench-mobile.png')});
  assert(await wb.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  report.workbench={real_API_project:project.id,rejected_reference_visible:true,reload_preserves_review:true,
    historical_preview_and_exports_marked:true,desktop_mobile:true};
  report.result='passed';report.errors=errors;
 }finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack));console.error(e);process.exitCode=1;});
