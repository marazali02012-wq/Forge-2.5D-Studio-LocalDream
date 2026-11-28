// The HTTP bridge uses a provider double. The editor draws and exports a real GLB.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs';
import {chromium} from 'playwright';
import validator from 'gltf-validator';

const [input, evidence] = process.argv.slice(2);
assert(input && evidence, 'Supply an editor-ready GLB and an evidence directory.');
fs.mkdirSync(evidence, {recursive: true, mode: 0o700});
const raw = fs.readFileSync(input);
const scene = JSON.parse(raw.subarray(20, 20 + raw.readUInt32LE(12)));
const count = scene.accessors[scene.meshes[0].primitives[0].indices].count / 3;
async function validate(data) {
  const {issues} = await validator.validateBytes(data);
  assert.deepEqual([issues.numErrors, issues.numWarnings], [0, 0]);
}
await validate(raw);
const fixture = spawn(process.env.FORGE_QA_PYTHON || 'python', [
  'verification/f01/kaggle_bridge_qa.py', '--serve-fixture', input,
], {stdio: ['ignore', 'pipe', 'inherit']});
let browser;
try {
  const [chunk] = await once(fixture.stdout, 'data');
  const port = Number(String(chunk).trim());
  assert(Number.isInteger(port) && port > 0);
  browser = await chromium.launch({
    executablePath: process.env.FORGE_QA_CHROMIUM,
    args: ['--allow-file-access-from-files', '--enable-unsafe-swiftshader'],
  });
  const context = await browser.newContext({
    viewport: {width: 740, height: 360},
    deviceScaleFactor: 1, hasTouch: true, isMobile: true, acceptDownloads: true,
  });
  const page = await context.newPage();
  const issues = [];
  const calls = [];
  page.on('pageerror', error => issues.push(error.message));
  page.on('requestfailed', request => console.error(request.failure()?.errorText));
  page.on('request', request => {
    if (request.url().startsWith('http:') && !request.url().startsWith('http://127.0.0.1:')) {
      issues.push('Unexpected HTTP request');
    }
    if (request.method() === 'POST') calls.push(new URL(request.url()).pathname);
  });
  page.on('dialog', dialog => dialog.accept());
  await page.addInitScript(() => {
    const original = window.setTimeout;
    window.setTimeout = (callback, timeout, ...args) =>
      original(callback, timeout === 15000 ? 150 : timeout, ...args);
  });
  // Route through the test runner because this workspace's Chromium restricts
  // local sockets. API requests still traverse the real localhost HTTP handler.
  const local = 'http://127.0.0.1:' + port;
  await page.route(local + '/**', async route => {
    const request = route.request();
    if (new URL(request.url()).pathname === '/editor') {
      return route.fulfill({contentType: 'text/html', path: 'Forge_R70_34_Studio.html'});
    }
    const response = await fetch(request.url(), {
      method: request.method(), headers: request.headers(),
      body: request.postDataBuffer() ?? undefined,
    });
    return route.fulfill({
      status: response.status, headers: Object.fromEntries(response.headers),
      body: Buffer.from(await response.arrayBuffer()),
    });
  });
  await page.goto(local + '/editor');
  await page.locator('#quickThree').click();
  await page.waitForFunction(() => threeEnabled);
  await page.locator('#quickAi').click();
  assert(await page.getByRole('button', {name: 'Resimden 3D üret', exact: true}).isVisible());
  await page.locator('#forgeKaggleOpen').click();
  for (const [width, height] of [[667, 375], [740, 360], [800, 360]]) {
    await page.setViewportSize({width, height});
    const fits = await page.locator('#forgeKaggleDialog').evaluate(dialog => {
      const box = dialog.getBoundingClientRect();
      return box.left >= 0 && box.top >= 0 && box.right <= innerWidth &&
        box.bottom <= innerHeight && dialog.scrollWidth <= dialog.clientWidth &&
        dialog.scrollHeight <= dialog.clientHeight &&
        dialog.querySelector('#forgeKaggleStart').getBoundingClientRect().bottom < box.bottom;
    });
    assert(fits, 'Forge Kaggle dialog overflows');
    await page.screenshot({path: evidence + '/dialog-' + width + '.png'});
  }
  await page.setViewportSize({width: 740, height: 360});
  const inputImage = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGNkYGhgIAUwkaR6VMOohiGlAQC6nwCgXe7drgAAAABJRU5ErkJggg==', 'base64');
  await page.locator('#forgeKaggleImage').setInputFiles({
    name: 'local-fixture.png', mimeType: 'image/png', buffer: inputImage,
  });
  await page.locator('#forgeKaggleServer').fill(local);
  await page.locator('#forgeKaggleAccess').fill('forge-local-test-access-not-a-real-key');
  await page.locator('#forgeKaggleStart').click();
  await page.waitForFunction(() => $('forgeKaggleStatus').textContent.includes('GPU kuyruğunda'), null, {timeout: 8000})
    .catch(async error => {
      console.error('Editor status:', await page.locator('#forgeKaggleStatus').textContent());
      throw error;
    });
  await page.screenshot({path: evidence + '/queued.png'});
  await page.waitForFunction(() => $('forgeKaggleStatus').textContent.includes('modeli üretiyor'));
  await page.waitForFunction(n => parts[0]?.type === 'aiMesh' && parts[0].geometry.i.length === n * 3, count);
  for (const [angle, radians] of Object.entries({
    front: 0, back: Math.PI, right: Math.PI / 2, left: -Math.PI / 2, diagonal: Math.PI / 4,
  })) {
    await page.evaluate(radians => {yaw = radians; pitch = .08; draw();}, radians);
    assert.equal(await page.evaluate(() => three.renderer.info.render.triangles), count);
    await page.screenshot({path: evidence + '/' + angle + '.png'});
  }
  const download = page.waitForEvent('download');
  await page.locator('#save').click();
  const exported = evidence + '/roundtrip.glb';
  await (await download).saveAs(exported);
  await validate(fs.readFileSync(exported));
  assert.deepEqual(calls, ['/v1/kaggle-jobs']);
  assert.deepEqual(issues, []);
  console.log(JSON.stringify({provider: 'local test double', renderedTriangles: count,
    angles: 5, dialogSizes: 3, KhronosErrors: 0, KhronosWarnings: 0, jsErrors: issues.length}));
} finally {
  await browser?.close();
  fixture.kill();
}
