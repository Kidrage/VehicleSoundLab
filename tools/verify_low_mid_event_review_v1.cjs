// Bounded, muted verification of the nine-track E candidate review.
const fs = require('fs'), path = require('path'), assert = require('assert'), crypto = require('crypto');
const { chromium } = require(path.join(process.argv[2], 'playwright'));
const url = process.argv[3], out = process.argv[4];
fs.mkdirSync(out, { recursive: false });
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--mute-audio'] });
  const report = { result: 'running', timbre_accepted: false }, errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 1000 }, acceptDownloads: true });
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(url);
    assert.equal(await page.locator('audio').count(), 1);
    assert(await page.locator('audio').evaluate(a => a.paused && !a.autoplay));
    const tracks = await page.evaluate(() => tracks);
    assert.equal(tracks.length, 9);
    const select = async index => {
      const previous = await page.locator('audio').evaluate(a => a.currentSrc);
      await page.click('[data-track="' + index + '"]');
      await page.waitForFunction(previous => {
        const a = document.querySelector('audio');
        return a.currentSrc !== previous && a.readyState >= 2 && !a.seeking;
      }, previous);
      assert(await page.locator('audio').evaluate(a => a.currentSrc.startsWith('blob:')));
      assert.equal(await page.locator('[aria-pressed="true"]').count(), 1);
    };
    report.decoded = [];
    for (const [index, row] of tracks.entries()) {
      const response = await page.request.get(new URL(row.file, url).href);
      assert.equal(response.status(), 200);
      assert.equal(hash(await response.body()), row.sha256);
      const decoded = await page.evaluate(async file => {
        const context = new AudioContext();
        try {
          const audio = await context.decodeAudioData(await (await fetch(file)).arrayBuffer());
          return { frames: audio.length, channels: audio.numberOfChannels, rate: audio.sampleRate };
        } finally { await context.close(); }
      }, row.file);
      // decodeAudioData may resample on a non-48kHz browser device.
      assert(Math.abs(decoded.frames / decoded.rate - row.frames / 48000) < 1 / decoded.rate);
      assert.equal(decoded.channels, row.channels);
      await select(index);
      const target = await page.locator('audio').evaluate(a => {
        const target = Math.min(.3, a.duration / 2);
        a.currentTime = target; a.volume = .4; return target;
      });
      await page.waitForFunction(target => {
        const a = document.querySelector('audio');
        return !a.seeking && Math.abs(a.currentTime - target) < .015;
      }, target);
      report.decoded.push({ file: row.file, ...decoded, seek_seconds: target });
    }
    await select(6);
    await page.locator('audio').evaluate(async a => { a.currentTime = 2; await a.play(); });
    await select(7);
    await page.waitForFunction(() => {
      const a = document.querySelector('audio');
      return a.duration === 8 && !a.paused && a.currentTime >= 2 && a.currentTime < 3;
    });
    await page.locator('audio').evaluate(a => a.pause());
    assert.equal(await page.locator('audio').evaluate(a => a.volume), .4);
    await page.evaluate(() => {
      for (const index of [0, 7, 1]) document.querySelector('[data-track="' + index + '"]').click();
    });
    await page.waitForFunction(() => {
      const a = document.querySelector('audio');
      return a.readyState >= 2 && !a.seeking && Math.abs(a.duration - .1) < .001 &&
        document.querySelector('[data-track="1"]').getAttribute('aria-pressed') === 'true';
    });
    await select(7);
    for (const href of await page.locator('a').evaluateAll(links => links.map(a => a.href))) {
      assert.equal((await page.request.get(href)).status(), 200);
    }
    report.downloads = [];
    for (const file of ['event-profile.json', 'controller-preset.json', 'drive-on.take.json']) {
      const [download] = await Promise.all([page.waitForEvent('download'), page.click('a[href="' + file + '"]')]);
      const destination = path.join(out, file);
      await download.saveAs(destination);
      const response = await page.request.get(new URL(file, url).href);
      assert.equal(hash(fs.readFileSync(destination)), hash(await response.body()));
      report.downloads.push({ file, sha256: hash(fs.readFileSync(destination)) });
    }
    await page.screenshot({ path: path.join(out, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(out, 'mobile.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert.deepEqual(errors, []);
    Object.assign(report, { result: 'passed', nine_hashes_and_decodes: true,
      short_100ms_blob_seek: true, playing_switch_position_and_volume_preserved: true,
      rapid_switch_last_request_wins: true, actual_downloads_exact: true,
      one_player: true, desktop_mobile: true, audio_muted: true });
  } catch (error) {
    report.result = 'failed'; report.error = String(error); throw error;
  } finally {
    report.errors = errors;
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
  console.log(JSON.stringify(report));
})().catch(error => { console.error(error); process.exit(1); });
