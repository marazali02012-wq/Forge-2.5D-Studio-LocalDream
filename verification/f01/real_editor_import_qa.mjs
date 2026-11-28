// F01 offline real multi-view GLB and independent text GLB import, no mocked model.
import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from 'playwright';import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';import validator from 'gltf-validator';
const out='f01-editor-evidence';fs.mkdirSync(out,{recursive:true});
function withoutVertexColors(source){
 const oldLength=source.readUInt32LE(12);
 const json=JSON.parse(source.subarray(20,20+oldLength).toString('utf8'));
 const primitive=json.meshes[0].primitives[0];
 assert.notEqual(primitive.attributes.COLOR_0,undefined);
 delete primitive.attributes.COLOR_0;
 const material=json.materials?.[primitive.material]?.pbrMetallicRoughness;
 const color=material?.baseColorFactor?.slice(0,3)??[1,1,1];
 const encoded=Buffer.from(JSON.stringify(json),'utf8');
 const aligned=Buffer.alloc(Math.ceil(encoded.length/4)*4,0x20);
 encoded.copy(aligned);
 const header=Buffer.from(source.subarray(0,20));
 const binary=source.subarray(20+oldLength);
 header.writeUInt32LE(header.length+aligned.length+binary.length,8);
 header.writeUInt32LE(aligned.length,12);
 return {bytes:Buffer.concat([header,aligned,binary]),color};
}
const browser=await chromium.launch({headless:true,args:['--allow-file-access-from-files','--enable-unsafe-swiftshader']});
try{
const ctx=await browser.newContext({viewport:{width:800,height:360},offline:true,deviceScaleFactor:1,hasTouch:true,isMobile:true,acceptDownloads:true}),page=await ctx.newPage(),errors=[],requests=[],dialogs=[];
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});page.on('dialog',d=>{dialogs.push(d.message());return d.accept()});
await page.goto(pathToFileURL(resolve('Forge_R70_29_AI_Connected.html')).href);await page.waitForFunction(()=>typeof parseForgeAiGLB==='function');await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
const cases=[['photo','/tmp/mobile-color/colored.glb',57999],['text','/tmp/text-source/text-00.glb',58540]];
const reports=[];
for(const [name,file,count] of cases){
 const source=fs.readFileSync(file);const val=await validator.validateBytes(source);assert.equal(val.issues.numErrors,0);assert.equal(val.issues.numWarnings,0);
 await page.locator('#forgeAiFile').setInputFiles(file);
 await page.waitForFunction(n=>parts[0]?.type==='aiMesh'&&parts[0].geometry.i.length===n*3,count);
 const result=await page.evaluate(()=>({triangles:mesh(parts).pos.length/9,rendered:three.renderer.info.render.triangles,valid:validPart(parts[0]),overflow:document.documentElement.scrollWidth>innerWidth}));
 assert.equal(result.triangles,count);assert.equal(result.rendered,count);assert.ok(result.valid&&!result.overflow);
 for(const [width,height] of [[800,360],[740,360],[667,375]]){
  await page.setViewportSize({width,height});
  for(const view of ['front','side','back']){await page.locator('#quickCamera [data-action='+view+']').click();await page.waitForTimeout(150);await page.screenshot({path:out+'/'+name+'-'+width+'-'+view+'.png'});}
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 }
 const p=page.waitForEvent('download');await page.locator('#project').click();await(await p).saveAs(out+'/'+name+'.json');
 const prior=await page.evaluate(()=>JSON.stringify(parts));await page.locator('#file').setInputFiles(out+'/'+name+'.json');await page.waitForFunction(()=>document.getElementById('file').value==='');assert.equal(await page.evaluate(()=>JSON.stringify(parts)),prior);
 const q=page.waitForEvent('download');await page.locator('#save').click();await(await q).saveAs(out+'/'+name+'-roundtrip.glb');
 const v=await validator.validateBytes(fs.readFileSync(out+'/'+name+'-roundtrip.glb'));assert.equal(v.issues.numErrors,0);assert.equal(v.issues.numWarnings,0);
 await page.locator('#forgeAiFile').setInputFiles({name:'bad.glb',mimeType:'model/gltf-binary',buffer:Buffer.from('bad')});await page.waitForFunction(()=>document.getElementById('forgeAiFile').value==='');assert.equal(await page.evaluate(()=>JSON.stringify(parts)),prior);
 reports.push({name,...result,roundtripErrors:v.issues.numErrors,roundtripWarnings:v.issues.numWarnings});
}
const uncolored=withoutVertexColors(fs.readFileSync(cases[0][1]));
await page.locator('#forgeAiFile').setInputFiles({
 name:'uncolored.glb',mimeType:'model/gltf-binary',buffer:uncolored.bytes,
});
await page.waitForFunction(n=>parts[0]?.type==='aiMesh'&&parts[0].geometry.i.length===n*3,cases[0][2]);
const neutral=await page.evaluate(()=>({
 triangles:three.renderer.info.render.triangles,
 color:parts[0].geometry.c.slice(0,3),
 valid:validPart(parts[0]),
}));
assert.ok(neutral.valid);
assert.equal(neutral.triangles,cases[0][2]);
assert.deepEqual(neutral.color,uncolored.color);
await page.screenshot({path:out+'/uncolored-import.png'});
reports.push({name:'uncolored',...neutral});
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);fs.writeFileSync(out+'/report.json',JSON.stringify({reports,errors,requests,dialogs},null,2));console.log({reports,errors,requests,dialogs});
}finally{await browser.close()}
