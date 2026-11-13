/* Headless QA of this project's local audio preview, never desktop automation. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const { chromium } = require('playwright');

async function main() {
  const [url, out] = process.argv.slice(2);
  assert(url && out, 'usage: node check_idle_state_preview.cjs URL OUTPUT');
  fs.mkdirSync(out, { recursive: false });
  fs.copyFileSync(__filename, path.join(out, 'executed_check.cjs'));
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
    args: ['--mute-audio'],
  });
  const errors = [], responses = [];
  const report = { result: 'failed', url, checks: [], errors, responses,
    audible_or_device_validation: false };
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => responses.push({ url: response.url(), status: response.status() }));
    assert.equal((await page.goto(url)).status(), 200);
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    await page.waitForFunction(() => document.querySelector('#rpm').textContent.endsWith(' RPM'));
    assert.equal(await page.locator('audio').count(), 1);
    assert.equal(await page.locator('#mode option').count(), 3);
    assert.equal(await page.locator('audio').evaluate(a => a.paused), true);
    assert.equal(await page.locator('audio').evaluate(a => a.duration), 8);
    report.checks.push('single player, three modes, eight seconds, no autoplay');
    await page.locator('[data-time="1.05"]').click();
    await page.waitForFunction(() => document.querySelector('#weight').textContent === '100%');
    assert.equal(await page.locator('#state').innerText(), '怠速');
    assert(Math.abs(parseFloat(await page.locator('#rpm').innerText()) - 850) < 1);
    await page.selectOption('#mode', 'original');
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1 &&
      Math.abs(document.querySelector('audio').currentTime - 1.05) < .001 &&
      document.querySelector('#weight').textContent === '0%');
    await page.selectOption('#mode', 'idle_solo');
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1 &&
      document.querySelector('#weight').textContent === '100%');
    report.checks.push('saved trace drives idle/RPM/weight; paused selection preserves position');
    await page.locator('audio').evaluate(async a => { a.muted = true; await a.play(); });
    await page.waitForFunction(() => document.querySelector('audio').currentTime > 1.2);
    const before = await page.locator('audio').evaluate(a => a.currentTime);
    await page.selectOption('#mode', 'candidate');
    await page.waitForFunction(() => !document.querySelector('audio').paused &&
      document.querySelector('#mode').value === 'candidate' &&
      document.querySelector('audio').readyState >= 1);
    const after = await page.locator('audio').evaluate(a => a.currentTime);
    assert(after >= before - .01 && after < before + .7);
    await page.locator('audio').evaluate(a => a.pause());
    for (const [time, state] of [['0', '起动机'], ['1.9', '怠速'], ['4.2', '空挡补油']]) {
      await page.locator(`[data-time="${time}"]`).click();
      await page.waitForFunction(expected => document.querySelector('#state').textContent === expected, state);
    }
    report.checks.push('muted playback advances and survives source switching; seek buttons show expected states');
    await page.locator('[data-time="1.05"]').click();
    await page.waitForFunction(() => document.querySelector('#state').textContent === '怠速');
    await page.screenshot({ path: path.join(out, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(out, 'mobile.png'), fullPage: true });
    report.checks.push('desktop and 390px layouts captured; no horizontal overflow');
    assert.equal(errors.length, 0);
    assert(responses.every(r => r.status === 200 || r.status === 206));
    report.result = 'preview_controls_trace_and_muted_browser_playback_verified';
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify(report));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
