import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from 'playwright';import validator from 'gltf-validator';import {createServer} from 'node:http';
const dir='f01-text-menu-evidence';fs.mkdirSync(dir,{recursive:true});
const token=process.env.FORGE_API_TOKEN,api='http://127.0.0.1:8765',origin='http://127.0.0.1:8766';
const promptText='a red ceramic teapot with a curved handle and spout';
const post=(body,auth=true,extra={})=>fetch(api+'/v1/generate-text',{method:'POST',headers:{'Content-Type':'application/json',...(auth?{Authorization:'Bearer '+token}:{}),...extra},body:JSON.stringify(body)});
assert.equal((await post({prompt:promptText},false)).status,401);
assert.equal((await post({prompt:''})).status,400);
assert.equal((await post({prompt:'a',seed:2})).status,400);
assert.equal((await post({prompt:'a'.repeat(301)})).status,400);
assert.equal((await post({prompt:promptText},true,{Origin:'https://example.invalid'})).status,403);
const health=await(await fetch(api+'/health')).json();assert.equal(health.text_experimental_enabled,true);
const http=createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(fs.readFileSync('Forge_R70_34_F01_Text_Experimental.html'))});await new Promise(r=>http.listen(8766,'127.0.0.1',r));
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:800,height:360},isMobile:true,hasTouch:true}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('dialog',d=>d.type()==='prompt'?d.accept(d.message().includes('adres')?api:token):d.accept());
 await page.goto(origin);await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
 await page.locator('#quickAi').click();await page.locator('#forgeTextOpen').click();
 const sizes=[];
 for(const [width,height] of [[800,360],[740,360],[667,375]]){
  await page.setViewportSize({width,height});const b=await page.locator('#forgeTextDialog').boundingBox();assert.ok(b&&b.x>=0&&b.y>=0&&b.x+b.width<=width+1&&b.y+b.height<=height+1);
  await page.screenshot({path:dir+'/menu-'+width+'.png'});sizes.push({width,height,b});
 }
 await page.locator('#forgeTextStart').click();assert.match(await page.locator('#forgeTextStatus').innerText(),/karakterlik/);
 await page.locator('#forgeTextPrompt').fill(promptText);
 const rp=page.waitForResponse(r=>r.url()===api+'/v1/generate-text'&&r.request().method()==='POST',{timeout:450000});
 await page.locator('#forgeTextStart').click();const response=await rp;assert.equal(response.status(),200);
 const raw=await response.body();fs.writeFileSync(dir+'/generated.glb',raw);const v=await validator.validateBytes(raw);assert.equal(v.issues.numErrors,0);assert.equal(v.issues.numWarnings,0);
 await page.waitForFunction(()=>parts[0]?.type==='aiMesh',null,{timeout:30000});
 const result=await page.evaluate(b64=>{const raw=parseForgeAiGLB(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)).buffer),p=parts[0];return {triangles:p.geometry.i.length/3,rendered:three.renderer.info.render.triangles,geometryUnrotated:raw.geometry.v.every((x,i)=>x===p.geometry.v[i]),overflow:document.documentElement.scrollWidth>innerWidth,secretStored:Object.keys(localStorage).some(k=>localStorage[k].includes(b64))}},raw.toString('base64'));
 assert.equal(result.triangles,result.rendered);assert.ok(result.geometryUnrotated&&!result.overflow&&result.triangles>100&&result.triangles<=60000);
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(secret=>Object.values(localStorage).concat(Object.values(sessionStorage)).some(x=>String(x).includes(secret)),token),false);
 for(const view of ['front','side','back']){await page.locator('#quickCamera [data-action='+view+']').click();await page.screenshot({path:dir+'/'+view+'.png'})}
 fs.writeFileSync(dir+'/report.json',JSON.stringify({actualInference:true,prompt:promptText,bytes:raw.length,glbErrors:v.issues.numErrors,glbWarnings:v.issues.numWarnings,sizes,result,errors},null,2));
}finally{await browser.close();http.close()}
