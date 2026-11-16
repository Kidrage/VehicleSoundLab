// Full public UI workflow with actual C-generated audio; automated playback muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const out=process.argv[3],fixture=process.argv[4];fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const errors=[];let report={result:'running'};
try{const page=await browser.newPage({viewport:{width:1400,height:1050}});page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.muted=true;return play.call(this);};});
 await page.goto('http://127.0.0.1:8791');
 await page.waitForFunction(()=>document.querySelector('#modelInfo').textContent.includes('300阶'));
 assert.equal(await page.locator('#harmonicRows tr').count(),300);
 await page.click('[data-preset=warm]');await page.waitForFunction(()=>document.querySelector('#name').value==='Warm Additive');
 await page.fill('#seconds','.25');await page.click('#render');
 await page.waitForFunction(()=>document.querySelector('#downloads a')&&document.querySelector('#render').disabled===false,{},{timeout:90000});
 await page.locator('#preview').evaluate(a=>{a.muted=true;});
 await page.waitForFunction(()=>document.querySelector('#preview').readyState>=1);
 assert.equal(await page.locator('#preview').evaluate(a=>a.duration),.25);
 assert.equal(await page.locator('#downloads a').count(),3);
 const warmAudio=await page.locator('#preview').getAttribute('src');
 await page.click('#pinA');
 await page.locator('#audioFile').setInputFiles(fixture);
 await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('2.00s')&&!document.querySelector('#analyze').disabled,{},{timeout:30000});
 await page.fill('#root','47');await page.fill('#start','.1');await page.fill('#end','1.9');
 await page.selectOption('#state','idle');await page.selectOption('#viewpoint','cabin');
 await page.click('#analyze');await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('1.80s')&&!document.querySelector('#analyze').disabled,{},{timeout:30000});
 assert.equal(await page.inputValue('#state'),'idle');assert.equal(await page.inputValue('#viewpoint'),'cabin');
 await page.fill('#harmonics','128');await page.click('#compile');
 await page.waitForFunction(()=>document.querySelector('#modelInfo').textContent.includes('128阶')&&!document.querySelector('#compile').disabled,{},{timeout:90000});
 await page.click('[data-recipe=bright]');assert.equal(await page.inputValue('#high_db'),'3');
 await page.fill('#seconds','.5');await page.click('#render');
 await page.waitForFunction(()=>document.querySelector('#preview').getAttribute('src')&&document.querySelector('#renderInfo').textContent.includes('峰值')&&!document.querySelector('#render').disabled,{},{timeout:90000});
 await page.locator('#preview').evaluate(a=>{a.muted=true;});
 await page.waitForFunction(()=>document.querySelector('#preview').readyState>=1&&document.querySelector('#preview').duration===.5);
 const currentAudio=await page.locator('#preview').getAttribute('src');
 await page.click('#listenA');
 assert.equal(await page.locator('#preview').getAttribute('src'),warmAudio);
 assert.equal(await page.locator('#listenA').getAttribute('aria-pressed'),'true');
 await page.click('#listenB');
 assert.equal(await page.locator('#preview').getAttribute('src'),currentAudio);
 await page.waitForFunction(()=>document.querySelector('#preview').readyState>=1);
 await page.locator('#preview').evaluate(a=>{a.loop=true;return a.play();});
 await page.locator('#reference').evaluate(a=>a.play());
 assert(await page.locator('#preview').evaluate(a=>a.paused));
 await page.locator('#preview').evaluate(a=>a.play());
 assert(await page.locator('#reference').evaluate(a=>a.paused));
 await page.locator('#preview').evaluate(a=>{a.pause();a.loop=false;});
 await page.click('#advanced summary');await page.click('#loadJson');
 await page.waitForFunction(()=>document.querySelector('#jsonEditor').value.includes('base_profile'));
 const pkg=JSON.parse(await page.inputValue('#jsonEditor'));assert(pkg.base_profile.basis.length===128);
 assert.equal(pkg.state,'idle');assert.equal(pkg.viewpoint,'cabin');
 await page.click('#advanced summary');
 await page.fill('#name','UI saved voice');await page.click('#save');
 await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#projectLabel').textContent==='UI saved voice');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#name').value==='UI saved voice');
 assert.equal(await page.inputValue('#high_db'),'3');
 await page.waitForFunction(()=>document.querySelector('#projects').options.length>1);
 assert(await page.locator('#projects option').count()>1);
 assert((await page.locator('#renderInfo').innerText()).includes('上次生成'));
 await page.waitForFunction(()=>document.querySelector('#historyList').options.length>2);
 await page.click('#historyPanel summary');
 const revision=await page.locator('#historyList option').evaluateAll(options=>options.find(o=>o.textContent.includes('生成试听')).value);
 await page.locator('#high_db').evaluate(input=>{input.value='6';input.dispatchEvent(new Event('input'));});
 await page.fill('#start','.3');await page.fill('#end','1.5');await page.click('#analyze');
 await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('1.20s')&&!document.querySelector('#analyze').disabled);
 assert.equal(await page.inputValue('#high_db'),'6');
 assert((await page.locator('#sourceBinding').innerText()).includes('上次提取'));
 await page.waitForFunction(revision=>Array.from(document.querySelector('#historyList').options).some(o=>o.value===revision),revision);
 await page.selectOption('#historyList',revision);
 await page.evaluate(async()=>{await window.DesignHistory.refresh({id:document.querySelector('#projects').value});});
 assert.equal(await page.inputValue('#historyList'),revision);
 await page.click('#restoreHistory');
 await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('1.80s')&&document.querySelector('#high_db').value==='3'&&!document.querySelector('#restoreHistory').disabled);
 assert((await page.locator('#sourceBinding').innerText()).includes('来源一致'));
 await page.click('#historyPanel summary');
 await page.locator('#toneControls').scrollIntoViewIfNeeded();
 const transport=await page.locator('.transport').boundingBox();assert(transport.y>=0&&transport.y<100);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.locator('#toneControls').scrollIntoViewIfNeeded();
 const mobileTransport=await page.locator('.transport').boundingBox();assert(mobileTransport.y>=0&&mobileTransport.y<100);
 await page.screenshot({path:path.join(out,'mobile-controls.png')});
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);
 report={result:'passed',page_errors:errors,real_upload_analysis_compile_C_preview:true,preset_switch:true,
   editable_macros:true,complete_JSON_available:true,downloads:3,preview_seconds:.5,mobile_no_horizontal_overflow:true,
   save_and_reload:true,recent_projects:true,sticky_preview:true,
   ab_uses_one_player_without_gain_change:true,reference_and_preview_mutually_exclusive:true,
   analyze_preserves_pending_edits:true,restore_history_restores_model_controls_and_selection:true,
   labels_survive_analysis_before_model_exists:true,
   automated_audio_muted:true};
}catch(e){report={result:'failed',error:String(e),page_errors:errors};throw e;}
finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(report);
})().catch(e=>{console.error(e);process.exit(1);});
