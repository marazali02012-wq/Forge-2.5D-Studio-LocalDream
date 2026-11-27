import fs from 'node:fs';
import assert from 'node:assert/strict';
const html=fs.readFileSync('Forge_R70_12_Offline_3D_Modeler.html','utf8');
const script=html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>'));
const api=new Function('const self=globalThis;\n'+script.split('let parts=[],selected')[0]+';return {mesh,glb,sourceParts,anatomyParts,optimizeParts,MeshoptSimplifier}')();
assert.equal(api.MeshoptSimplifier.supported,true,'WebAssembly unavailable');
await api.MeshoptSimplifier.ready;
const results=[];
for(const [name,parts] of [['head',api.anatomyParts('head')],['hand',api.anatomyParts('L')],...['knight','ranger','guardian'].map(s=>[s,api.sourceParts(s)])]){
 const original=api.mesh(parts), reduced=api.optimizeParts(parts,api.MeshoptSimplifier);
 assert.ok(reduced.pos.length>0&&reduced.pos.length<=original.pos.length);
 assert.ok(reduced.pos.every(Number.isFinite)&&reduced.nor.every(Number.isFinite));
 const out=api.glb(reduced);assert.equal(new DataView(out.buffer).getUint32(8,true),out.length);
 results.push({name,before:original.pos.length/9,after:reduced.pos.length/9,glbBytes:out.length});
}
assert.ok(results.some(x=>x.after<x.before),'No real simplification was achieved');
console.log(JSON.stringify(results,null,2));
fs.writeFileSync('meshopt-results.json',JSON.stringify(results,null,2));
