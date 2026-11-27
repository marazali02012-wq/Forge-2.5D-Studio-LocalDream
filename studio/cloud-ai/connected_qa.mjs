import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from 'playwright';import validator from 'gltf-validator';import {createServer} from 'node:http';
const dir='r70-29-qa';fs.mkdirSync(dir,{recursive:true});const token=process.env.FORGE_API_TOKEN,api='http://127.0.0.1:8765';
const image=fs.readFileSync('/tmp/triposr/examples/robot.png');
const bad=await fetch(api+'/v1/generate',{method:'POST',headers:{'Content-Type':'image/png'},body:image});assert.equal(bad.status,401);
const invalid=await fetch(api+'/v1/generate',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'text/plain'},body:'x'});assert.equal(invalid.status,415);
const http=createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(fs.readFileSync('Forge_R70_29_AI_Connected.html'))});await new Promise(r=>http.listen(8766,'127.0.0.1',r));
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
try{
 const ctx=await browser.newContext({viewport:{width:800,height:360},isMobile:true,hasTouch:true,acceptDownloads:true});const page=await ctx.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));page.on('dialog',d=>d.type()==='prompt'?d.accept(d.message().includes('adres')?api:token):d.accept());
 await page.goto('http://127.0.0.1:8766');await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
 const responsePromise=page.waitForResponse(r=>r.url()===api+'/v1/generate'&&r.request().method()==='POST',{timeout:330000});
 await page.locator('#forgeAiImage').setInputFiles({name:'robot.png',mimeType:'image/png',buffer:image});
 const response=await responsePromise;assert.equal(response.status(),200);const data=await response.body();fs.writeFileSync(dir+'/real-generated-raw.glb',data);const validation=await validator.validateBytes(data);assert.equal(validation.issues.numErrors,0);
 await page.waitForFunction(()=>parts[0]?.type==='aiMesh',null,{timeout:120000});
 const result=await page.evaluate(b64=>{const raw=parseForgeAiGLB(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)).buffer),p=parts[0],a=raw.geometry.v,b=p.geometry.v;return {triangles:mesh(parts).pos.length/9,rendered:three.renderer.info.render.triangles,overflow:document.documentElement.scrollWidth>innerWidth,axisCorrect:a.every((v,i)=>Math.abs(v-b[i-i%3+(i%3+2)%3])<1e-6),normalCorrect:raw.geometry.n.every((v,i)=>Math.abs(v-p.geometry.n[i-i%3+(i%3+2)%3])<1e-6)}},data.toString('base64'));
 assert.equal(result.triangles,result.rendered);assert.ok(result.triangles>100&&!result.overflow&&result.axisCorrect&&result.normalCorrect);assert.deepEqual(errors,[]);
 for(const view of ['front','side','back']){await page.locator('#quickCamera [data-action='+view+']').click();await page.screenshot({path:dir+'/'+view+'.png'})}
 const report={actualUpload:true,actualInference:true,httpStatus:response.status(),authRejected:bad.status,invalidRejected:invalid.status,bytes:data.length,...result,glbErrors:validation.issues.numErrors,glbWarnings:validation.issues.numWarnings,errors,requests:requests.filter(s=>/^https?:/.test(s)).map(s=>new URL(s).origin)};
 fs.writeFileSync(dir+'/report.json',JSON.stringify(report,null,2));console.log(report);
}finally{await browser.close();http.close()}
