// Usage: node verify_pages.cjs <project root> <report folder> <chrome.exe>
// Set NODE_PATH to a directory containing playwright (or install it locally).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL, fileURLToPath } = require('node:url');
const { chromium } = require('playwright');
const [rootArg, outputArg, chrome] = process.argv.slice(2);
if (!rootArg || !outputArg) throw new Error('Project and report paths are required');
const root = path.resolve(rootArg), output = path.resolve(outputArg);
const url = (...parts) => pathToFileURL(path.join(root, ...parts)).href;
(async () => {
 const browser = await chromium.launch({ executablePath:chrome, args:['--mute-audio'] });
 const page = await browser.newPage({ viewport:{width:1320,height:984} });
 const errors = [];
 page.on('pageerror', e => errors.push(String(e)));
 fs.mkdirSync(output, { recursive:true });
 try {
  await page.goto(url('handoff','系统总图.svg'));
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.locator('text').evaluateAll(els => els.map(t => {
   const b=t.getBBox(); return [t.textContent,b.x,b.y,b.x+b.width,b.y+b.height];
  }));
  assert(geometry.every(([,x,y,r,b]) => x>=0&&y>=0&&r<=1320&&b<=984), 'diagram text out of bounds');
  await page.screenshot({path:path.join(output,'系统总图.png')});
  const layouts = [];
  for (const width of [1320,390]) {
   await page.setViewportSize({width,height:984});
   await page.goto(url('handoff','index.html'));
   assert(await page.locator('figure img').evaluate(img => img.complete && img.naturalWidth>0));
   assert(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth));
   const links = await page.locator('a').evaluateAll(els => els.map(e => e.href));
   for (const link of links) assert(fs.existsSync(fileURLToPath(link)),link);
   await page.screenshot({path:path.join(output,'index-'+width+'.png'),fullPage:true});
   layouts.push({width,localLinks:links.length});
  }
  const audioChecks=[];
  async function audio(caseName) {
   await page.waitForFunction(() => {
    const a=document.getElementById('player');
    return a && a.readyState>=1 && !a.error && Number.isFinite(a.duration) && a.duration>0;
   }, null, {timeout:6000});
   const state = await page.locator('#player').evaluate(a=>({source:a.dataset.source,duration:a.duration}));
   audioChecks.push({case:caseName, file:path.relative(root,fileURLToPath(state.source)), seconds:state.duration});
  }
  for (const file of ['OSC完整度对照V2.html','持续OSC细节与低频V1.html','低频轰鸣V2.html']) {
   await page.goto(url('research',file));
   for (const summary of await page.locator('details:not([open]) > summary').all()) await summary.click();
   const methods=await page.locator('[data-method]').evaluateAll(els=>els.map(e=>e.dataset.method));
   const profiles=await page.locator('[data-profile]').evaluateAll(els=>els.map(e=>e.dataset.profile));
   for (const profile of profiles.length ? profiles : ['default']) {
    if (profile!=='default') {
     await page.locator('[data-profile='+JSON.stringify(profile)+']').click();
     await audio(file+' '+profile+' initial');
    }
    for (const method of methods) {
     await page.locator('[data-method='+JSON.stringify(method)+']').click();
     await audio(file+' '+profile+' '+method);
    }
   }
   await page.locator('#transport').click();
   await page.waitForFunction(()=>document.getElementById('player').currentTime>.05, null, {timeout:4000});
   await page.locator('#transport').click();
   assert.equal(await page.locator('#player').evaluate(a=>a.paused),true);
  }
  assert.deepEqual(errors,[]);
  const report={browser:browser.version(),mode:'offline file URLs; audio muted',layouts,diagramText:geometry.length,audioChecks,pageErrors:errors};
  fs.writeFileSync(path.join(output,'offline-pages.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({layouts,diagramText:geometry.length,audioChecks:audioChecks.length,errors}));
 } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});

