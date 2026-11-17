const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
(async()=>{
 const out=process.argv[3],url=process.argv[4],browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const errors=[],report={result:'running'};let page;
 try{
  page=await browser.newPage({viewport:{width:1280,height:960}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);assert.equal(await page.locator('audio').count(),1);
  await page.waitForFunction(()=>document.querySelector('audio').readyState>=1);
  assert(Math.abs(await page.locator('audio').evaluate(a=>a.duration)-9)<.001);
  for(const image of await page.locator('img').all())assert(await image.evaluate(i=>i.complete&&i.naturalWidth>0));
  assert(await page.locator('audio').evaluate(a=>a.paused&&!a.autoplay));
  await page.locator('#clip').selectOption({index:1});await page.waitForFunction(()=>document.querySelector('audio').readyState>=1&&document.querySelector('audio').duration<1);
  assert(Math.abs(await page.locator('audio').evaluate(a=>a.duration)-.71)<.001);
  assert(await page.locator('audio').evaluate(a=>a.paused));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',original_and_context_audio_HTTP_ok:true,images_loaded:true,one_player_no_autoplay:true,desktop_mobile_checked:true});
 }catch(e){report.result='failed';report.error=String(e);throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
