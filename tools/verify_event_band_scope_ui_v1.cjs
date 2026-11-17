// A bounded owned browser/server verifies the actual editor and C previews.
const path=require('path'),fs=require('fs'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=process.argv[4],base=process.argv[5];
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const original=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return original.call(this);};});
  const ready=()=>page.waitForFunction(()=>!document.querySelector('#analyze').disabled,{},{timeout:60000});
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert(await page.locator('#scopeLow').isDisabled());assert.equal(await page.locator('audio').count(),1);
  await page.locator('#audioFile').setInputFiles(fixture);await ready();
  await page.fill('#start','.4');await page.fill('#end','1');await page.fill('#bgStart','0');await page.fill('#bgEnd','.3');
  await page.click('#analyze');await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('对比度不足'));await ready();
  assert.equal(await page.locator('#render').isDisabled(),true);
  await page.selectOption('#scopeMode','band');assert.equal(await page.locator('#scopeLow').isDisabled(),false);
  await page.fill('#scopeLow','6000');await page.fill('#scopeHigh','10000');await page.click('#analyze');
  await page.waitForFunction(()=>document.querySelector('#modeRows tr')&&!document.querySelector('#render').disabled,{},{timeout:60000});
  assert((await page.innerText('#analysisInfo')).includes('6000–10000 Hz'));
  assert((await page.innerText('#analysisInfo')).includes('全频'));
  assert.equal(await page.locator('#bandRows tr').count(),1);
  await page.click('#render');await page.waitForFunction(()=>document.querySelector('#downloads a')&&!document.querySelector('#render').disabled,{},{timeout:60000});
  const id=await page.inputValue('#projects'),initial=await(await page.request.get(base+'/api/events/project/'+id)).json();
  assert.equal(initial.reference_matches_model,true);const saved=initial.history[0].id;
  await page.reload();await page.waitForFunction(()=>document.querySelector('#scopeLow').value==='6000');await ready();
  assert.equal(await page.inputValue('#scopeMode'),'band');assert.equal(await page.inputValue('#scopeHigh'),'10000');
  assert.equal(await page.locator('#scopeLow').isDisabled(),false);
  await page.selectOption('#scopeMode','full');assert(await page.locator('#scopeLow').isDisabled());
  await page.click('#analyze');await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('对比度不足'));await ready();
  assert(await page.locator('#scopeLow').isDisabled());assert((await page.innerText('#sourceBinding')).includes('来源不同'));
  const refused=await(await page.request.get(base+'/api/events/project/'+id)).json();
  assert.deepEqual(refused.document.parameters,initial.document.parameters);
  await page.click('#historyPanel summary');await page.selectOption('#historyList',saved);await page.click('#restoreHistory');
  await page.waitForFunction(()=>document.querySelector('#scopeMode').value==='band'&&!document.querySelector('#restoreHistory').disabled);
  assert.equal(await page.inputValue('#scopeLow'),'6000');assert.equal(await page.locator('#scopeLow').isDisabled(),false);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('#scopeMode').scrollIntoViewIfNeeded();
  await page.waitForTimeout(3200);await page.screenshot({path:path.join(out,'mobile-scope.png')});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',full_refuses_scoped_admits:true,scope_and_full_contrast_visible:true,
   controls_restore_disabled_state:true,scope_survives_reload:true,scope_history_restored:true,
   refused_scope_change_preserves_profile:true,one_player_no_autoplay:await page.locator('audio').evaluate(a=>a.paused),
   desktop_mobile_checked:true,automated_audio_muted:true,live_driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
