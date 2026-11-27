import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const browser=await chromium.launch({headless:true,args:['--allow-file-access-from-files','--enable-unsafe-swiftshader']});
try{
 const context=await browser.newContext({viewport:{width:800,height:360},offline:true,deviceScaleFactor:1,hasTouch:true,isMobile:true});
 const page=await context.newPage(),errors=[],dialogs=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{dialogs.push(d.message());await d.accept()});
 await page.goto(pathToFileURL(resolve('Forge_R70_13_Offline_3D_Modeler.html')).href);
 await page.waitForFunction(()=>typeof booleanSolid==='function');
 const data=await page.evaluate(async()=>{
  const api=await getManifold();
  const a={type:'box',t:[0,1.2,0],s:[1.2,1.2,1.2],r:[0,0,0],color:'#b48e56'};
  const b={type:'cylinder',t:[0,1.2,0],s:[.6,1.6,.6],r:[0,0,0],color:'#63747b'};
  const d=booleanSolid(a,b,'difference',api);parts=[d.part];selected=0;yaw=.65;pitch=.45;ui();refresh();
  return {triangles:d.triangles,volume:d.volume,webgl:!!gl,canvas:[cv.width,cv.height]};
 });
 assert.ok(data.webgl&&data.volume>0&&data.triangles>0);
 await page.screenshot({path:'studio/r70-reference/R70_13_browser.png'});
 assert.deepEqual(errors,[]);assert.deepEqual(dialogs,[]);
 fs.writeFileSync('studio/r70-reference/R70_13_browser.json',JSON.stringify({data,errors,dialogs,offline:true,viewport:[800,360]},null,2));
 console.log(data);
}finally{await browser.close()}
