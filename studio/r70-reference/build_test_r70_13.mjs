import fs from 'node:fs';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const template=fs.readFileSync('studio/r70-reference/Forge_R70_13_template.html','utf8');
const runtime='vendor/manifold/runtime/';
const js=fs.readFileSync(runtime+'manifold.js'),wasm=fs.readFileSync(runtime+'manifold.wasm');
const html=template.replace('__FORGE_MANIFOLD_JS__',js.toString('base64')).replace('__FORGE_MANIFOLD_WASM__',wasm.toString('base64'));
fs.writeFileSync('Forge_R70_13_Offline_3D_Modeler.html',html);
fs.writeFileSync(runtime+'temp-test.mjs',js);
try {
 const {default:Module}=await import(pathToFileURL(resolve(runtime+'temp-test.mjs')));
 const mf=await Module({wasmBinary:wasm});mf.setup();
 const s=template.slice(template.indexOf('<script>')+8,template.lastIndexOf('</script>'));
 const api=new Function('const self=globalThis;\n'+s.split('let parts=[],selected')[0]+';return {mesh,glb,booleanSolid,manifoldInput,validPart,sourceParts,anatomyParts}')();
 const cube=(x=0)=>({type:'box',t:[x,1,0],s:[1,1,1],r:[0,0,0],color:'#8999ad'});
 const results=[];
 for(const [op,expected] of [['union',1.5],['difference',.5],['intersection',.5]]){
  const r=api.booleanSolid(cube(),cube(.5),op,mf);
  assert.ok(Math.abs(r.volume-expected)<1e-5,op+' volume');
  assert.ok(api.validPart(r.part));
  const solid=api.manifoldInput(JSON.parse(JSON.stringify(r.part)),mf);
  assert.equal(solid.status(),'NoError');assert.ok(Math.abs(solid.volume()-expected)<1e-5);solid.delete();
  const glb=api.glb(api.mesh([r.part]));assert.equal(new DataView(glb.buffer).getUint32(8,true),glb.length);
  results.push({op,volume:r.volume,triangles:r.triangles,glbBytes:glb.length});
 }
 const drill={type:'cylinder',t:[0,1,0],s:[.5,1.5,.5],r:[0,0,0],color:'#997744'};
 const hole=api.booleanSolid(cube(),drill,'difference',mf);
 assert.ok(hole.volume>.7&&hole.volume<.9);
 const checked=api.manifoldInput(hole.part,mf);assert.equal(checked.status(),'NoError');checked.delete();
 assert.throws(()=>api.booleanSolid(cube(),cube(3),'intersection',mf));
 assert.throws(()=>api.booleanSolid(api.sourceParts('knight')[0],cube(),'union',mf));
 assert.ok(api.mesh(api.sourceParts('knight')).pos.length>0);
 assert.ok(api.mesh(api.anatomyParts('head')).pos.length>0);
 results.push({op:'drill',volume:hole.volume,triangles:hole.triangles});
 fs.writeFileSync('studio/r70-reference/R70_13_boolean_results.json',JSON.stringify({results,hole:hole.part},null,2));
 console.log(JSON.stringify(results));
} finally {fs.rmSync(runtime+'temp-test.mjs',{force:true})}
