// Actual local Web Audio and UI checks; the physical monitor remains muted.
const {chromium}=require(process.argv[2]+'/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),out=path.join(root,'renders/character_tuner_v1');
const url='http://127.0.0.1:8789/research/'+encodeURIComponent('燃烧与机械调参V1.html');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1000,height:1120},acceptDownloads:true}),errors=[];
    page.on('pageerror',error=>errors.push(String(error)));
    await page.goto(url);await page.waitForFunction(()=>window.characterTuner?.ready);
    await page.evaluate(()=>{characterTuner.audio.monitor.gain.value=0;});
    assert.equal(await page.evaluate(()=>characterTuner.audio.context.sampleRate),48000);
    const cases=await page.locator('#case option').evaluateAll(xs=>xs.map(x=>x.value)),mixChecks=[];
    for(const id of cases){
      await page.selectOption('#case',id);
      await page.waitForFunction(id=>characterTuner.ready&&characterTuner.state().case===id,id);
      const shape=await page.evaluate(()=>characterTuner.audio.buffers.map(b=>({frames:b.length,channels:b.numberOfChannels,rate:b.sampleRate})));
      assert.equal(new Set(shape.map(x=>x.frames)).size,1);assert(shape.every(x=>x.channels===2&&x.rate===48000));
      assert(await page.evaluate(()=>{
        const a=characterTuner.audio,[lo,hi]=a.region;
        return a.loopBuffers.every((b,i)=>[0,1].every(c=>{
          const x=b.getChannelData(c),raw=a.buffers[i].getChannelData(c);
          return x[0]===0&&x[x.length-1]===0&&x[1000]===raw[lo+1000]&&x.length===hi-lo;
        }));
      }));
    }
    for(const id of ['mid','high','drive']){
      await page.selectOption('#case',id);await page.waitForFunction(id=>characterTuner.ready&&characterTuner.state().case===id,id);
      const checks=await page.evaluate(async()=>{
        const tuner=characterTuner,result=[];
        for(const [pressure,structure]of [[0,0],[1,0],[0,1],[.317,.731],[1,1],[.65,.65]]){
          tuner.set({pressure,structure,baseline:false,volume:.8});const actual=await tuner.offline();let maxError=0,difference=0;
          const gain=tuner.audio.fixedGain*.8;
          for(let c=0;c<2;c++){
            const a=actual.getChannelData(c),[b,p,s]=tuner.audio.buffers.map(x=>x.getChannelData(c));
            for(let i=0;i<a.length;i++)maxError=Math.max(maxError,Math.abs(a[i]-(b[i]+pressure*p[i]+structure*s[i])*gain));
          }
          const l=actual.getChannelData(0),r=actual.getChannelData(1);for(let i=0;i<l.length;i++)difference+=Math.abs(l[i]-r[i]);
          result.push({pressure,structure,maxError,stereoDifference:difference,frames:actual.length});
        }
        return result;
      });
      assert(checks.every(x=>x.maxError<2e-7&&x.stereoDifference>1));mixChecks.push({case:id,checks});
    }
    await page.selectOption('#case','high');await page.waitForFunction(()=>characterTuner.ready&&characterTuner.state().case==='high');
    for(const [id,value]of [['pressure',31],['structure',73],['volume',43]])await page.locator('#'+id).evaluate((e,value)=>{e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));},value);
    await page.locator('#pressure').focus();await page.keyboard.press('ArrowRight');
    let current=await page.evaluate(()=>characterTuner.settings);assert.equal(current.pressure,.32);assert.equal(current.structure,.73);assert.equal(current.volume,.43);
    await page.click('#play');await page.waitForFunction(()=>characterTuner.audio.running&&characterTuner.audio.position()>2400);
    let starts=await page.evaluate(()=>characterTuner.audio.lastStartTimes);assert.equal(new Set(starts).size,1);
    const before=await page.evaluate(()=>characterTuner.audio.position());await page.click('#compare');
    assert.equal(await page.evaluate(()=>characterTuner.settings.baseline),true);
    assert(await page.evaluate(()=>characterTuner.audio.position())>=before);assert.equal(await page.evaluate(()=>characterTuner.settings.pressure),.32);
    await page.click('#compare');assert.equal(await page.evaluate(()=>characterTuner.settings.baseline),false);
    await page.click('#play');assert.equal(await page.evaluate(()=>characterTuner.audio.running),false);
    await page.check('#loop');await page.evaluate(async()=>{await characterTuner.audio.seek(4.78*48000);});
    await page.click('#play');await page.waitForFunction(()=>characterTuner.audio.running&&characterTuner.audio.position()>2.51*48000&&characterTuner.audio.position()<3.0*48000);
    const loopBefore=await page.evaluate(()=>characterTuner.audio.position());await page.uncheck('#loop');
    const loopAfter=await page.evaluate(()=>characterTuner.audio.position());assert(Math.abs(loopAfter-loopBefore)<12000);
    await page.click('#play');assert.equal(await page.evaluate(()=>characterTuner.audio.running),false);
    await page.check('#loop');
    const saved=await page.evaluate(()=>characterTuner.state()),saveWait=page.waitForEvent('download');await page.click('#save');
    const save=await saveWait;await save.saveAs(path.join(out,'ui_settings.json'));
    const waveWait=page.waitForEvent('download');await page.click('#export');const wave=await waveWait;await wave.saveAs(path.join(out,'ui_export.wav'));
    await page.click('#compare');const baselineWait=page.waitForEvent('download');await page.click('#export');
    await (await baselineWait).saveAs(path.join(out,'ui_export_baseline.wav'));await page.click('#compare');
    await page.locator('#volume').evaluate(e=>{e.value=10;e.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.locator('#settings-file').setInputFiles(path.join(out,'ui_settings.json'));
    await page.waitForFunction(()=>characterTuner.ready&&characterTuner.settings.volume===.43);
    const loaded=await page.evaluate(()=>characterTuner.state());for(const k of ['case','pressure','structure','volume','loop','baseline'])assert.equal(loaded[k],saved[k]);
    const bad={...saved,pressure:2};await page.locator('#settings-file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(bad))});
    await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('未载入：'));
    assert.equal(await page.evaluate(()=>characterTuner.settings.pressure),saved.pressure);
    const offgrid={...saved,pressure:.317,structure:.731,volume:.437};
    await page.locator('#settings-file').setInputFiles({name:'offgrid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(offgrid))});
    await page.waitForFunction(()=>characterTuner.ready&&characterTuner.settings.pressure===.317);
    assert.equal(await page.locator('#pressure-value').textContent(),'31.7%');
    await page.locator('#volume').focus();await page.keyboard.press('ArrowRight');
    assert.equal(await page.evaluate(()=>characterTuner.settings.pressure),.317);assert.equal(await page.evaluate(()=>characterTuner.settings.structure),.731);
    // Asset corruption is rejected before decode, with transport stopped.
    await page.route('**/mid_pressure_delta.wav',async route=>{const response=await route.fetch(),body=await response.body();body[body.length-1]^=1;await route.fulfill({response,body});});
    await page.selectOption('#case','mid');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('校验失败'));
    assert.equal(await page.evaluate(()=>characterTuner.ready),false);assert.equal(await page.evaluate(()=>characterTuner.audio.running),false);
    assert(await page.locator('#export').isDisabled());await page.unroute('**/mid_pressure_delta.wav');
    await page.evaluate(()=>characterTuner.loadCase('mid'));await page.waitForFunction(()=>characterTuner.ready);
    await page.evaluate(()=>characterTuner.set({pressure:.32,structure:.73,volume:.43,baseline:false}));
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'tuner_desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'tuner_mobile.png'),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
    const report={result:'pass',casesLoaded:cases.length,sampleRate:48000,webAudioMixChecks:mixChecks,
      sourceStartsIdentical:true,controlsIndependent:true,keyboardRange:true,baselinePreservesParametersAndTransport:true,
      loopWrapAndExit:true,loopEndpointFadeAndRawBufferPreservation:true,settingsRoundtrip:true,offgridSettingsRetained:true,baselineAndCandidateExports:true,invalidSettingsPreserveState:true,corruptAssetStopsAndDisablesExport:true,
      exportSettings:saved,mobileOverflow:false,javascriptErrors:errors,
      scope:'Headless Chrome, checksum-verified stereo buffers, actual muted Web Audio transport, OfflineAudioContext and UI downloads. No subjective sound or physical array validation.'};
    fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(report,null,2));
    process.stdout.write(JSON.stringify({...report,webAudioMixChecks:mixChecks.map(x=>({case:x.case,checks:x.checks.length,maxError:Math.max(...x.checks.map(c=>c.maxError))}))},null,2)+'\n');
  }finally{await browser.close();}
})().catch(error=>{process.stderr.write(String(error.stack||error)+'\n');process.exitCode=1;});
