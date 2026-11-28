// F01 visual audit: real WebGL renders of actual GLB geometry from five
// directions next to the source image. No mesh editing, only viewing.
// Usage: node glb_views.mjs THREE_DIR OUT.png "label|source.png|model.glb" ...
// THREE_DIR holds three@0.170.0 build/three.module.js and examples/jsm (pinned by SHA-256).
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from 'playwright';

const [threeDir, out, ...rows] = process.argv.slice(2);
assert(threeDir && out && rows.length, 'usage: glb_views.mjs THREE_DIR OUT.png "label|source|glb" ...');
const pinned = {
  'build/three.module.js': 'ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb',
  'examples/jsm/loaders/GLTFLoader.js': '45139faddd5aaf48ed2d62203d976e5cbd703db1a592de40527f9f6cf58abd44',
  'examples/jsm/utils/BufferGeometryUtils.js': 'c25b7930e570e9ec56173cd3b866ec8d2e10016630db3937efb439daf1cedbf6',
};
for (const [file, digest] of Object.entries(pinned)) {
  const actual = crypto.createHash('sha256').update(fs.readFileSync(path.join(threeDir, file))).digest('hex');
  assert.equal(actual, digest, 'three.js checksum mismatch: ' + file);
}
const files = new Map();
const cases = rows.map((row, index) => {
  const [label, source, glb] = row.split('|');
  files.set(`/src${index}.png`, [fs.readFileSync(source), 'image/png']);
  files.set(`/model${index}.glb`, [fs.readFileSync(glb), 'model/gltf-binary']);
  return {label, source: `/src${index}.png`, model: `/model${index}.glb`};
});
for (const file of Object.keys(pinned)) {
  files.set('/three/' + file, [fs.readFileSync(path.join(threeDir, file)), 'text/javascript']);
}
const page_html = `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#1b2028">
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const S = 260, cases = ${JSON.stringify(cases)};
const views = [['Ön', [0, 0, 1]], ['Arka', [0, 0, -1]], ['Sağ', [1, 0, 0]], ['Sol', [-1, 0, 0]], ['Çapraz', [0.7, 0.35, 0.7]]];
const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
renderer.setSize(S, S);
const sheet = document.createElement('canvas');
sheet.width = S * 6; sheet.height = (S + 26) * cases.length;
const g = sheet.getContext('2d');
g.fillStyle = '#1b2028'; g.fillRect(0, 0, sheet.width, sheet.height);
const stats = [];
for (const [row, item] of cases.entries()) {
  const y0 = row * (S + 26);
  const img = new Image(); img.src = item.source; await img.decode();
  const k = Math.min(S / img.width, S / img.height);
  g.drawImage(img, (S - img.width * k) / 2, y0 + 26 + (S - img.height * k) / 2, img.width * k, img.height * k);
  const gltf = await new GLTFLoader().loadAsync(item.model);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#2a313c');
  let triangles = 0;
  gltf.scene.traverse(o => {
    if (!o.isMesh) return;
    o.geometry.computeVertexNormals();
    o.material = new THREE.MeshStandardMaterial({color: '#c9c3b8', roughness: .75, metalness: 0, side: THREE.DoubleSide});
    triangles += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
  });
  scene.add(gltf.scene);
  const box = new THREE.Box3().setFromObject(gltf.scene);
  const center = box.getCenter(new THREE.Vector3()), radius = box.getBoundingSphere(new THREE.Sphere()).radius;
  scene.add(new THREE.HemisphereLight('#ffffff', '#445', 1.6));
  for (const [ok, name] of views.entries()) {
    const [label, dir] = name;
    const camera = new THREE.OrthographicCamera(-radius, radius, radius, -radius, .01, radius * 10);
    const d = new THREE.Vector3(...dir).normalize();
    camera.position.copy(center).addScaledVector(d, radius * 4);
    camera.lookAt(center);
    const light = new THREE.DirectionalLight('#ffffff', 2.2);
    light.position.copy(camera.position).add(new THREE.Vector3(radius, radius * 2, 0));
    scene.add(light);
    renderer.render(scene, camera);
    scene.remove(light);
    g.drawImage(renderer.domElement, S * (ok + 1), y0 + 26);
    g.fillStyle = '#e8edf3'; g.font = '14px sans-serif'; g.fillText(label, S * (ok + 1) + 8, y0 + 44);
  }
  g.fillStyle = '#ffffff'; g.font = 'bold 15px sans-serif';
  g.fillText(item.label + ' · ' + triangles.toLocaleString('tr-TR') + ' üçgen', 8, y0 + 18);
  stats.push({label: item.label, triangles});
}
window.result = {png: sheet.toDataURL('image/png'), stats};
</script>`;
const browser = await chromium.launch({args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://forge.local/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: page_html});
    const hit = files.get(url.pathname);
    return hit ? route.fulfill({contentType: hit[1], body: hit[0]}) : route.fulfill({status: 404});
  });
  await page.goto('http://forge.local/');
  await page.waitForFunction(() => window.result || null, null, {timeout: 600000});
  assert.deepEqual(errors, []);
  const result = await page.evaluate(() => window.result);
  fs.writeFileSync(out, Buffer.from(result.png.split(',')[1], 'base64'));
  console.log(JSON.stringify({out, rows: result.stats}));
} finally {
  await browser.close();
}
