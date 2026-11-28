// F01 real end-to-end chain, no test double: editor upload -> authenticated
// Forge server -> provider (server CPU or private Kaggle CPU session) ->
// BiRefNet mask -> TripoSG -> mobile geometry gate -> automatic GLB download ->
// editor import -> five views -> edit (mirror) -> GLB export -> Khronos.
// The server runs private_api_kaggle.py with FORGE_LOCAL_TRIPOSG=1 or
// FORGE_KAGGLE_RESEARCH=1 (FORGE_KAGGLE_ACCELERATOR=cpu|gpu).
// Usage: node local_editor_qa.mjs SERVER_ORIGIN IMAGE.png EVIDENCE_DIR
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {chromium} from 'playwright';
import validator from 'gltf-validator';

const [server, image, evidence] = process.argv.slice(2);
const token = process.env.FORGE_API_TOKEN;
assert(server && image && evidence && token, 'usage: SERVER IMAGE EVIDENCE with FORGE_API_TOKEN set');
fs.mkdirSync(evidence, {recursive: true, mode: 0o700});
async function validate(data) {
  const {issues} = await validator.validateBytes(new Uint8Array(data));
  return [issues.numErrors, issues.numWarnings];
}
const started = Date.now();
const browser = await chromium.launch({args: ['--enable-unsafe-swiftshader']});
try {
  const context = await browser.newContext({
    viewport: {width: 740, height: 360}, deviceScaleFactor: 1, hasTouch: true, isMobile: true,
    acceptDownloads: true,
  });
  const page = await context.newPage();
  const issues = [];
  const statuses = [];
  let served = null;
  page.on('pageerror', error => issues.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  // The page and API share one origin through the runner, as in kaggle_editor_qa.mjs.
  await page.route(server + '/**', async route => {
    const request = route.request();
    if (new URL(request.url()).pathname === '/editor') {
      return route.fulfill({contentType: 'text/html', path: 'Forge_R70_34_Studio.html'});
    }
    let response;
    try {
      response = await fetch(request.url(), {
        method: request.method(), headers: request.headers(),
        body: request.postDataBuffer() ?? undefined,
      });
    } catch {
      // A restarting server must look like a real network failure to the page.
      return route.abort('connectionrefused');
    }
    const body = Buffer.from(await response.arrayBuffer());
    if (request.url().endsWith('/model') && response.ok) served = body;
    return route.fulfill({status: response.status, headers: Object.fromEntries(response.headers), body});
  });
  await page.addInitScript(() => {
    const original = window.setTimeout;
    window.setTimeout = (callback, timeout, ...args) =>
      original(callback, timeout === 15000 ? 5000 : timeout, ...args);
  });
  await page.goto(server + '/editor');
  await page.locator('#quickThree').click();
  await page.waitForFunction(() => threeEnabled);
  await page.locator('#quickAi').click();
  await page.locator('#forgeKaggleOpen').click();
  await page.screenshot({path: evidence + '/dialog.png'});
  await page.locator('#forgeKaggleImage').setInputFiles(image);
  await page.locator('#forgeKaggleServer').fill(server + '/');
  await page.locator('#forgeKaggleAccess').fill(token);
  await page.locator('#forgeKaggleStart').click();
  const deadline = Date.now() + 3 * 3600_000;
  let last = '';
  while (Date.now() < deadline) {
    const text = await page.locator('#forgeKaggleStatus').textContent();
    if (text !== last) {
      last = text;
      statuses.push({seconds: Math.round((Date.now() - started) / 1000), text});
      console.log(JSON.stringify(statuses.at(-1)));
      if (/üretiyor|sırasında/.test(text) && statuses.length < 6) {
        await page.screenshot({path: evidence + '/status-' + statuses.length + '.png'});
      }
    }
    if (await page.evaluate(() => parts[0]?.type === 'aiMesh')) break;
    if (/başarısız|iptal|doldu|geçersiz/i.test(text)) throw Error('Chain failed: ' + text);
    await page.waitForTimeout(2000);
  }
  assert(served, 'No GLB was downloaded from the server');
  assert.deepEqual(await validate(served), [0, 0]);
  const count = await page.evaluate(() => parts[0].geometry.i.length / 3);
  for (const [angle, radians] of Object.entries({
    front: 0, back: Math.PI, right: Math.PI / 2, left: -Math.PI / 2, diagonal: Math.PI / 4,
  })) {
    await page.evaluate(radians => {yaw = radians; pitch = .08; draw();}, radians);
    assert.equal(await page.evaluate(() => three.renderer.info.render.triangles), count);
    await page.screenshot({path: evidence + '/' + angle + '.png'});
  }
  // Edit: mirror the AI part (an existing editor operation), then export.
  await page.evaluate(() => {parts[0].mirror = !parts[0].mirror; draw();});
  await page.screenshot({path: evidence + '/edited-mirror.png'});
  const download = page.waitForEvent('download');
  await page.locator('#save').click();
  const exported = evidence + '/roundtrip.glb';
  await (await download).saveAs(exported);
  const exportedIssues = await validate(fs.readFileSync(exported));
  assert.deepEqual(exportedIssues, [0, 0]);
  assert.deepEqual(issues, []);
  const result = {
    chain: 'editor->server->provider->BiRefNet->TripoSG->mobile gate->editor->export',
    seconds: Math.round((Date.now() - started) / 1000), renderedTriangles: count,
    servedBytes: served.length, angles: 5, KhronosServed: [0, 0], KhronosExport: exportedIssues,
    jsErrors: issues.length, statuses,
  };
  fs.writeFileSync(evidence + '/result.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
}
