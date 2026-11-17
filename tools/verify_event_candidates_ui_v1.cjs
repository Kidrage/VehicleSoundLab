// Own bounded server; no driver launch or persistent service.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=process.argv[4],base=process.argv[5];
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  const current=async()=>{const id=await page.inputValue('#projects');return(await page.request.get(base+'/api/events/project/'+id)).json();};
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert(await page.locator('#scanCandidates').isDisabled());assert.equal(await page.locator('audio').count(),1);
  await page.selectOption('#viewpoint','cabin');await page.locator('#audioFile').setInputFiles(fixture);
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled);
  await page.click('#candidatePanel summary');await page.click('#scanCandidates');
  await page.waitForFunction(()=>document.querySelector('#candidateRows [data-candidate-index]')&&!document.querySelector('#scanCandidates').disabled);
  let p=await current();assert.equal(p.candidate_scan.candidates.length,2);assert.equal(p.candidate_scan.both_above_3db,1);
  assert(!p.document&&!p.candidate_scan.fit_performed&&!p.candidate_scan.physical_identity_confirmed);
  assert.equal(await page.locator('[data-candidate-index]').count(),1);
  assert.equal(await page.locator('[data-candidate-index]').getAttribute('data-candidate-index'),'1');
  await page.check('#candidateAll');assert.equal(await page.locator('[data-candidate-index]').count(),2);
  await page.click('[data-candidate-index="1"]');
  await page.waitForFunction(()=>document.querySelector('#start').value==='4.695'&&!document.querySelector('#scanCandidates').disabled);
  await page.waitForFunction(()=>document.querySelector('audio').src.startsWith('blob:')&&document.querySelector('audio').readyState>=3);
  p=await current();assert(p.context_matches_selection);assert(!p.document);assert.equal(p.selected_candidate.index,1);
  assert.deepEqual(p.selection,[4.695,4.795]);assert.deepEqual(p.background_selection,[4.37,4.57]);
  assert.deepEqual(p.following_background_selection,[4.88,5.08]);assert.equal(p.viewpoint,'cabin');
  assert.equal(await page.inputValue('#afterStart'),'4.88');assert.equal(await page.inputValue('#afterEnd'),'5.08');
  assert(await page.locator('#contextPanel').evaluate(e=>e.open));assert(await page.locator('#analyze').isEnabled());
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));
  const digest=await page.locator('audio').evaluate(async a=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await(await fetch(a.src)).arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join(''));
  assert.equal(digest,p.context_probe.monitor_sha256);
  await page.locator('audio').evaluate(async a=>{a.muted=true;await a.play();});
  await page.waitForFunction(()=>document.querySelector('audio').currentTime>.08);await page.locator('audio').evaluate(a=>a.pause());
  const fetched=await(await page.request.get(base+p.scan_report_url)).json();assert.deepEqual(fetched,p.candidate_scan);
  const revision=p.history[0].id,oldRun=p.scan_run;
  await page.reload();await page.waitForFunction(()=>document.querySelector('#start').value==='4.695'&&!document.querySelector('#scanCandidates').disabled);
  assert.equal((await current()).selected_candidate.index,1);
  await page.click('#candidatePanel summary');await page.click('#scanCandidates');
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled&&document.querySelector('#toast').textContent.includes('候选扫描已保存'));
  p=await current();assert.notEqual(p.scan_run,oldRun);assert(!p.selected_candidate);assert.deepEqual(p.selection,[4.695,4.795]);
  const stale=await(await page.request.post(base+'/api/events/candidate',{data:{id:p.id,scan_run:oldRun,candidate_index:1}})).json();
  let status;for(let n=0;n<100;n++){status=await(await page.request.get(base+'/api/job/'+stale.job)).json();if(status.status==='error')break;await new Promise(r=>setTimeout(r,50));}
  assert.equal(status.status,'error');assert(status.error.includes('候选列表已变化'));
  await page.click('#historyPanel summary');await page.selectOption('#historyList',revision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelector('#toast').textContent.includes('已完成'));
  p=await current();assert.equal(p.scan_run,oldRun);assert.equal(p.selected_candidate.index,1);assert(p.context_matches_selection);
  await page.locator('#candidatePanel').evaluate(e=>e.open=true);await page.check('#candidateAll');
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.locator('#candidatePanel').screenshot({path:path.join(out,'desktop-candidates.png')});
  await page.setViewportSize({width:390,height:844});await page.locator('#candidatePanel').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile-candidates.png')});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',project_id:p.id,scan_counts:[2,1],source_context_HTTP_hash_exact:true,
   fixed_windows_populated:true,no_automatic_fit:true,no_automatic_physical_label:true,
   history_reload_and_restore:true,stale_selection_rejected:true,one_player_muted_audition:true,
   desktop_mobile_checked:true,driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
