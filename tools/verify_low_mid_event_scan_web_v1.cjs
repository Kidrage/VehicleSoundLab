const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=process.argv[4],base=process.argv[5];
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let page;const report={result:'running'},errors=[];
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  const current=async()=>{const id=await page.inputValue('#projects');return(await page.request.get(base+'/api/events/project/'+id)).json();};
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert(await page.locator('#scanDetector').isDisabled());assert.equal(await page.locator('audio').count(),1);
  await page.locator('#audioFile').setInputFiles(fixture);
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled);
  await page.locator('#candidatePanel').evaluate(e=>e.open=true);
  assert.equal(await page.inputValue('#scanDetector'),'high');
  await page.selectOption('#scanDetector','low_mid');await page.click('#scanCandidates');
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled&&document.querySelector('#candidateRows [data-candidate-index]'));
  let p=await current();assert.equal(p.scan_detector,'low_mid');assert.equal(p.candidate_scan.detector.family,'low_mid');
  assert((await page.textContent('#candidateInfo')).includes('低中频扫描'));
  const index=p.candidate_scan.candidates.findIndex(v=>Math.abs(v.source_seconds-1.4)<.1);assert(index>=0);
  await page.click('[data-candidate-index="'+index+'"]');
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled&&document.querySelector('audio').src.startsWith('blob:'));
  p=await current();assert(p.context_matches_selection&&!p.document);
  assert.equal(p.scan_detector,'low_mid');assert.equal(p.selected_candidate.index,index);
  const revision=p.history[0].id,run=p.scan_run;
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled);
  assert.equal(await page.inputValue('#scanDetector'),'low_mid');
  await page.locator('#candidatePanel').evaluate(e=>e.open=true);
  await page.selectOption('#scanDetector','high');await page.click('#scanCandidates');
  await page.waitForFunction(()=>!document.querySelector('#scanCandidates').disabled&&document.querySelector('#toast').textContent.includes('候选扫描已保存'));
  p=await current();assert.equal(p.scan_detector,'high');assert(!p.candidate_scan.detector.family);assert(!p.selected_candidate);
  assert(p.candidate_scan.candidates.every(v=>Math.abs(v.source_seconds-1.4)>.1));
  await page.locator('#historyPanel').evaluate(e=>e.open=true);await page.selectOption('#historyList',revision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelector('#toast').textContent.includes('已完成'));
  p=await current();assert.equal(p.scan_run,run);assert.equal(p.scan_detector,'low_mid');assert.equal(await page.inputValue('#scanDetector'),'low_mid');
  assert.equal((await(await page.request.get(base+p.scan_report_url)).json()).detector.family,'low_mid');
  await page.locator('#candidatePanel').evaluate(e=>e.open=true);await page.locator('#candidatePanel').screenshot({path:path.join(out,'desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.locator('#candidatePanel').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',project:p.id,default_high:true,low_mid_scan_and_select:true,
   reload_history_preserve_family:true,download_family_exact:true,no_automatic_fit_or_label:true,
   desktop_mobile_checked:true,one_player:true,driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
