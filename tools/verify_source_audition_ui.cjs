// Real browser metadata/control/playback checks. Automated audio remains muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'renders/source_audition_v1');
const file=path.join(root,'research/声源分层试听V1.html');
const url='http://127.0.0.1:8789/research/'+encodeURIComponent('声源分层试听V1.html');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{const create=document.createElement.bind(document);document.createElement=function(name,...args){const element=create(name,...args);if(name.toLowerCase()==='audio')element.muted=true;return element;};});
  await page.goto(url);
  await page.locator('#player').evaluate(a=>{a.muted=true;});
  await page.locator('audio[data-reference]').evaluateAll(xs=>xs.forEach(x=>{x.muted=true;}));
  async function ready(){
   await page.waitForFunction(()=>{
    const a=document.getElementById('player'),source=new URL(selectedSource(),location.href).href;
    return active.ready&&a.readyState>=1&&a.dataset.source===source&&Number.isFinite(a.duration)&&!a.error;
   },{},{timeout:15000});
   assert.equal(await page.locator('#player').evaluate(a=>a.muted),true);
   assert.equal(await page.locator('[data-view][aria-pressed="true"]').count(),1);
  }
  await ready();
  const scenes=await page.locator('#scene option').evaluateAll(xs=>xs.map(x=>x.value));
  const recipes=await page.locator('#recipe option').evaluateAll(xs=>xs.map(x=>x.value));
  const groups=await page.locator('#group option').evaluateAll(xs=>xs.map(x=>x.value));
  let loads=0,boosts=0;
  for(const scene of scenes){
   await page.selectOption('#scene',scene);
   for(const recipe of recipes){
    await page.selectOption('#recipe',recipe);
    await page.click('[data-view=full]');await ready();loads++;
    for(const group of groups){
     await page.selectOption('#group',group);
     for(const view of ['solo','without']){await page.click(`[data-view=${view}]`);await ready();loads++;}
    }
    await page.selectOption('#group','mechanical');await page.click('[data-view=solo]');await ready();
    await page.check('#boost');await ready();boosts++;
    assert((await page.locator('#player').evaluate(a=>a.dataset.source)).endsWith('_mechanical_plus24.wav'));
    assert((await page.locator('#boostNote').textContent()).includes('+24 dB'));
    await page.click('[data-view=without]');await ready();
    assert.equal(await page.isChecked('#boost'),false);assert.equal(await page.isDisabled('#boost'),true);
    await page.click('[data-view=solo]');await ready();await page.check('#boost');await ready();
    await page.click('[data-view=full]');await ready();assert.equal(await page.isChecked('#boost'),false);
   }
  }
  await page.selectOption('#scene','mid');await page.selectOption('#recipe','base');
  await page.selectOption('#group','exhaust');await page.click('[data-view=full]');await ready();
  await page.locator('#player').evaluate(a=>{a.currentTime=1.25;});
  await page.click('[data-view=solo]');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-1.25)<.03);
  await page.selectOption('#recipe','combined');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-1.25)<.03);
  await page.selectOption('#group','body');await ready();
  assert(Math.abs(await page.locator('#player').evaluate(a=>a.currentTime)-1.25)<.03);
  await page.locator('#player').evaluate(a=>{a.currentTime=.5;});await page.click('#transport');
  await page.waitForFunction(()=>document.getElementById('player').currentTime>.55);
  assert.equal(await page.locator('#transport').textContent(),'暂停');
  await page.click('[data-view=without]');await ready();
  await page.waitForFunction(()=>!document.getElementById('player').paused);
  assert(await page.locator('#player').evaluate(a=>a.currentTime)>.5);
  // Delay an obsolete response while newer requests replace it. No stale seek/play.
  await page.route('**/audition_mid_combined_solo_intake.wav',async route=>{
   await new Promise(resolve=>setTimeout(resolve,300));await route.continue().catch(()=>{});
  });
  await page.evaluate(()=>{
   document.querySelector('[data-view=solo]').click();
   group.value='intake';group.dispatchEvent(new Event('change'));
   group.value='air';group.dispatchEvent(new Event('change'));
   recipe.value='base';recipe.dispatchEvent(new Event('change'));
   group.value='mechanical';group.dispatchEvent(new Event('change'));
   recipe.value='combined';recipe.dispatchEvent(new Event('change'));
  });
  await ready();await page.waitForFunction(()=>!document.getElementById('player').paused);
  assert((await page.locator('#player').evaluate(a=>a.dataset.source)).endsWith('audition_mid_combined_solo_mechanical.wav'));
  await page.locator('#player').evaluate(a=>a.pause());
  assert.equal(await page.locator('#transport').textContent(),'播放');
  assert.equal(await page.locator('#playerHost audio').count(),1);
  await page.unrouteAll({behavior:'wait'});
  // Leaving mechanical solo/group/scene clears auxiliary gain.
  await page.check('#boost');await ready();await page.selectOption('#group','body');await ready();
  assert.equal(await page.isChecked('#boost'),false);
  await page.selectOption('#group','mechanical');await ready();await page.check('#boost');await ready();
  await page.selectOption('#scene','high');await ready();assert.equal(await page.isChecked('#boost'),false);
  assert(await page.locator('#player').evaluate(a=>a.paused&&a.currentTime<.01));
  // Manual reference and synthetic playback exclude one another.
  for(const name of ['low','blips']){
   const ref=page.locator(`audio[data-reference=${name}]`);
   await ref.evaluate(a=>a.load());
   await page.waitForFunction(name=>{const a=document.querySelector(`audio[data-reference=${name}]`);return a.readyState>=1&&Number.isFinite(a.duration)&&!a.error;},name);
   await page.locator('#player').evaluate(async a=>{a.currentTime=0;await a.play();});
   await ref.evaluate(async a=>{a.currentTime=0;await a.play();});
   assert(await page.locator('#player').evaluate(a=>a.paused));
   await page.locator('#player').evaluate(async a=>{await a.play();});
   assert(await ref.evaluate(a=>a.paused));await page.locator('#player').evaluate(a=>a.pause());
  }
  await page.selectOption('#scene','high');await page.selectOption('#group','mechanical');
  await page.click('[data-view=solo]');await ready();
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(out,'listening_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'listening_mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  // Portable file: entry also loads metadata and actually plays muted.
  await page.goto(pathToFileURL(file).href);await page.locator('#player').evaluate(a=>{a.muted=true;});await ready();
  await page.locator('#player').evaluate(async a=>{await a.play();});
  await page.waitForFunction(()=>document.getElementById('player').currentTime>.05);
  await page.locator('#player').evaluate(a=>a.pause());
  assert.deepEqual(errors,[]);
  const report={result:'pass',scenes:scenes.length,recipes:recipes.length,groups:groups.length,
   normal_audio_metadata_loads:loads,boosted_mechanical_loads:boosts,reference_metadata_loads:2,
   position_preserved_on_view_recipe_group:true,actual_muted_playback_and_switch:true,
   obsolete_request_cannot_seek_or_play_current:true,boost_default_off_and_reset_on_full_remove_group_scene:true,
   scene_change_stops_and_restarts_position:true,reference_mutual_exclusion:true,
   http_and_file_entry_checked:true,mobile_horizontal_overflow:false,javascript_errors:errors,
   visible_transport_play_pause_checked:true,
   scope:'Headless Chrome metadata, real muted decoding/playback, controls and screenshots. No subjective sound evaluation, sample-accurate switching or physical speaker-array validation.'};
  fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));
  process.stdout.write(JSON.stringify(report,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
