// Own bounded server: material -> editable multi-stage envelopes -> C exports.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=JSON.parse(fs.readFileSync(process.argv[4],'utf8')),base=process.argv[5];
function pcm(wav){for(let p=12;p+8<=wav.length;){const n=wav.readUInt32LE(p+4);if(wav.toString('ascii',p,p+4)==='data')return wav.subarray(p+8,p+8+n);p+=8+n+(n&1);}throw Error('Missing WAV data');}
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let page;const report={result:'running'},errors=[];
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  await page.click('[data-preset=catch]');await page.waitForFunction(()=>!document.querySelector('#save').disabled);
  const current=async()=>{const id=await page.inputValue('#projects');return (await page.request.get(base+'/api/events/project/'+id)).json();};
  await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled);
  let p=await current();assert(p.document.parameters.modes.every(m=>!('attack_seconds' in m)));assert(!('contours' in p.document.parameters));
  await page.selectOption('#kind','crank');await page.selectOption('#viewpoint','cabin');
  await page.locator('#audioFile').setInputFiles(fixture.context);
  await page.waitForFunction(()=>!document.querySelector('#analyze').disabled);
  for(const [id,value] of Object.entries({start:'3.2',end:'3.95',bgStart:'.2',bgEnd:'1.2'}))await page.fill('#'+id,value);
  assert(await page.locator('#fitEnvelope').isDisabled());await page.check('#fitResponse');
  assert(!await page.locator('#fitEnvelope').isDisabled());await page.check('#fitEnvelope');assert(!await page.locator('#fitContour').isDisabled());await page.check('#fitContour');await page.selectOption('#contourMethod','band-contour-v2');await page.check('#fitGated');
  await page.click('#analyze');await page.waitForFunction(()=>document.querySelectorAll('#contourRows fieldset').length===1&&!document.querySelector('#analyze').disabled,null,{timeout:240000});
  p=await current();assert.equal(p.document.schema,'vsl.event-profile/4');assert.deepEqual(p.document.parameters,fixture.expected);assert.equal(p.envelope_fit,'band-contour-v2');assert(p.document.fit.contour_fit.bands[0].selected===false);assert((await page.textContent('#analysisInfo')).includes('保留原包络'));assert.equal(await page.inputValue('#contourMethod'),'band-contour-v2');
  const original=p.document.parameters.contours[0].gain[1];
  const render=async()=>{await page.click('#render');await page.waitForFunction(()=>document.querySelector('#downloads a')&&!document.querySelector('#render').disabled,null,{timeout:60000});return current();};
  p=await render();const saved=p.history[0].id;
  const initial=pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  await page.click('#contourPanel summary');
  await page.locator('#contourRows fieldset').nth(0).locator('[data-gain]').nth(1).fill('.12');p=await render();
  const changed=pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());assert(!initial.equals(changed));
  await page.reload();await page.waitForFunction(()=>document.querySelector('#projects').value&&!document.querySelector('#render').disabled);
  assert(await page.locator('#fitEnvelope').isChecked());assert(await page.locator('#fitContour').isChecked());assert.equal(await page.inputValue('#contourMethod'),'band-contour-v2');assert.equal(Number(await page.locator('#contourRows fieldset').nth(0).locator('[data-gain]').nth(1).inputValue()),.12);
  await page.click('#historyPanel summary');await page.selectOption('#historyList',saved);await page.click('#restoreHistory');
  await page.waitForFunction(expected=>Number(document.querySelector('#contourRows fieldset')?.querySelectorAll('[data-gain]')[1]?.value)===expected&&!document.querySelector('#restoreHistory').disabled,original);
  p=await render();assert(initial.equals(pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body())));
  for(const n of ['parameters.json','parameters.csv','profile.h','event-design.zip'])assert.equal((await page.request.get(base+p.downloads+n)).status(),200);
  await page.selectOption('#scopeMode','band');assert(await page.locator('#fitEnvelope').isDisabled());assert(await page.locator('#fitContour').isDisabled());await page.selectOption('#scopeMode','full');
  await page.locator('#contourPanel').evaluate(el=>el.open=true);
  const card=page.locator('#contourRows fieldset').nth(0);assert(await card.locator('[data-add-point]').isDisabled());assert(await card.locator('tbody tr').nth(0).locator('button').isDisabled());
  const beforeInvalid=p.document.parameters;await card.locator('[data-time]').nth(1).fill('0');await page.click('#save');await page.waitForFunction(()=>document.querySelector('#toast').classList.contains('error'));assert.deepEqual((await current()).document.parameters,beforeInvalid);await card.locator('[data-time]').nth(1).fill(String(beforeInvalid.contours[0].seconds[1]));
  p=await render();
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.locator('#contourRows').screenshot({path:path.join(out,'contours.png')});
  await page.setViewportSize({width:390,height:844});await page.locator('#fitEnvelope').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile.png')});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.equal(await page.locator('audio').count(),1);assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',project_id:p.id,legacy_missing_attack_preserved:true,material_parameters_exact:true,weak_band_explicitly_retained:true,new_strategy_saved_and_restored:true,
   contour_edit_changes_C_PCM:true,invalid_time_preserves_saved_parameters:true,point_limit_and_first_point_checked:true,history_restores_PCM_exact:true,reload_preserves_controls:true,
   exports_HTTP200:true,scope_and_fit_dependencies:true,one_player_no_autoplay:true,desktop_mobile_checked:true,
   persistent_service_restarted:false,live_driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
