const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],base=process.argv[4];
const fixtures=JSON.parse(fs.readFileSync(path.join(out,'fixtures.json'),'utf8'));
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
 assert.equal(format.readUInt32LE(4),48000);assert.equal(format.readUInt16LE(14),32);return data;
}
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--mute-audio']});
 let page;const report={result:'running'},errors=[];
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  const current=async()=>{const id=await page.inputValue('#projects');return(await page.request.get(base+'/api/events/project/'+id)).json();};
  const idle=async()=>page.waitForFunction(()=>!document.querySelector('#analyze').disabled);
  const frame=async()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const upload=async(job)=>{
   const prior=await page.inputValue('#projects');await page.locator('#audioFile').setInputFiles(job.source);
   await page.waitForFunction(id=>document.querySelector('#projects').value!==id&&document.querySelector('#projects').value!==''&&!document.querySelector('#analyze').disabled,prior);
   for(const [id,value] of [['start',job.seconds[0]],['end',job.seconds[1]],['bgStart',job.background_seconds[0]],['bgEnd',job.background_seconds[1]]])await page.fill('#'+id,String(value));
   await page.selectOption('#kind',job.kind);
  };
  const render=async()=>{await page.click('#render');await page.waitForFunction(()=>!document.querySelector('#render').disabled&&document.querySelector('#downloads a'));return current();};
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert(await page.locator('#responseMethod').isDisabled());assert.equal(await page.locator('audio').count(),1);
  await upload(fixtures.B_rank6);const initial=await current(),initialRevision=initial.history[0].id;
  await page.check('#fitResponse');assert(!(await page.locator('#responseMethod').isDisabled()));
  await page.selectOption('#responseMethod','source-response-ensemble-v1');
  assert(await page.locator('#fitEnvelope').isDisabled());assert(await page.locator('#fitContour').isDisabled());
  await page.selectOption('#scopeMode','band');assert(await page.locator('#responseMethod').isDisabled());
  await page.selectOption('#scopeMode','full');assert(!(await page.locator('#responseMethod').isDisabled()));
  const historyCount=(await current()).history.length;
  await page.check('#fitGated');await page.click('#analyze');await idle();
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('60毫秒'));
  assert.equal((await current()).history.length,historyCount);
  await page.uncheck('#fitGated');await page.click('#analyze');await idle();
  let p=await current();assert.equal(p.document.source_job.schema,'vsl.event-authoring-job/11');
  assert(p.analysis.response_summary.qualified);assert((await page.textContent('#analysisInfo')).includes('4次共同提参／4次独立检查 · 已通过'));
  p=await render();assert.equal(p.render_report.renderer_abi,4);
  const renderedRevision=p.history[0].id;
  const original=Buffer.from(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  const pack=await(await page.request.get(base+p.downloads+'parameters.json')).json();
  await page.locator('#analysisInfo').scrollIntoViewIfNeeded();await frame();
  await page.screenshot({path:path.join(out,'desktop-qualified.png'),fullPage:true});
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#render').disabled);
  assert.equal(await page.inputValue('#responseMethod'),'source-response-ensemble-v1');
  assert((await page.textContent('#analysisInfo')).includes('已通过'));
  await page.locator('#historyPanel').evaluate(e=>e.open=true);
  await page.selectOption('#historyList',initialRevision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelector('#toast').textContent.includes('已完成'));
  assert(!(await current()).document);assert(await page.locator('#responseMethod').isDisabled());
  await page.selectOption('#historyList',renderedRevision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelector('#toast').textContent.includes('已完成'));
  assert.equal(await page.inputValue('#responseMethod'),'source-response-ensemble-v1');
  const download=page.waitForEvent('download');await page.locator('#downloads a').filter({hasText:'JSON'}).click();
  await(await download).saveAs(path.join(out,'parameters.json'));
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(out,'parameters.json'),'utf8')),pack);
  const sourceFree=path.join(out,'source-free.json');fs.writeFileSync(sourceFree,JSON.stringify(pack));
  const prior=(await current()).id;await page.locator('#presetFile').setInputFiles(sourceFree);
  await page.waitForFunction(id=>document.querySelector('#projects').value!==id&&document.querySelector('#projects').value!==''&&!document.querySelector('#render').disabled,prior);
  p=await current();assert(!p.audio&&p.document);assert.equal(await page.inputValue('#responseMethod'),'source-response-ensemble-v1');
  p=await render();const imported=Buffer.from(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  assert(wavSamples(original).equals(wavSamples(imported)));
  report.qualified_project=initial.id;report.source_free_project=p.id;
  await upload(fixtures.B_rank3);await page.uncheck('#fitResponse');await page.click('#analyze');await idle();
  p=await render();const oldDoc=p.document,oldVersion=p.last_version;
  const oldWave=Buffer.from(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  await page.check('#fitResponse');await page.selectOption('#responseMethod','source-response-ensemble-v1');
  await page.click('#analyze');await idle();p=await current();
  assert.equal(p.analysis.status,'analysis_only');assert(!p.analysis.response_summary.qualified);
  assert.deepEqual(p.document,oldDoc);assert.equal(p.last_version,oldVersion);
  assert(wavSamples(oldWave).equals(wavSamples(Buffer.from(await(await page.request.get(base+p.downloads+'synthesis.wav')).body()))));
  const text=await page.textContent('#analysisInfo');assert(text.includes('未通过，保留已有音色参数'));assert(!text.includes('已通过频谱检查'));
  await page.locator('#analysisInfo').scrollIntoViewIfNeeded();await frame();
  await page.screenshot({path:path.join(out,'desktop-refused.png'),fullPage:true});
  await page.setViewportSize({width:412,height:915});await page.locator('#responseMethod').scrollIntoViewIfNeeded();await frame();
  await page.screenshot({path:path.join(out,'mobile-method.png')});
  const selectBox=await page.locator('#responseMethod').boundingBox();assert(selectBox&&selectBox.x>=0&&selectBox.x+selectBox.width<=412);
  await page.locator('.transport').scrollIntoViewIfNeeded();await frame();
  await page.screenshot({path:path.join(out,'mobile-controls.png')});
  const renderBox=await page.locator('#render').boundingBox();assert(renderBox&&renderBox.x>=0&&renderBox.x+renderBox.width<=412);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',method_selector_and_envelope_exclusion:true,invalid_short_gated_preserves_history:true,
   job11_actual_C:true,reload_history_download:true,source_free_C_PCM_exact:true,
   refusal_keeps_old_document_preview:true,refusal_readout_not_old_success:true,desktop_mobile_checked:true,
   one_player:true,driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
