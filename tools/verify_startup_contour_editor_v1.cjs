// Final contour editor: capacity, removals, immutable history and desktop/mobile layout.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(path.join(process.argv[2],'playwright'));
const base=process.argv[3],out=process.argv[4],id=process.argv[5];
(async()=>{fs.mkdirSync(out);const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});let page;const errors=[],report={result:'running'};
 try{
  page=await browser.newPage({viewport:{width:1440,height:1600}});page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(id=>localStorage.setItem('vslEventProject',id),id);
  await page.goto(base+'/events.html');await page.waitForFunction(()=>!document.querySelector('#render').disabled);
  const current=async()=>await(await page.request.get(base+'/api/events/project/'+id)).json();
  const original=await current(),revision=original.history[0].id;
  await page.locator('#contourPanel').evaluate(e=>e.open=true);
  for(let i=0;i<2;i++)await page.click('#addContour');
  assert.equal(await page.locator('#contourRows fieldset').count(),4);assert(await page.locator('#addContour').isDisabled());
  await page.locator('#contourRows fieldset').last().getByText('删除频段',{exact:true}).click();assert(!await page.locator('#addContour').isDisabled());
  await page.click('#addContour');assert(await page.locator('#addContour').isDisabled());
  let card=page.locator('#contourRows fieldset').first();await card.locator('tbody tr').nth(2).locator('button').click();
  assert.equal(await card.locator('tbody tr').count(),7);assert(!await card.locator('[data-add-point]').isDisabled());
  await card.locator('[data-add-point]').click();assert.equal(await card.locator('tbody tr').count(),8);assert(await card.locator('[data-add-point]').isDisabled());
  await page.click('#save');await page.waitForFunction(()=>!document.querySelector('#save').disabled);
  const saved=await current();assert.equal(saved.document.parameters.contours.length,4);
  assert(await card.locator('tbody tr').first().locator('button').isDisabled());assert(await card.locator('[data-time]').first().evaluate(e=>e.readOnly));
  await page.locator('#historyPanel').evaluate(e=>e.open=true);await page.selectOption('#historyList',revision);await page.click('#restoreHistory');
  await page.waitForFunction(()=>!document.querySelector('#restoreHistory').disabled&&document.querySelectorAll('#contourRows fieldset').length===2);
  assert.deepEqual((await current()).document.parameters,original.document.parameters);
  await page.locator('#contourPanel').evaluate(e=>e.open=true);await page.locator('#contourRows').scrollIntoViewIfNeeded();await page.evaluate(()=>scrollBy(0,-190));
  await page.locator('#contourRows').screenshot({path:path.join(out,'contours.png')});
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,'desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.locator('#contourRows fieldset').first().scrollIntoViewIfNeeded();await page.evaluate(()=>scrollBy(0,-180));
  await page.screenshot({path:path.join(out,'mobile.png')});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);Object.assign(report,{result:'passed',four_group_limit_and_reenable:true,eight_point_limit_and_reenable:true,
   first_point_protected_after_save:true,history_restores_parameters_exact:true,desktop_mobile_checked:true});
 }catch(e){report.result='failed';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png')});throw e;}
 finally{report.errors=errors;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});
