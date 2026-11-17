// Bounded headless test. Its own local test server is closed by the parent.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const out=process.argv[3],fixture=process.argv[4],base=process.argv[5];
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[];let report={result:'running'};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const original=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return original.call(this);};});
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert.equal(await page.locator('audio').count(),1);assert.equal(await page.locator('#render').isDisabled(),true);
  await page.locator('#audioFile').setInputFiles(fixture);
  await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('1.20s')&&!document.querySelector('#analyze').disabled);
  await page.fill('#start','.4');await page.fill('#end','.95');await page.fill('#bgStart','0');await page.fill('#bgEnd','.3');
  await page.selectOption('#kind','afterfire');await page.selectOption('#viewpoint','engine');await page.fill('#context','Known synthetic decay; UI verification, not a real vehicle.');
  await page.click('#analyze');await page.waitForFunction(()=>document.querySelector('#modeRows tr')&&!document.querySelector('#render').disabled,{},{timeout:60000});
  assert.equal(await page.inputValue('#kind'),'afterfire');assert.equal(await page.inputValue('#viewpoint'),'engine');
  const modeCount=await page.locator('#modeRows tr').count();assert(modeCount>0&&modeCount<=12);
  assert.equal(await page.locator('#bandRows tr').count(),4);
  await page.fill('#c_seconds','.7');await page.fill('#c_pitch','1.03');await page.fill('#c_seed','48271');
  await page.click('#render');await page.waitForFunction(()=>document.querySelector('#downloads a')&&!document.querySelector('#render').disabled,{},{timeout:60000});
  assert.equal(await page.locator('#downloads a').count(),5);
  const firstAudio=await page.locator('#player').getAttribute('src');
  await page.waitForFunction(()=>document.querySelector('#player').readyState>=1&&Math.abs(document.querySelector('#player').duration-.7)<.00001);
  // libsndfile FLOAT WAVs may contain a timestamp in PEAK. Compare the actual data chunk.
  const digest=async url=>{const wav=await (await page.request.get(base+url)).body();assert.equal(wav.toString('ascii',0,4),'RIFF');
   for(let at=12;at+8<=wav.length;){const size=wav.readUInt32LE(at+4);if(wav.toString('ascii',at,at+4)==='data')return crypto.createHash('sha256').update(wav.subarray(at+8,at+8+size)).digest('hex');at+=8+size+(size&1);}throw Error('No WAV data chunk');};
  const firstHash=await digest(firstAudio);const projectId=await page.inputValue('#projects');
  const initial=await (await page.request.get(base+'/api/events/project/'+projectId)).json();
  const firstRevision=initial.history[0].id;assert.equal(initial.preview_stale,false);
  assert.equal(initial.document.viewpoint,'engine');assert.equal(initial.document.kind,'afterfire');assert.equal(initial.reference_matches_model,true);
  await page.click('#pinA');await page.fill('#p_level','0.5');await page.click('#render');
  await page.waitForFunction(old=>document.querySelector('#player').getAttribute('src')!==old&&!document.querySelector('#render').disabled,firstAudio,{timeout:60000});
  const editedAudio=await page.locator('#player').getAttribute('src');assert.notEqual(await digest(editedAudio),firstHash);
  await page.click('#listenA');assert.equal(await page.locator('#player').getAttribute('src'),firstAudio);
  await page.locator('#player').evaluate(a=>{a.volume=.4;return a.play();});
  await page.click('#listenB');assert.equal(await page.locator('#player').getAttribute('src'),editedAudio);
  assert.equal(await page.locator('#player').evaluate(a=>a.volume),.4);
  await page.click('#listenReference');assert.equal(await page.locator('#player').getAttribute('src'),initial.reference_url);
  await page.locator('#player').evaluate(a=>a.pause());
  // Save/reload and exact history restoration through the visible controls.
  await page.fill('#name','事件界面测试');await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#projectLabel').textContent==='事件界面测试');
  await page.reload();await page.waitForFunction(()=>document.querySelector('#name').value==='事件界面测试');
  assert.equal(await page.inputValue('#p_level'),'0.5');assert.equal(await page.inputValue('#c_seed'),'48271');
  await page.click('#historyPanel summary');await page.selectOption('#historyList',firstRevision);await page.click('#restoreHistory');
  await page.waitForFunction(url=>document.querySelector('#player').getAttribute('src')===url&&!document.querySelector('#restoreHistory').disabled,firstAudio);
  await page.click('#render');await page.waitForFunction(url=>document.querySelector('#player').getAttribute('src')!==url&&!document.querySelector('#render').disabled,firstAudio,{timeout:60000});
  assert.equal(await digest(await page.locator('#player').getAttribute('src')),firstHash);
  // A refused fit saves draft edits, retains existing parameters and flags provenance mismatch.
  await page.fill('#p_level','.6');await page.fill('#start','0');await page.fill('#end','.12');await page.fill('#bgStart','.15');await page.fill('#bgEnd','.27');await page.click('#analyze');
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('对比度不足')&&!document.querySelector('#analyze').disabled,{},{timeout:60000});
  assert.equal(await page.inputValue('#p_level'),'0.6');assert((await page.innerText('#sourceBinding')).includes('来源不同'));
  const refused=await (await page.request.get(base+'/api/events/project/'+projectId)).json();assert.equal(refused.document.parameters.level,.6);assert.equal(refused.analysis.status,'analysis_only');
  await page.fill('#p_level','.65');
  const saved=await (await page.request.get(base+refused.downloads+'parameters.json')).json();assert(saved.document.parameters.modes.length>0);
  // Parameter import without any reference file still generates the same C result.
  const packagePath=path.join(out,'import.json');fs.writeFileSync(packagePath,JSON.stringify(saved));
  await page.locator('#presetFile').setInputFiles(packagePath);
  await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent==='参数工程'&&!document.querySelector('#render').disabled);
  const previous=await (await page.request.get(base+'/api/events/project/'+projectId)).json();assert.equal(previous.document.parameters.level,.65);
  assert.equal(await page.locator('#analyze').isDisabled(),true);
  await page.click('#render');await page.waitForFunction(()=>document.querySelector('#downloads a')&&!document.querySelector('#render').disabled,{},{timeout:60000});
  assert.equal(await digest(await page.locator('#player').getAttribute('src')),firstHash);
  // Current limits/JSON are real editable controls.
  await page.locator('summary').filter({hasText:'振荡模态'}).click();
  const before=await page.locator('#modeRows tr').count();await page.locator('#modeRows tr').first().locator('button').click();
  assert.equal(await page.locator('#modeRows tr').count(),before-1);await page.click('#addMode');assert.equal(await page.locator('#modeRows tr').count(),before);
  await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(3200);await page.screenshot({path:path.join(out,'mobile.png')});
  await page.locator('#profileControls').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'mobile-controls.png')});
  const transport=await page.locator('.transport').boundingBox();assert(transport.y>=0&&transport.y<80);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.goto(base+'/');assert.equal(await page.locator('a[href="/events.html"]').count(),1);
  assert.deepEqual(errors,[]);
  report={result:'passed',errors,real_upload_selection_fit_and_C_preview:true,mode_count:modeCount,band_count:4,
   controls_affect_PCM:true,one_player_AB_preserves_volume:true,reference_uses_same_player:true,
   saved_parameters_survive_reload:true,history_restores_exact_PCM:true,refused_fit_preserves_draft_and_flags_binding:true,project_switch_preserves_unsaved_parameters:true,
   parameter_import_without_audio_reproduces_PCM:true,editable_modal_rows:true,download_count:5,
   main_workbench_links_event_editor:true,mobile_no_horizontal_overflow:true,automated_audio_muted:true,live_driver_not_launched:true};
 }catch(e){report={result:'failed',error:String(e),errors};throw e;}
 finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
