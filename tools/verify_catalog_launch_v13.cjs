// Exercise the workbench button against an owned bounded server.
const fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require(path.join(process.argv[2], 'playwright'));
const url = process.argv[3], out = process.argv[4];
fs.mkdirSync(out, { recursive: false });
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--mute-audio'] });
  const report = { result: 'running', audio_autoplay: false }, errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(url);
    const click = async () => {
      const [response] = await Promise.all([
        page.waitForResponse(response => response.url().endsWith('/api/driver') && response.request().method() === 'POST'),
        page.click('#driver')
      ]);
      assert.equal(response.status(), 200);
      return response.json();
    };
    const first = await click();
    assert(first.opened && !first.already_open && first.revision === 13 && first.independent_window);
    const second = await click();
    assert(second.already_open && second.pid === first.pid && second.ready === first.ready);
    await page.screenshot({ path: path.join(out, 'workbench.png'), fullPage: true });
    assert.deepEqual(errors, []);
    Object.assign(report, { result: 'passed', first, second, actual_workbench_click: true, duplicate_launch_reused: true });
  } catch (error) {
    report.result = 'failed'; report.error = String(error); throw error;
  } finally {
    report.errors = errors;
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
