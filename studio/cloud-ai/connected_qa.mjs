import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from 'playwright';import validator from 'gltf-validator';import {createServer} from 'node:http';
const dir='r70-29-qa';fs.mkdirSync(dir,{recursive:true});const token=process.env.FORGE_API_TOKEN,api='http://127.0.0.1:8765';
const image=fs.readFileSync(process.env.FORGE_TEST_IMAGE || '/tmp/triposr/examples/robot.png');
const bad=await fetch(api+'/v1/generate',{method:'POST',headers:{'Content-Type':'image/png'},body:image});assert.equal(bad.status,401);
const invalid=await fetch(api+'/v1/generate',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'text/plain'},body:'x'});assert.equal(invalid.status,415);
const http=createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(fs.readFileSync('Forge_R70_29_AI_Connected.html'))});await new Promise(r=>http.listen(8766,'127.0.0.1',r));
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
try{
 const ctx=await browser.newContext({viewport:{width:800,height:360},isMobile:true,hasTouch:true,acceptDownloads:true});const page=await ctx.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));page.on('dialog',d=>d.type()==='prompt'?d.accept(d.message().includes('adres')?api:token):d.accept());
 await page.goto('http://127.0.0.1:8766');await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
 const responsePromise=page.waitForResponse(r=>r.url()===api+'/v1/generate'&&r.request().method()==='POST',{timeout:330000});
 await page.locator('#forgeAiImage').setInputFiles({name:'character.png',mimeType:'image/png',buffer:image});
 const response=await responsePromise;assert.equal(response.status(),200);const data=await response.body();fs.writeFileSync(dir+'/real-generated-raw.glb',data);const validation=await validator.validateBytes(data);assert.equal(validation.issues.numErrors,0);
 await page.waitForFunction(()=>parts[0]?.type==='aiMesh',null,{timeout:120000});
 const result=await page.evaluate(b64=>{const raw=parseForgeAiGLB(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)).buffer),p=parts[0],a=raw.geometry.v,b=p.geometry.v;return {triangles:mesh(parts).pos.length/9,rendered:three.renderer.info.render.triangles,overflow:document.documentElement.scrollWidth>innerWidth,axisCorrect:a.every((v,i)=>Math.abs(v-b[i-i%3+(i%3+2)%3])<1e-6),normalCorrect:raw.geometry.n.every((v,i)=>Math.abs(v-p.geometry.n[i-i%3+(i%3+2)%3])<1e-6)}},data.toString('base64'));
 assert.equal(result.triangles,result.rendered);assert.ok(result.triangles>100&&!result.overflow&&result.axisCorrect&&result.normalCorrect);assert.deepEqual(errors,[]);
 for(const view of ['front','side','back']){await page.locator('#quickCamera [data-action='+view+']').click();await page.screenshot({path:dir+'/'+view+'.png'})}
 // F01: real mobile dialog and explicit high-detail upload, not a stub.
 const quality={viewports:[],actualInference:false};
 for(const [width,height] of [[800,360],[740,360],[667,375]]){
  await page.setViewportSize({width,height});
  await page.locator('#quickAi').click();
  const q=page.locator('#forgeStaticQuality');await q.waitFor({state:'visible'});
  assert.equal(await q.inputValue(),'128');
  const bounds=await page.locator('#aiTools').boundingBox();
  assert.ok(bounds&&bounds.x>=0&&bounds.y>=0&&bounds.x+bounds.width<=width+1&&bounds.y+bounds.height<=height+1);
  await page.screenshot({path:dir+'/f01-quality-menu-'+width+'.png'});
  quality.viewports.push({width,height,bounds});
  await page.locator('#closeAiTools').click();
 }
 const chair=fs.readFileSync('/tmp/triposr/examples/chair.png');
 await page.locator('#quickAi').click();
 await page.locator('#forgeStaticQuality').selectOption('192');
 await page.screenshot({path:dir+'/f01-quality-selected.png'});
 const highResponse=page.waitForResponse(r=>r.url()===api+'/v1/generate?resolution=192'&&r.request().method()==='POST',{timeout:330000});
 const chooser=page.waitForEvent('filechooser');
 await page.locator('#aiTools [data-forge-action="forgeAiGenerate"]').click();
 await (await chooser).setFiles({name:'chair.png',mimeType:'image/png',buffer:chair});
 const hd=await highResponse;assert.equal(hd.status(),200);
 const hdData=await hd.body();fs.writeFileSync(dir+'/f01-chair-hd.glb',hdData);
 const hdValidation=await validator.validateBytes(hdData);
 assert.equal(hdValidation.issues.numErrors,0);assert.equal(hdValidation.issues.numWarnings,0);
 const parsed=await page.evaluate(b64=>parseForgeAiGLB(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)).buffer).geometry.i.length/3,hdData.toString('base64'));
 await page.waitForFunction(n=>parts[0]?.type==='aiMesh'&&parts[0].geometry.i.length/3===n,parsed,{timeout:120000});
 quality.actualInference=true;quality.triangles=parsed;quality.bytes=hdData.length;quality.glbErrors=hdValidation.issues.numErrors;quality.glbWarnings=hdValidation.issues.numWarnings;
 assert.ok(parsed>30000&&parsed<=60000);
 assert.deepEqual(errors,[]);
 for(const view of ['front','side','back']){
  await page.locator('#quickCamera [data-action='+view+']').click();
  await page.screenshot({path:dir+'/f01-chair-hd-'+view+'.png'});
 }
 // F01: two independent genuine inference requests; invalid image must not
 // erase prior successes or abort later files.
 const batch={requests:0,downloads:[],viewports:[]};
 await page.locator('#quickAi').click();await page.locator('#forgeStaticQuality').selectOption('128');await page.locator('#forgeBatchOpen').click();
 for(const [width,height] of [[800,360],[740,360],[667,375]]){
  await page.setViewportSize({width,height});const box=await page.locator('#forgeBatchDialog').boundingBox();
  assert.ok(box&&box.x>=0&&box.y>=0&&box.x+box.width<=width+1&&box.y+box.height<=height+1);
  await page.screenshot({path:dir+'/f01-batch-menu-'+width+'.png'});batch.viewports.push({width,height,box});
 }
 const before=await page.evaluate(()=>JSON.stringify(parts[0].geometry.i));
 await page.locator('#forgeBatchFiles').setInputFiles([
  {name:'chair.png',mimeType:'image/png',buffer:chair},
  {name:'invalid.png',mimeType:'image/png',buffer:Buffer.from('not png')},
  {name:'teapot.png',mimeType:'image/png',buffer:fs.readFileSync('/tmp/triposr/examples/teapot.png')}
 ]);
 const responses=[];const listener=r=>{if(r.url()===api+'/v1/generate'&&r.request().method()==='POST')responses.push(r.status())};page.on('response',listener);
 await page.locator('#forgeBatchStart').click();
 await page.waitForFunction(()=>document.getElementById('forgeBatchStatus').textContent==='Hazır: 2 · Hata: 1 · Atlanan: 0',null,{timeout:650000});
 page.off('response',listener);assert.deepEqual(responses,[200,400,200]);batch.requests=responses;
 assert.equal(await page.evaluate(()=>JSON.stringify(parts[0].geometry.i)),before);
 const links=page.locator('#forgeBatchResults a');assert.equal(await links.count(),2);
 for(let i=0;i<2;i++){
  const wait=page.waitForEvent('download');await links.nth(i).click();const download=await wait;
  const name=download.suggestedFilename();assert.equal(name,['1-chair.glb','3-teapot.glb'][i]);
  const path=dir+'/f01-batch-'+name;await download.saveAs(path);const bytes=fs.readFileSync(path);
  const v=await validator.validateBytes(bytes);assert.equal(v.issues.numErrors,0);assert.equal(v.issues.numWarnings,0);
  batch.downloads.push({name,bytes:bytes.length,errors:v.issues.numErrors,warnings:v.issues.numWarnings});
 }
 assert.notDeepEqual(fs.readFileSync(dir+'/f01-batch-1-chair.glb'),fs.readFileSync(dir+'/f01-batch-3-teapot.glb'));
 assert.ok((await page.locator('#forgeBatchResults').innerText()).includes('Geçersiz veya boş görsel'));
 assert.equal(await page.locator('#forgeBatchChoose').innerText(),'Görselleri seç');
 await page.screenshot({path:dir+'/f01-batch-results.png'});
 // A real generation starts, then stop must prevent the second POST.
 await page.locator('#forgeBatchFiles').setInputFiles([
  {name:'chair.png',mimeType:'image/png',buffer:chair},
  {name:'teapot.png',mimeType:'image/png',buffer:fs.readFileSync('/tmp/triposr/examples/teapot.png')}
 ]);
 const stopPosts=[];const stopListener=r=>{if(r.url()===api+'/v1/generate'&&r.method()==='POST')stopPosts.push(r.url())};
 page.on('request',stopListener);
 const firstPost=page.waitForRequest(r=>r.url()===api+'/v1/generate'&&r.method()==='POST');
 await page.locator('#forgeBatchStart').click();await firstPost;
 await page.locator('#forgeBatchStop').click();
 await page.waitForFunction(()=>document.getElementById('forgeBatchStatus').textContent==='Hazır: 1 · Hata: 0 · Atlanan: 1',null,{timeout:350000});
 page.off('request',stopListener);assert.equal(stopPosts.length,1);
 assert.equal(await page.locator('#forgeBatchResults a').count(),1);assert.ok(await page.locator('#forgeBatchChoose').isEnabled());
 batch.stop={posts:stopPosts.length,ready:1,skipped:1};
 await page.screenshot({path:dir+'/f01-batch-stop.png'});await page.locator('#forgeBatchClose').click();
 assert.deepEqual(errors,[]);
 const report={batch,quality,actualUpload:true,actualInference:true,httpStatus:response.status(),authRejected:bad.status,invalidRejected:invalid.status,bytes:data.length,...result,glbErrors:validation.issues.numErrors,glbWarnings:validation.issues.numWarnings,errors,requests:requests.filter(s=>/^https?:/.test(s)).map(s=>new URL(s).origin)};
 fs.writeFileSync(dir+'/report.json',JSON.stringify(report,null,2));console.log(report);
}finally{await browser.close();http.close()}
