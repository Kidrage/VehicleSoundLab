// Only an owned local server and browser profile; no persistent App launch.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const [base,out]=process.argv.slice(3);
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--mute-audio']});
 const errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(base);await page.getByRole('button',{name:'打开 Vehicle Sound App ↗'}).waitFor();
  await page.screenshot({path:path.join(out,'home.png'),fullPage:true});
  await page.getByRole('link',{name:/02.*组合车辆配方/}).click();
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('[data-group=base] select'));
  await page.selectOption('[data-group=base] select','00000000000000000000000000000001');
  await page.check('#includeSystem');await page.locator('#systemFields summary').first().click();
  const field=key=>`[data-system-field="dna.${key}"]`;
  await page.fill(field('line'),'.81');await page.fill(field('air'),'1.13');await page.fill(field('air_state.5'),'1.25');
  await page.fill('#name','统一 DNA 配方 · 浏览器验证');await page.click('#save');
  await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#downloads a[href$="vehicle.preset.json"]'));
  const href=await page.getByRole('link',{name:'下载整车参数',exact:true}).getAttribute('href');
  const response=await page.request.get(base+href);assert(response.ok());const preset=await response.json();
  assert.equal(preset.schema,'vsl.source-controller-preset/9');assert.equal(preset.control.dna.line,.81);assert.equal(preset.control.dna.air,1.13);assert.equal(preset.control.dna.air_state[5],1.25);
  fs.writeFileSync(path.join(out,'browser.preset.json'),JSON.stringify(preset,null,2));
  await page.locator('#systemPanel').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'recipe.png'),fullPage:true});
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#recipes').value);
  assert.equal(await page.inputValue(field('line')),'0.81');assert.equal(await page.inputValue(field('air_state.5')),'1.25');
  await page.setViewportSize({width:420,height:900});await page.goto(base);await page.screenshot({path:path.join(out,'home-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.setViewportSize({width:1440,height:900});await page.goto('file:///E:/VehicleSoundLab-Git/handoff/统一系统主线.svg');
  await page.screenshot({path:path.join(out,'diagram.png')});assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify({passed:true,preset_roundtrip:true,portal_navigation:true,mobile_portal:true,no_page_errors:true,manual_mouse_verified:false},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
