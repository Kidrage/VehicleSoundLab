// Muted functional QA of this project's generated comparison page.
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const {pathToFileURL}=require('url');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const workspace=path.resolve(process.argv[3]),out=path.join(workspace,'references/analysis/residual_osc_v1/review');
const review=JSON.parse(fs.readFileSync(path.join(out,'review.json'),'utf8'));
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('谐波间残差OSC_V1.html'));
  assert(await page.locator('audio').evaluateAll(list=>list.every(a=>a.paused&&!a.autoplay)));
  await page.locator('audio').evaluateAll(list=>list.forEach(a=>{a.muted=true;a.load();}));
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.readyState>=1&&!a.error&&Number.isFinite(a.duration)),{},{timeout:30000});
  const durations=await page.locator('audio').evaluateAll(list=>list.map(a=>a.duration));
  assert.equal(durations.length,review.records.length);
  durations.forEach((d,i)=>assert(Math.abs(d-review.records[i].frames/48000)<1e-6));
  await page.locator('audio').nth(1).evaluate(a=>a.play());
  await page.waitForFunction(()=>!document.querySelectorAll('audio')[1].paused);
  await page.locator('audio').nth(3).evaluate(a=>a.play());
  assert(await page.locator('audio').nth(1).evaluate(a=>a.paused));
  await page.locator('#stop').click();
  assert(await page.locator('audio').evaluateAll(list=>list.every(a=>a.paused)));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  await page.goto(pathToFileURL(review.page).href);
  await page.locator('audio').evaluateAll(list=>list.forEach(a=>{a.muted=true;a.load();}));
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.readyState>=1&&!a.error),{},{timeout:30000});
  assert.deepEqual(errors,[]);
  const result={result:'pass',muted:true,players:durations.length,durations,no_autoplay:true,stop_all:true,
    http_and_file:true,one_player_at_a_time:true,narrow_viewport:true,page_sha256:sha(review.page),verifier_sha256:sha(__filename),errors};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
