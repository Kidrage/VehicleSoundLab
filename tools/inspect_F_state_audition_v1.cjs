// Actual Chrome metadata/transport inspection; automated playback stays muted.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const {chromium}=require(process.argv[2]+'/playwright');
const folder=path.resolve(process.argv[3]),out=path.join(folder,'browser1');
fs.mkdirSync(out,{recursive:false});
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const report={schema:'vsl.F-state-audition-browser/1',result:'running',automated_audio_muted:true,clips:[]};
(async()=>{let browser;try{
 const source=JSON.parse(fs.readFileSync(path.join(folder,'report.json'),'utf8'));
 const url='http://127.0.0.1:8789/references/analysis/F_state_audition_v1/review1/index.html';
 browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1000,height:900}}),errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 const response=await page.goto(url);assert.equal(response.status(),200);
 assert.equal(await page.locator('audio').count(),1);
 assert.equal(await page.locator('#choice').inputValue(),'F2_tailpipe.wav');
 assert.equal(await page.locator('#player').evaluate(a=>a.volume),.5);
 await page.locator('#player').evaluate(a=>{a.muted=true;});
 for(const clip of source.clips){
  await page.selectOption('#choice',clip.file);
  await page.waitForFunction(file=>{const a=document.getElementById('player');return a.currentSrc.endsWith('/'+file)&&a.readyState>=1&&!a.error;},clip.file);
  const state=await page.locator('#player').evaluate(a=>({duration:a.duration,paused:a.paused,volume:a.volume,muted:a.muted}));
  assert(Math.abs(state.duration-clip.frames/48000)<1/48000);
  assert(state.paused&&state.volume===.5&&state.muted);
  await page.locator('#player').evaluate(async a=>{await a.play();});
  await page.waitForFunction(()=>document.getElementById('player').currentTime>.08);
  await page.locator('#player').evaluate(a=>a.pause());
  report.clips.push({file:clip.file,...state,muted_transport_advances:true});
 }
 await page.selectOption('#choice','F2_tailpipe.wav');
 await page.waitForFunction(()=>document.getElementById('player').readyState>=1);
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
 assert.equal(errors.length,0);
 fs.copyFileSync(__filename,path.join(out,'executed_source.cjs'));
 report.result='all7_native_float_clips_decode_and_single_player_transport_verified_muted';
 report.source_report_sha256=hash(path.join(folder,'report.json'));
 report.html_sha256=hash(path.join(folder,'index.html'));
 report.executed_source_sha256=hash(__filename);
 report.desktop_sha256=hash(path.join(out,'desktop.png'));
 report.mobile_sha256=hash(path.join(out,'mobile.png'));
 report.audio_quality_accepted=false;
 console.log(JSON.stringify({result:report.result,clips:report.clips.length}));
 }catch(error){report.result='failed';report.error=String(error);throw error;}
 finally{if(browser)await browser.close();fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');}
})().catch(()=>{process.exitCode=1;});
