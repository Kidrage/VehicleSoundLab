// Full public UI workflow with actual C-generated audio; automated playback muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const out=process.argv[3],fixture=process.argv[4];fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const errors=[];let report={result:'running'};
try{const page=await browser.newPage({viewport:{width:1400,height:1050}});page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{HTMLMediaElement.prototype.play=function(){this.muted=true;return Promise.resolve();};});
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
 await page.locator('#audioFile').setInputFiles(fixture);
 await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('2.00s')&&!document.querySelector('#analyze').disabled,{},{timeout:30000});
 await page.fill('#root','47');await page.fill('#start','.1');await page.fill('#end','1.9');
 await page.click('#analyze');await page.waitForFunction(()=>document.querySelector('#sourceInfo').textContent.includes('1.80s')&&!document.querySelector('#analyze').disabled,{},{timeout:30000});
 await page.fill('#harmonics','128');await page.click('#compile');
 await page.waitForFunction(()=>document.querySelector('#modelInfo').textContent.includes('128阶')&&!document.querySelector('#compile').disabled,{},{timeout:90000});
 await page.click('[data-recipe=bright]');assert.equal(await page.inputValue('#high_db'),'3');
 await page.fill('#seconds','.5');await page.click('#render');
 await page.waitForFunction(()=>document.querySelector('#preview').getAttribute('src')&&document.querySelector('#renderInfo').textContent.includes('峰值')&&!document.querySelector('#render').disabled,{},{timeout:90000});
 await page.locator('#preview').evaluate(a=>{a.muted=true;});
 await page.waitForFunction(()=>document.querySelector('#preview').readyState>=1&&document.querySelector('#preview').duration===.5);
 await page.click('#advanced summary');await page.click('#loadJson');
 await page.waitForFunction(()=>document.querySelector('#jsonEditor').value.includes('base_profile'));
 const pkg=JSON.parse(await page.inputValue('#jsonEditor'));assert(pkg.base_profile.basis.length===128);
 await page.click('#advanced summary');
 await page.fill('#name','UI saved voice');await page.click('#save');
 await page.waitForFunction(()=>!document.querySelector('#save').disabled&&document.querySelector('#projectLabel').textContent==='UI saved voice');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#name').value==='UI saved voice');
 assert.equal(await page.inputValue('#high_db'),'3');
 await page.waitForFunction(()=>document.querySelector('#projects').options.length>1);
 assert(await page.locator('#projects option').count()>1);
 assert((await page.locator('#renderInfo').innerText()).includes('上次生成'));
 await page.locator('#toneControls').scrollIntoViewIfNeeded();
 const transport=await page.locator('.transport').boundingBox();assert(transport.y>=0&&transport.y<100);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);
 report={result:'passed',page_errors:errors,real_upload_analysis_compile_C_preview:true,preset_switch:true,
   editable_macros:true,complete_JSON_available:true,downloads:3,preview_seconds:.5,mobile_no_horizontal_overflow:true,
   save_and_reload:true,recent_projects:true,sticky_preview:true,
   automated_audio_muted:true};
}catch(e){report={result:'failed',error:String(e),page_errors:errors};throw e;}
finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(report);
})().catch(e=>{console.error(e);process.exit(1);});
