// Bounded owned service only. Material authoring, diagnostics and actual C PCM.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=process.argv[4],base=process.argv[5];
function pcm(wav){for(let p=12;p+8<=wav.length;){const n=wav.readUInt32LE(p+4);if(wav.toString('ascii',p,p+4)==='data')return wav.subarray(p+8,p+8+n);p+=8+n+(n&1);}throw Error('WAV data missing');}
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  const ready=()=>page.waitForFunction(()=>!document.querySelector('#analyze').disabled,null,{timeout:90000});
  const current=async()=>{const id=await page.inputValue('#projects');return (await page.request.get(base+'/api/events/project/'+id)).json();};
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert(await page.locator('#probeContext').isDisabled());assert.equal(await page.locator('audio').count(),1);
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));
  await page.selectOption('#kind','catch');await page.selectOption('#viewpoint','cabin');
  await page.locator('#audioFile').setInputFiles(fixture);await ready();
  for(const [key,value] of Object.entries({start:'2.22',end:'3.02',bgStart:'0',bgEnd:'1.2'}))await page.fill('#'+key,value);
  await page.click('#analyze');await page.waitForFunction(()=>!document.querySelector('#render').disabled,null,{timeout:90000});
  await page.click('#render');await page.waitForFunction(()=>document.querySelector('#downloads a')&&!document.querySelector('#render').disabled,null,{timeout:60000});
  const initial=await current(),audio=pcm(await(await page.request.get(base+initial.downloads+'synthesis.wav')).body());
  await page.click('#contextPanel summary');
  // Selecting a fitted model reinitializes uncommitted diagnostic-only inputs.
  await page.fill('#afterStart','3.8');await page.fill('#afterEnd','4.4');
  await page.click('#probeContext');await page.waitForFunction(()=>document.querySelector('#contextInfo').textContent.startsWith('本次选区')&&!document.querySelector('#probeContext').disabled,null,{timeout:60000});
  let p=await current();const contextRevision=p.history[0].id;
  assert.deepEqual(p.document,initial.document);assert.deepEqual(p.controls,initial.controls);assert.equal(p.last_version,initial.last_version);assert(!p.preview_stale);
  assert(p.context_matches_selection);assert(!p.context_probe.fit_performed);assert(!p.context_probe.physical_identity_confirmed);
  assert.deepEqual(p.context_probe.backgrounds.map(r=>r.name),['before','after']);
  assert.equal((await page.request.get(base+p.context_report_url)).status(),200);
  await page.click('#listenContext');await page.locator('audio').evaluate(a=>{a.muted=true;a.load();});
  await page.waitForFunction(()=>document.querySelector('audio').src.startsWith('blob:')&&document.querySelector('audio').readyState>=3);
  await page.locator('audio').evaluate(a=>{a.currentTime=2;});await page.waitForFunction(()=>Math.abs(document.querySelector('audio').currentTime-2)<.1);
  await page.locator('audio').evaluate(a=>a.play());await page.waitForFunction(()=>document.querySelector('audio').currentTime>2.1);await page.locator('audio').evaluate(a=>a.pause());
  await page.route('**/master-monitor.wav',async route=>{await new Promise(r=>setTimeout(r,250));await route.continue().catch(()=>{});});
  await page.click('#listenSource');await page.click('#listenB');await page.click('#listenContext');
  await page.waitForFunction(()=>document.querySelector('audio').src.startsWith('blob:')&&document.querySelector('audio').readyState>=3);
  const adoptedHash=await page.locator('audio').evaluate(async a=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await(await fetch(a.src)).arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join(''));
  assert.equal(adoptedHash,p.context_probe.monitor_sha256);await page.unroute('**/master-monitor.wav');
  await page.click('#render');await page.waitForFunction(()=>!document.querySelector('#render').disabled&&document.querySelector('#downloads a'),null,{timeout:60000});
  p=await current();assert(audio.equals(pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body())));
  const bundle=await(await page.request.get(base+p.downloads+'parameters.json')).json();
  assert(bundle.source_context.matches_current_selection&&bundle.source_context.matches_model_event_and_before_background);
  assert(!bundle.source_context.following_background_used_for_fit);
  assert.deepEqual((await(await page.request.get(base+p.downloads+'source-context.json')).json()),bundle.source_context);
  await page.fill('#start','2.23');assert((await page.textContent('#contextInfo')).startsWith('选区已变化'));
  await page.click('#save');await ready();p=await current();assert(!p.context_matches_selection);assert(!p.reference_matches_model);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#start').value==='2.23'&&!document.querySelector('#analyze').disabled);
  await page.click('#historyPanel summary');await page.selectOption('#historyList',contextRevision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>document.querySelector('#start').value==='2.22'&&!document.querySelector('#restoreHistory').disabled);
  p=await current();assert(p.context_matches_selection);assert(audio.equals(pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body())));
  await page.selectOption('#scopeMode','band');assert((await page.textContent('#contextInfo')).startsWith('选区已变化'));
  await page.fill('#scopeLow','1200');await page.fill('#scopeHigh','14000');await page.click('#contextPanel summary');await page.click('#probeContext');
  await page.waitForFunction(()=>document.querySelector('#contextInfo').textContent.includes('选定频带')&&!document.querySelector('#probeContext').disabled,null,{timeout:60000});
  p=await current();assert.equal(p.context_probe.analysis_scope.mode,'band');assert(p.context_matches_selection);
  const beforeInvalid=JSON.stringify(p.context_probe),historyCount=p.history.length;
  await page.fill('#afterStart','2.5');await page.click('#probeContext');
  await page.waitForFunction(()=>document.querySelector('#toast').classList.contains('error')&&!document.querySelector('#probeContext').disabled);
  p=await current();assert.equal(JSON.stringify(p.context_probe),beforeInvalid);assert.equal(p.history.length,historyCount);
  await page.fill('#afterStart','3.8');await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('#contextPanel').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile-context.png')});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',project_id:p.id,context_revision:contextRevision,
   real_material_C_PCM_preserved:true,source_and_model_binding_checked:true,full_and_scoped_probes:true,
   rapid_switch_adopts_latest_audio_hash:true,
   context_evidence_in_parameter_exports:true,
   source_context_HTTP_seek_and_muted_play:true,history_restores_context_and_C_PCM:true,
   invalid_following_background_preserves_project:true,selection_save_reload:true,
   one_player_no_autoplay:true,desktop_mobile_checked:true,driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
