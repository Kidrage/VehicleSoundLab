// Decode and play muted; this checks operation, not timbre quality.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'renders/observed_dna_v1');
const file=path.join(root,'research/录音DNA相位试听V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8789/research/'+encodeURIComponent('录音DNA相位试听V1.html'));
  await page.locator('#player').evaluate(a=>{a.muted=true;});
  async function ready(){await page.waitForFunction(()=>{const a=player.current.audio;return player.current.ready&&a.readyState>=1&&a.dataset.source===new URL(selectedSource(),location.href).href&&Number.isFinite(a.duration)&&!a.error;},{},{timeout:15000});assert(await page.locator('#player').evaluate(a=>a.muted));assert.equal(await page.locator('[data-method][aria-pressed=true]').count(),1);}
  await ready();let loads=0;
  for(const scene of ['first_early','first_late','second_early']){await page.selectOption('#case',scene);for(const method of ['fitted','common_flat']){await page.click(`[data-method=${method}]`);await ready();loads++;assert(Math.abs(await page.locator('#player').evaluate(a=>a.duration)-3)<.01);}}
  await page.click('[data-method=fitted]');await ready();await page.locator('#player').evaluate(a=>{a.currentTime=.75;});
  await page.click('[data-method=common_flat]');await ready();assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-.75)<.03);
  await page.click('#transport');await page.waitForFunction(()=>!player.current.audio.paused&&player.current.audio.currentTime>.80);
  await page.click('[data-method=fitted]');await ready();await page.waitForFunction(()=>!player.current.audio.paused);
  await page.locator('details').first().evaluate(e=>{e.open=true;});await page.locator('#reference').evaluate(async a=>{a.muted=true;await a.play();});
  await page.waitForFunction(()=>player.current.audio.paused&&!document.getElementById('reference').paused);
  await page.click('#transport');await page.waitForFunction(()=>!player.current.audio.paused&&document.getElementById('reference').paused);
  await page.selectOption('#case','first_early');await ready();assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.01));
  await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('details').nth(1).evaluate(e=>{e.open=true;});await page.waitForFunction(()=>document.querySelector('img').complete&&document.querySelector('img').naturalWidth>0);
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>{a.muted=true;});await ready();
  await page.click('#transport');await page.waitForFunction(()=>player.current.audio.currentTime>.05);await page.click('#transport');
  assert.deepEqual(errors,[]);
  const report={result:'pass',cases:3,methods:2,audio_metadata_loads:loads,actual_muted_playback:true,
   position_and_playing_state_preserved:true,case_change_stops_at_zero:true,reference_exclusive_playback:true,
   http_and_file_entry:true,figure_loaded:true,mobile_horizontal_overflow:false,javascript_errors:errors,
   scope:'Actual headless Chrome metadata, muted decoding/playback, seek/control switching and screenshots. No subjective acceptance or physical-array listening.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));process.stdout.write(JSON.stringify(report,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
