// Own bounded test server only: actual material analysis, edits, history and C exports.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],fixture=JSON.parse(fs.readFileSync(process.argv[4],'utf8')),base=process.argv[5];
function pcm(wav){
 assert.equal(wav.toString('ascii',0,4),'RIFF');assert.equal(wav.toString('ascii',8,12),'WAVE');
 for(let p=12;p+8<=wav.length;){const n=wav.readUInt32LE(p+4);if(wav.toString('ascii',p,p+4)==='data')return wav.subarray(p+8,p+8+n);p+=8+n+(n&1);}
 throw Error('Missing WAV data');
}
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report={result:'running'},errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
  const ready=()=>page.waitForFunction(()=>!document.querySelector('#analyze').disabled,null,{timeout:90000});
  const current=async()=>{const id=await page.inputValue('#projects');return (await page.request.get(base+'/api/events/project/'+id)).json();};
  const rendered=()=>page.waitForFunction(()=>document.querySelector('#downloads a')&&!document.querySelector('#render').disabled,null,{timeout:60000});
  await page.goto(base+'/events.html');await page.waitForSelector('[data-preset=catch]');
  assert.equal(await page.locator('audio').count(),1);assert(!await page.locator('#fitResponse').isChecked());
  await page.selectOption('#kind','catch');await page.selectOption('#viewpoint','cabin');
  await page.locator('#audioFile').setInputFiles(fixture.context);await ready();
  for(const [id,value] of Object.entries({start:'2.22',end:'3.02',bgStart:'0',bgEnd:'1.2'}))await page.fill('#'+id,value);
  await page.check('#fitResponse');await page.click('#analyze');
  await page.waitForFunction(()=>document.querySelector('#p_noise_lowpass_hz').value==='10000'&&!document.querySelector('#analyze').disabled,null,{timeout:90000});
  const fitted=await current();assert.deepEqual(fitted.document.parameters,fixture.expected);
  assert.equal(fitted.response_fit,'source-response-v1');assert.equal(fitted.document.schema,'vsl.event-profile/2');
  await page.click('#render');await rendered();let p=await current();const saved=p.history[0].id;
  const initial=pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));
  await page.fill('#p_noise_lowpass_hz','6000');await page.click('#render');await rendered();p=await current();
  const changed=pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body());assert(!initial.equals(changed));
  await page.reload();await page.waitForFunction(()=>document.querySelector('#p_noise_lowpass_hz').value==='6000'&&!document.querySelector('#analyze').disabled);
  assert(await page.locator('#fitResponse').isChecked());
  await page.click('#historyPanel summary');await page.selectOption('#historyList',saved);await page.click('#restoreHistory');
  await page.waitForFunction(()=>document.querySelector('#p_noise_lowpass_hz').value==='10000'&&!document.querySelector('#restoreHistory').disabled);
  await page.click('#render');await rendered();p=await current();
  assert(initial.equals(pcm(await(await page.request.get(base+p.downloads+'synthesis.wav')).body())));
  for(const name of ['parameters.json','profile.h','parameters.csv','event-design.zip'])assert.equal((await page.request.get(base+p.downloads+name)).status(),200);
  await page.selectOption('#scopeMode','band');assert(await page.locator('#fitResponse').isDisabled());
  await page.selectOption('#scopeMode','full');assert(!await page.locator('#fitResponse').isDisabled());
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('#fitResponse').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile-analysis.png')});
  await page.locator('#p_noise_lowpass_hz').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'mobile-cutoff.png')});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  const coloredId=p.id;
  await page.click('[data-preset=catch]');
  await page.waitForFunction(id=>document.querySelector('#projects').value!==id&&!document.querySelector('#save').disabled,coloredId);
  assert.equal(await page.inputValue('#p_noise_lowpass_hz'),'0');assert(!await page.locator('#fitResponse').isChecked());
  await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled);
  const legacy=await current();assert(!('noise_lowpass_hz' in legacy.document.parameters));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',project_id:coloredId,material_response_fit_parameters_exact:true,
   cutoff_edits_change_actual_C_PCM:true,history_restores_PCM_exact:true,checkbox_and_cutoff_persist:true,
   band_scope_disables_response_fit:true,legacy_missing_cutoff_preserved:true,exports_HTTP200:true,
   one_player_no_autoplay:true,desktop_mobile_checked:true,live_driver_not_launched:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
