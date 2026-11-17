const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=process.argv[4],base=process.argv[5];
function wavSamples(bytes){
 assert.equal(bytes.toString('ascii',0,4),'RIFF');assert.equal(bytes.toString('ascii',8,12),'WAVE');
 let data=null,format=null;
 for(let offset=12;offset+8<=bytes.length;){
  const name=bytes.toString('ascii',offset,offset+4),length=bytes.readUInt32LE(offset+4);
  assert(offset+8+length<=bytes.length);
  if(name==='fmt ')format=bytes.subarray(offset+8,offset+8+length);
  if(name==='data')data=bytes.subarray(offset+8,offset+8+length);
  offset+=8+length+(length%2);
 }
 assert(format&&data);assert.equal(format.readUInt16LE(0),3);assert.equal(format.readUInt16LE(2),1);
 assert.equal(format.readUInt32LE(4),48000);assert.equal(format.readUInt16LE(14),32);
 return data;
}
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--mute-audio']});
 let page;const report={result:'running'},errors=[];
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  const current=async()=>{const id=await page.inputValue('#projects');return(await page.request.get(base+'/api/events/project/'+id)).json();};
  const idle=async()=>page.waitForFunction(()=>!document.querySelector('#analyze').disabled);
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert(await page.locator('#scanDetector').isDisabled());assert.equal(await page.locator('audio').count(),1);
  await page.locator('#audioFile').setInputFiles(fixture);
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled);
  await page.locator('#candidatePanel').evaluate(e=>e.open=true);
  assert.equal(await page.inputValue('#scanDetector'),'high');
  await page.selectOption('#scanDetector','short_high');await page.click('#scanCandidates');
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled&&document.querySelector('#candidateRows [data-candidate-index]'));
  let p=await current();assert.equal(p.candidate_scan.detector.family,'short_high');
  const index=p.candidate_scan.candidates.findIndex(v=>v.both_full_band_above_3db&&Math.abs(v.source_seconds-1.4)<.02);assert(index>=0);
  await page.click('[data-candidate-index="'+index+'"]');
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled&&document.querySelector('audio').src.startsWith('blob:'));
  p=await current();assert(p.context_matches_selection&&!p.document);
  assert(Math.abs(Number(await page.inputValue('#end'))-Number(await page.inputValue('#start'))-.016)<1e-12);
  const selectedRevision=p.history[0].id,selectedHistory=p.history.length,scanRun=p.scan_run;
  await page.check('#fitGated');await page.click('#analyze');await idle();
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('60毫秒'));
  p=await current();assert.equal(p.history.length,selectedHistory);assert(!p.document);
  await page.uncheck('#fitGated');await page.click('#analyze');await idle();
  p=await current();assert.equal(p.document.source_job.schema,'vsl.event-authoring-job/10');
  assert.equal(p.document.observation.time_analysis.event_frames,768);
  assert((await page.textContent('#analysisInfo')).includes('短事件 16.0 ms'));
  await page.click('#render');await page.waitForFunction(()=>!document.querySelector('#render').disabled&&document.querySelector('#downloads a'));
  p=await current();assert.equal(p.render_report.renderer_abi,4);assert(!p.preview_stale);
  const response=await page.request.get(base+p.downloads+'parameters.json');assert(response.ok());
  const pack=await response.json();assert.equal(pack.document.source_job.schema,'vsl.event-authoring-job/10');
  assert.equal(pack.candidate_scan.report.detector.family,'short_high');
  assert(pack.source_context.matches_current_selection&&pack.source_context.matches_model_event_and_before_background);
  const originalPreview=Buffer.from(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  const renderRevision=p.history[0].id;
  await page.locator('#contextPanel').evaluate(e=>e.open=false);
  await page.locator('#candidatePanel').evaluate(e=>e.open=false);
  await page.locator('#analysisInfo').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#render').disabled);
  assert.equal(await page.inputValue('#scanDetector'),'short_high');
  p=await current();assert.equal(p.scan_run,scanRun);assert.equal(p.document.observation.time_analysis.event_frames,768);
  await page.locator('#historyPanel').evaluate(e=>e.open=true);
  await page.selectOption('#historyList',selectedRevision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelector('#toast').textContent.includes('已完成'));
  p=await current();assert(!p.document&&p.context_matches_selection);assert.equal(p.scan_run,scanRun);
  await page.selectOption('#historyList',renderRevision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelector('#toast').textContent.includes('已完成'));
  p=await current();assert(p.document&&!p.preview_stale);
  const download=page.waitForEvent('download');await page.locator('#downloads a').filter({hasText:'JSON'}).click();
  await(await download).saveAs(path.join(out,'parameters.json'));
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(out,'parameters.json'),'utf8')),pack);
  const packageFile=path.join(out,'source-free.json');fs.writeFileSync(packageFile,JSON.stringify(pack));
  const previousProject=p.id;
  await page.locator('#presetFile').setInputFiles(packageFile);
  await page.waitForFunction(id=>document.querySelector('#projects').value!==id&&document.querySelector('#projects').value!==''&&!document.querySelector('#render').disabled,previousProject);
  p=await current();assert(!p.audio&&p.document);assert(await page.locator('#scanDetector').isDisabled());
  await page.click('#render');await page.waitForFunction(()=>!document.querySelector('#render').disabled&&document.querySelector('#downloads a'));
  p=await current();const importedPreview=Buffer.from(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  assert(wavSamples(originalPreview).equals(wavSamples(importedPreview)));
  await page.setViewportSize({width:412,height:915});
  await page.locator('.transport').scrollIntoViewIfNeeded();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await page.screenshot({path:path.join(out,'mobile-controls.png')});
  report.mobile_boxes=await page.evaluate(()=>Object.fromEntries(['.transport','#render','#player','.audition-controls'].map(selector=>{
   const e=document.querySelector(selector),r=e.getBoundingClientRect(),s=getComputedStyle(e);
   return[selector,{x:r.x,y:r.y,width:r.width,height:r.height,display:s.display,position:s.position,opacity:s.opacity}];
  })));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  const renderBox=await page.locator('#render').boundingBox();assert(renderBox&&renderBox.x>=0&&renderBox.x+renderBox.width<=412);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',source_free_project:p.id,short_scan_selection_context:true,
   invalid_gated_preserves_project:true,job10_C_render:true,short_measurement_readout:true,
   reload_history_and_download:true,source_free_C_PCM_exact:true,desktop_mobile_checked:true,
   one_player:true,driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
