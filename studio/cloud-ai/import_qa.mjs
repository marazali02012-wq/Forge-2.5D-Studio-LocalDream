import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from 'playwright';import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';import validator from 'gltf-validator';
const out='r70-28-qa';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--allow-file-access-from-files','--enable-unsafe-swiftshader']});
try{
const ctx=await browser.newContext({viewport:{width:800,height:360},offline:true,deviceScaleFactor:1,hasTouch:true,isMobile:true,acceptDownloads:true}),page=await ctx.newPage(),errors=[],requests=[],dialogs=[];
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});page.on('dialog',d=>{dialogs.push(d.message());return d.accept()});
await page.goto(pathToFileURL(resolve('Forge_R70_28_AI_Import.html')).href);await page.waitForFunction(()=>typeof parseForgeAiGLB==='function');await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
const cases=[['inputs/cloud-lod-qa/robot128/quadric_12k.glb',12000],['r70-28-qa/quality/mobile.glb',JSON.parse(fs.readFileSync('r70-28-qa/quality/report.json')).faces]];
const reports=[];for(const [k,[file,count]] of cases.entries()){
 if(k===1)await page.setViewportSize({width:667,height:375});
 await page.locator('#forgeAiFile').setInputFiles(file);
 await page.waitForFunction(n=>parts[0]?.type==='aiMesh'&&parts[0].geometry.i.length===n*3,count);
 const result=await page.evaluate(()=>({triangles:mesh(parts).pos.length/9,rendered:three.renderer.info.render.triangles,valid:validPart(parts[0]),overflow:document.documentElement.scrollWidth>innerWidth}));
 assert.equal(result.triangles,count);assert.equal(result.rendered,count);assert.ok(result.valid&&!result.overflow);
 for(const view of ['front','side','back']){await page.locator('#quickCamera [data-action='+view+']').click();await page.screenshot({path:out+'/'+k+'_'+view+'.png'})}
 const p=page.waitForEvent('download');await page.locator('#project').click();const dl=await p;await dl.saveAs(out+'/project_'+k+'.json');
 const prior=await page.evaluate(()=>JSON.stringify(parts));await page.locator('#file').setInputFiles(out+'/project_'+k+'.json');await page.waitForFunction(()=>document.getElementById('file').value==='');assert.equal(await page.evaluate(()=>JSON.stringify(parts)),prior);
 const q=page.waitForEvent('download');await page.locator('#save').click();await(await q).saveAs(out+'/roundtrip_'+k+'.glb');
 const validation=await validator.validateBytes(Uint8Array.from(fs.readFileSync(out+'/roundtrip_'+k+'.glb')));assert.equal(validation.issues.numErrors,0);assert.equal(validation.issues.numWarnings,0);
 result.validation={errors:validation.issues.numErrors,warnings:validation.issues.numWarnings};
 await page.locator('#forgeAiFile').setInputFiles({name:'bad.glb',mimeType:'model/gltf-binary',buffer:Buffer.from('bad')});await page.waitForFunction(()=>document.getElementById('forgeAiFile').value==='');assert.equal(await page.evaluate(()=>JSON.stringify(parts)),prior);reports.push(result);
}
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);fs.writeFileSync(out+'/browser-report.json',JSON.stringify({reports,errors,requests,dialogs},null,2));console.log(JSON.stringify({reports,errors,requests,dialogs}));
}finally{await browser.close()}
