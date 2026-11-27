import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
let html=fs.readFileSync('studio/r70-reference/Forge_R70_15_template.html','utf8');
for(const [token,file] of Object.entries({'__FORGE_MANIFOLD_JS__':'vendor/manifold/runtime/manifold.js','__FORGE_MANIFOLD_WASM__':'vendor/manifold/runtime/manifold.wasm','__FORGE_THREE_CORE__':'vendor/three/three.core.min.js','__FORGE_THREE_MODULE__':'vendor/three/three.module.min.js'}))html=html.replace(token,fs.readFileSync(file).toString('base64'));
const out='Forge_R70_15_Offline_3D_Modeler.html';fs.writeFileSync(out,html);
const browser=await chromium.launch({headless:true,args:['--allow-file-access-from-files','--enable-unsafe-swiftshader']});
try{
 const ctx=await browser.newContext({viewport:{width:800,height:360},offline:true,deviceScaleFactor:1,hasTouch:true,isMobile:true});
 const page=await ctx.newPage(),errors=[],dialogs=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{dialogs.push(d.message());await d.accept()});page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
 await page.goto(pathToFileURL(resolve(out)).href);
 await page.waitForFunction(()=>typeof initThree==='function');
 const layout=await page.evaluate(()=>({canvas:[cv.clientWidth,cv.clientHeight],overflow:document.documentElement.scrollWidth>innerWidth,header:document.querySelector('header').clientHeight}));
 assert.ok(layout.canvas[0]>=780&&layout.canvas[1]>=300&&!layout.overflow);
 await page.screenshot({path:'studio/r70-reference/R70_15_old.png'});
 await page.locator('#leftToggle').click();assert.ok(await page.locator('#leftPanel').isVisible());
 await page.screenshot({path:'studio/r70-reference/R70_15_panel.png'});
 await page.locator('#rightToggle').click();assert.ok(await page.locator('#rightPanel').isVisible());assert.ok(!await page.locator('#leftPanel').isVisible());
 await page.locator('#rightToggle').click();assert.ok(!await page.locator('#rightPanel').isVisible());
 await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
 const initial=await page.evaluate(()=>({triangles:three.renderer.info.render.triangles,expected:mesh(parts).pos.length/9,revision:three.T.REVISION,canvas:[three.renderer.domElement.width,three.renderer.domElement.height],calls:three.renderer.info.render.calls}));
 assert.equal(initial.triangles,initial.expected);assert.ok(initial.calls>0);
 await page.screenshot({path:'studio/r70-reference/R70_15_three.png'});
 await page.locator('#quickCamera [data-action=side]').click();await page.screenshot({path:'studio/r70-reference/R70_15_side.png'});
 await page.locator('#quickCamera [data-action=back]').click();await page.screenshot({path:'studio/r70-reference/R70_15_back.png'});
 const regression=await page.evaluate(async()=>{
 const a={type:'box',t:[0,1,0],s:[1,1,1],r:[0,0,0],color:'#ffffff'},b={...a,t:[.5,1,0]};
 const solid=booleanSolid(a,b,'union',await getManifold());parts=[solid.part];selected=0;ui();refresh();
 return {volume:solid.volume,triangles:three.renderer.info.render.triangles,expected:solid.triangles,glbBytes:glb(mesh(parts)).length};
 });
 assert.ok(Math.abs(regression.volume-1.5)<1e-5);assert.equal(regression.triangles,regression.expected);
 await page.locator('#quickThree').click();assert.equal(await page.evaluate(()=>threeEnabled),false);assert.equal(await page.evaluate(()=>three===null),true);await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);assert.equal(await page.evaluate(()=>three.renderer.info.render.triangles),regression.expected);await page.locator('#quickThree').click();assert.equal(await page.evaluate(()=>three===null),true);
 assert.deepEqual(errors,[]);assert.deepEqual(dialogs,[]);assert.deepEqual(requests,[]);
 fs.writeFileSync('studio/r70-reference/R70_15_browser.json',JSON.stringify({layout,initial,regression,errors,dialogs,requests,offline:true,viewport:[800,360]},null,2));
 const views={};for(const name of ['old','three','side','back','panel'])views[name]=fs.readFileSync('studio/r70-reference/R70_15_'+name+'.png').toString('base64');fs.writeFileSync('studio/r70-reference/R70_15_visual.json',JSON.stringify(views));console.log({initial,regression});
}finally{await browser.close()}
