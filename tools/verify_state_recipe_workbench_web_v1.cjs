// Bounded owned browser: author, download and reopen source-free state recipes.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const out=process.argv[3],base=process.argv[4],ids=JSON.parse(fs.readFileSync(process.argv[5]));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 let driverCalls=0;const errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1080}});
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(r.url().endsWith('/api/driver'))driverCalls++;});
  await page.goto(base+'/vehicles.html');await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('[data-group=base] select'));
  await page.fill('#name','浏览器四状态示例');await page.selectOption('[data-group=base] select',ids.base_low);
  for(const [group,id]of [['idle',ids.idle],['power',ids.power],['overrun',ids.overrun]]){
   await page.click(`[data-group=${group}] .add`);await page.selectOption(`[data-group=${group}] select`,id);
  }
  await page.fill('#rpm','3000');await page.fill('#detail','72');await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#downloads a').length===2);
  assert(!await page.locator('#status').evaluate(e=>e.classList.contains('error')));
  const id=await page.inputValue('#recipes'),version=await page.inputValue('#versions');assert(id&&version);
  const download=async(name)=>{const href=await page.locator('#downloads a').first().getAttribute('href');const response=await page.request.get(base+href);assert(response.ok());const bank=await response.json();fs.writeFileSync(path.join(out,name+'.dnabank.json'),JSON.stringify(bank,null,2));return {bank,href};};
  const first=await download('browser');assert.equal(first.bank.schema,'vsl.controller-dna-bank/2');assert.equal(first.bank.detail,.72);assert.equal(Object.keys(first.bank.states).length,3);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#downloads a').length===2);
  assert.equal(await page.inputValue('#recipes'),id);assert.equal((await download('reloaded')).href,first.href);
  await page.fill('#rpm','0');await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#status').classList.contains('error'));
  assert.equal((await download('after-invalid')).href,first.href);await page.fill('#rpm','3000');
  await page.fill('#name','浏览器第二版本');await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelectorAll('#versions option').length===2);
  const latest=await page.inputValue('#versions');assert.notEqual(latest,version);
  await page.selectOption('#versions',version);await page.waitForFunction(v=>!document.querySelector('#save').disabled&&document.querySelector('#name').value==='浏览器四状态示例',null);
  assert.equal((await download('historical')).href,first.href);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1440,height:1080});await page.click('#new');await page.selectOption('[data-group=base] select',ids.base_high);await page.fill('#name','另一辆设计示例');await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#recipes').value);
  const other=await page.inputValue('#recipes');assert.notEqual(other,id);
  await page.selectOption('#recipes',id);await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#name').value==='浏览器第二版本');
  assert.equal(await page.inputValue('#recipes'),id);
  // Main workbench entry is visible and the expanded navigation still fits.
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#name').value&&document.querySelector('#name').value!=='未命名音色');
  assert.equal(await page.locator('a[href="/vehicles.html"]').count(),1);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'main-mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.equal(driverCalls,0);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'passed',id,version,latest,
   four_state_export:true,reload_exact:true,invalid_preserves_export:true,immutable_history:true,
   switch_between_recipes:true,desktop_mobile:true,no_autoplay:true,driver_not_launched:true,browser_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack||e));process.exitCode=1;});
