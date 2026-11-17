// Own fixtures and browser only; never launch the driver's persistent process.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],base=process.argv[4],c=JSON.parse(fs.readFileSync(path.join(out,'configuration.json')));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let driverCalls=0;const errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1080}});
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(r.url().endsWith('/api/driver'))driverCalls++;});
  const ready=()=>page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('[data-group=base] select'));
  const field=key=>`[data-system-field="${key}"]`;
  const fill=async(key,value)=>page.fill(field(key),String(value));
  const download=async name=>{
   const href=await page.getByRole('link',{name:'下载整车参数',exact:true}).getAttribute('href');
   const response=await page.request.get(base+href);assert(response.ok());const raw=await response.body();
   fs.writeFileSync(path.join(out,name+'.preset.json'),raw);return {value:JSON.parse(raw),href};
  };
  await page.goto(base+'/vehicles.html');await ready();assert(!await page.isChecked('#includeSystem'));
  assert(await page.locator(field('startup.flare_rpm')).isDisabled());
  await page.fill('#name','浏览器整车配方 · 功能测试');await page.selectOption('[data-group=base] select',c.groups.base[0]);
  for(const key of ['idle','power','overrun']){await page.click(`[data-group=${key}] .add`);await page.selectOption(`[data-group=${key}] select`,c.groups[key][0]);}
  await page.check('#includeSystem');for(const s of await page.locator('#systemFields summary').all())await s.click();
  for(const [key,value]of Object.entries(c.system.startup))await fill('startup.'+key,value);
  for(const [key,value]of Object.entries(c.system.policy))await fill('policy.'+key,value);
  await page.check('#systemEventsEnabled');for(const [key,id]of Object.entries(c.system.events.projects))await page.selectOption(`[data-event-kind=${key}]`,id);
  await fill('macro.gain',.25);await fill('macro.pitch',1.1);await fill('macro.decay',.8);await fill('macro.texture',.9);await fill('layer.intake_gain',10);
  await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#downloads a').length===3);
  const id=await page.inputValue('#recipes'),version=await page.inputValue('#versions');assert(id&&version);
  const first=await download('browser');assert.equal(first.value.schema,'vsl.source-controller-preset/7');
  assert.equal(first.value.startup_response.flare_rpm,1800);assert.equal(first.value.event_policy.afterfire_min_count,3);
  assert.equal(first.value.control.events.pitch,1.1);assert.equal(first.value.control.intake_gain,.1);
  assert.equal(Object.keys(first.value.event_overrides).length,7);assert.equal(Object.keys(first.value.dna_bank.states).length,3);
  assert.equal(first.value.control.legacy_event_gain,0);assert((await page.textContent('#systemNotes')).includes('类型尚未确认'));
  await page.locator('#systemPanel').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.reload();await ready();assert(await page.isChecked('#includeSystem'));assert.equal((await download('reloaded')).href,first.href);
  for(const s of await page.locator('#systemFields summary').all())await s.click();
  assert.equal(await page.inputValue(field('macro.pitch')),'1.1');
  await fill('policy.afterfire_min_count',4);await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#status').classList.contains('error'));
  assert.equal((await download('after-invalid')).href,first.href);assert.equal(await page.locator('#versions option').count(),1);
  await fill('policy.afterfire_min_count',3);await fill('startup.stopping_seconds',.6);await page.fill('#name','浏览器整车配方 · 第二版');await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#versions option').length===2);
  const latest=await page.inputValue('#versions');assert.notEqual(latest,version);
  await page.selectOption('#versions',version);await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#name').value==='浏览器整车配方 · 功能测试');
  assert.equal((await download('historical')).href,first.href);
  // Alter only an owned fixture. Published coefficients/preset must stay intact.
  const eventPath=path.join(out,'projects','events',c.system.events.projects.catch,'project.json');
  const original=fs.readFileSync(eventPath),event=JSON.parse(original);event.name='事件来源已编辑';fs.writeFileSync(eventPath,JSON.stringify(event));
  await page.reload();await ready();assert((await page.textContent('#sourceStatus')).includes('1 个事件来源已更改'));
  fs.writeFileSync(eventPath,original);
  for(const s of await page.locator('#systemFields summary').all())await s.click();
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1440,height:1080});await page.click('#new');assert(!await page.isChecked('#includeSystem'));
  assert(await page.locator(field('startup.flare_rpm')).isDisabled());await page.selectOption('[data-group=base] select',c.groups.base[0]);
  await page.fill('#name','旧 DNA 单独配方');await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#downloads a').length===2);
  const plain=await page.inputValue('#recipes');assert.notEqual(plain,id);
  await page.selectOption('#recipes',id);await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#downloads a').length===3);
  assert(await page.isChecked('#includeSystem'));assert.equal(await page.inputValue('#versions'),latest);
  assert.equal(driverCalls,0);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',id,version,latest,
   full_preset_export:true,reload_exact:true,invalid_preserves_export:true,immutable_history:true,
   event_drift_warning:true,dna_only_export:true,switch_restores_system:true,desktop_mobile:true,
   no_autoplay:true,driver_not_launched:true,browser_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack||e));process.exitCode=1;});
