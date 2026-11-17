const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const url=process.argv[3],out=process.argv[4];fs.mkdirSync(out,{recursive:false});
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--mute-audio']});
 const report={result:'running',timbre_accepted:false},errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1200,height:1000},acceptDownloads:true});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);assert.equal(await page.locator('audio').count(),1);
  const rows=await page.evaluate(()=>tracks);assert.equal(rows.length,8);report.decoded=[];
  const select=async index=>{
   const previous=await page.locator('audio').evaluate(a=>a.currentSrc);
   await page.click('[data-track="'+index+'"]');
   await page.waitForFunction(p=>{const a=document.querySelector('audio');return a.currentSrc!==p&&a.readyState>=2&&!a.seeking;},previous);
   assert.equal(await page.locator('[aria-pressed=true]').count(),1);
  };
  for(const [index,row] of rows.entries()){
   const response=await page.request.get(new URL(row.file,url).href);assert.equal(response.status(),200);assert.equal(hash(await response.body()),row.sha256);
   const decoded=await page.evaluate(async file=>{
    const c=new AudioContext();try{const a=await c.decodeAudioData(await(await fetch(file)).arrayBuffer());return{frames:a.length,channels:a.numberOfChannels,rate:a.sampleRate};}finally{await c.close();}
   },row.file);
   assert.equal(decoded.channels,row.channels);assert(Math.abs(decoded.frames/decoded.rate-row.frames/48000)<1/decoded.rate);
   await select(index);await page.locator('audio').evaluate(a=>a.currentTime=.1);
   await page.waitForFunction(()=>{const a=document.querySelector('audio');return !a.seeking&&Math.abs(a.currentTime-.1)<.01;});
   report.decoded.push({file:row.file,...decoded});
  }
  await select(0);await page.locator('audio').evaluate(async a=>{a.currentTime=.3;await a.play();});
  await select(1);assert(await page.locator('audio').evaluate(a=>!a.paused&&a.currentTime>=.3));
  await page.locator('audio').evaluate(a=>a.pause());
  for(const href of await page.locator('a').evaluateAll(a=>a.map(x=>x.href)))assert.equal((await page.request.get(href)).status(),200);
  const download=page.waitForEvent('download');await page.click('a[href="report.json"]');
  await(await download).saveAs(path.join(out,'report-download.json'));
  assert.equal(hash(fs.readFileSync(path.join(out,'report-download.json'))),hash(await(await page.request.get(new URL('report.json',url).href)).body()));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  Object.assign(report,{result:'passed',eight_track_hash_decode_seek:true,one_player:true,playing_switch:true,all_links_and_download:true,desktop_mobile:true,audio_muted:true});
 }catch(e){report.result='failed';report.error=String(e);throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
