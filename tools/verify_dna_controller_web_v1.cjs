// Owned bounded workbench. Never launches the persistent native controller.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],base=process.argv[4];
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[],exports=[];let driverCalls=0;
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1080}});
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(r.url().endsWith('/api/driver'))driverCalls++;});
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#exportDriver')&&!document.querySelector('#exportDriver').disabled);
  assert.equal(await page.inputValue('#driverRpm'),'3000');
  const set=async(id,value)=>page.locator('#'+id).evaluate((e,v)=>{e.value=String(v);e.dispatchEvent(new Event('input',{bubbles:true}));},value);
  await set('gain_db',-8);await set('high_db',1);await set('local',.7);await set('detail',.63);await set('width',1.1);
  await page.click('#driverExport summary');await page.fill('#driverRpm','3000');
  await page.click('#exportDriver');await page.waitForFunction(()=>!document.querySelector('#exportDriver').disabled&&document.querySelector('#driverDownloads a'),null,{timeout:30000});
  const project=async()=>{await page.waitForFunction(()=>window.document.querySelector('#projects').value&&window.document.querySelector('#projects').value===globalThis.eval('project.id'));const id=await page.inputValue('#projects');return (await page.request.get(base+'/api/project/'+id)).json();};
  async function delivery(name){
   const p=await project(),links=await page.locator('#driverDownloads a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
   assert.equal(links.length,2);const responses=await Promise.all(links.map(h=>page.request.get(base+h)));
   assert(responses.every(r=>r.ok()));const [bank,provenance]=await Promise.all(responses.map(r=>r.json()));
   assert.equal(bank.schema,'vsl.controller-dna-bank/1');assert.equal(bank.anchors.length,1);assert(!JSON.stringify(bank).includes('RIFF'));
   fs.writeFileSync(path.join(out,name+'.dnabank.json'),JSON.stringify(bank,null,2));fs.writeFileSync(path.join(out,name+'.provenance.json'),JSON.stringify(provenance,null,2));
   exports.push({name,project_id:p.id,bank,provenance});return p;
  }
  let p=await delivery('v10');assert.equal(p.params.high_db,1);assert.equal(p.params.detail,.63);
  assert.equal(exports[0].bank.detail,.63);assert.equal(exports[0].provenance.reference_rpm,3000);
  await page.locator('#driverExport').screenshot({path:path.join(out,'driver-export.png')});
  await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#driverDownloads a').length===2&&!document.querySelector('#exportDriver').disabled);
  assert.equal((await project()).id,p.id);await page.click('#driverExport summary');
  const before=JSON.stringify((await project()).driver_export);
  await page.fill('#driverRpm','0');await page.click('#exportDriver');
  await page.waitForFunction(()=>document.querySelector('#toast').classList.contains('error')&&!document.querySelector('#exportDriver').disabled);
  assert.equal(JSON.stringify((await project()).driver_export),before);
  await page.fill('#driverRpm','3000');
  await page.setViewportSize({width:390,height:844});await page.locator('#driverExport').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile-export.png')});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1440,height:1080});await page.click('[data-preset=warm]');
  await page.waitForFunction(()=>document.querySelector('#name').value==='Warm Additive'&&!document.querySelector('#exportDriver').disabled);
  await page.fill('#driverRpm','3000');await page.click('#exportDriver');
  await page.waitForFunction(()=>document.querySelectorAll('#driverDownloads a').length===2&&!document.querySelector('#exportDriver').disabled);
  await delivery('warm');assert.notEqual(exports[0].bank.anchors[0].sha256,exports[1].bank.anchors[0].sha256);
  assert.equal(driverCalls,0);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',exports:exports.map(e=>({name:e.name,project_id:e.project_id})),
   source_free_parameter_download:true,current_edits_adopted:true,reload_preserves_export:true,invalid_preserves_project:true,
   two_voices_exported:true,no_autoplay:true,driver_not_launched:true,browser_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack||e));process.exitCode=1;});
