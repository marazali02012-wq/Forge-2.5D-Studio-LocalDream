import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {Document,NodeIO} from '@gltf-transform/core';
const require=createRequire(import.meta.url);
const validator=require('gltf-validator');
const dir=path.resolve('studio/r70-surface-lab/asset-qa');
fs.mkdirSync(dir,{recursive:true});
const html=fs.readFileSync('Forge_R70_17_Offline_3D_Modeler.html','utf8');
const js=html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>'));
const {mesh,outfitParts}=new Function('const self=globalThis;\n'+js.split('let parts=[],selected')[0]+';return {mesh,outfitParts}')();
const validate=async(bytes,name)=>{
 fs.writeFileSync(path.join(dir,name+'.glb'),bytes);
 const r=await validator.validateBytes(new Uint8Array(bytes),{uri:name+'.glb'});
 fs.writeFileSync(path.join(dir,name+'.validation.json'),JSON.stringify(r,null,2));
 assert.equal(r.issues.numErrors,0,name+' failed Khronos validator');
 return {errors:r.issues.numErrors,warnings:r.issues.numWarnings};
};
// Real Watlas runtime from the existing pinned local vendor directory.
fs.copyFileSync('vendor/watlas/watlas.js',path.join(dir,'watlas.mjs'));
fs.copyFileSync('vendor/watlas/watlas.wasm',path.join(dir,'watlas.wasm'));
const w=await import(pathToFileURL(path.join(dir,'watlas.mjs')).href);
await w.Initialize();
function indexed(m){
 const map=new Map(),pos=[],nor=[],col=[],ix=[];
 for(let i=0;i<m.pos.length;i+=3){
  const a=[...m.pos.slice(i,i+3),...m.nor.slice(i,i+3),...m.col.slice(i,i+3)];
  const key=a.map(x=>Math.round(x*1e6)).join(',');
  let id=map.get(key);if(id===undefined){id=pos.length/3;map.set(key,id);pos.push(...a.slice(0,3));nor.push(...a.slice(3,6));col.push(...a.slice(6,9))}
  ix.push(id);
 }
 return {position:new Float32Array(pos),normal:new Float32Array(nor),color:new Float32Array(col),index:new Uint32Array(ix)};
}
const doc=new Document(),buf=doc.createBuffer(),scene=doc.createScene('Forge anatomy UV QA');
const report={parts:[],rig:null};const parts=outfitParts('normal');
// Reuse actual older 26-joint animation exporter; separate procedural reference model.
for(const f of ['f3d_math.js','f3d_rig.js','f3d_mesh.js','future-reference/f3d_anim.js','future-reference/f3d_glb.js'])new Function(fs.readFileSync(path.join('studio/r70-reference',f),'utf8'))();
const F=globalThis.Forge3D,rig=F.buildSkeleton(),warrior=F.buildWarriorMesh(rig,{}, {},7);
const animated=F.exportGLB(rig,warrior,{fps:30});
const own=F.verifyGLB(animated);assert.equal(own.ok,true,JSON.stringify(own.errors));assert.equal(rig.bones.length,26);
const re=F.characterFromGLB(animated);assert.deepEqual(Object.keys(re.anim).sort(),['attack','death','hurt','idle','walk']);
const clips={};for(const [name,a] of Object.entries(re.anim)){const pose0=re.samplePose(name,0),pose1=re.samplePose(name,a.duration*.45);assert.ok(pose1.rot.flat().every(Number.isFinite));assert.ok(pose1.trans.flat().every(Number.isFinite));let diff=pose1.rot.flat().reduce((s,v,k)=>s+Math.abs(v-pose0.rot.flat()[k]),0);assert.ok(diff>1e-6,name+' has no rotation');clips[name]={duration:a.duration,channels:a.channels.length,rotationDelta:diff}}
report.rig={source:'legacy procedural warrior, not anatomical garment mesh',joints:rig.bones.length,clips,validation:await validate(animated,'legacy-warrior-rig'),ownStats:own.stats};

fs.writeFileSync(path.join(dir,'rig-report.json'),JSON.stringify(report.rig,null,2));
for(const p of parts){
 const m=indexed(mesh([p]));const atlas=new w.Atlas();
 try{
  atlas.addMesh({vertexPositionData:m.position,vertexCount:m.position.length/3,vertexPositionStride:12,indexData:m.index,indexCount:m.index.length});
  atlas.generate({},{resolution:512,padding:2,bilinear:true});
  assert.equal(atlas.atlasCount,1,p.name+' multi-atlas not supported');assert.ok(atlas.width>0&&atlas.height>0);
  const o=atlas.getMesh(0),i=new Uint32Array(o.indexCount);o.getIndexArray(i);
  const pos=new Float32Array(o.vertexCount*3),norm=new Float32Array(pos.length),col=new Float32Array(pos.length),uv=new Float32Array(o.vertexCount*2),assigned=new Uint8Array(o.vertexCount);
  for(let k=0;k<o.vertexCount;k++){const v=o.getVertex(k);assert.ok(v.xref>=0&&v.xref<m.position.length/3);assert.ok(v.atlasIndex===0||v.atlasIndex===-1);assigned[k]=v.atlasIndex===0?1:0;pos.set(m.position.subarray(v.xref*3,v.xref*3+3),k*3);norm.set(m.normal.subarray(v.xref*3,v.xref*3+3),k*3);col.set(m.color.subarray(v.xref*3,v.xref*3+3),k*3);if(assigned[k])uv.set([v.uv[0]/atlas.width,v.uv[1]/atlas.height],k*2)}
  assert.equal(i.length,m.index.length);assert.ok(i.every(x=>x<o.vertexCount));assert.ok(uv.every(x=>Number.isFinite(x)&&x>=0&&x<=1));
  // xatlas deliberately returns atlasIndex -1 for ignored faces. Keep them
  // in a separate untextured primitive; do not fabricate successful UVs.
  let degenerateUV=0,unassigned=0,unassignedZeroArea=0;
  const good=[],bad=[];
  for(let k=0;k<i.length;k+=3){
   const [a,b,c]=i.slice(k,k+3),abc=[a,b,c];
   if(!abc.every(v=>assigned[v])){
    unassigned++;bad.push(...abc);
    const u=[0,1,2].map(j=>pos[3*b+j]-pos[3*a+j]),v=[0,1,2].map(j=>pos[3*c+j]-pos[3*a+j]);
    if(Math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])<1e-9)unassignedZeroArea++;
    continue;
   }
   const x=uv[b*2]-uv[a*2],y=uv[b*2+1]-uv[a*2+1],u=uv[c*2]-uv[a*2],v=uv[c*2+1]-uv[a*2+1];
   if(Math.abs(x*v-y*u)<1e-12){degenerateUV++;bad.push(...abc)}else good.push(...abc);
  }
  assert.equal(good.length+bad.length,i.length);
  const mat=doc.createMaterial(p.name).setMetallicFactor(0).setRoughnessFactor(.8).setDoubleSided(true);
  const glmesh=doc.createMesh(p.name);
  function emit(indices,withUV){
   if(!indices.length)return;
   const map=new Map(),P=[],N=[],C=[],U=[],I=[];
   for(const id of indices){let k=map.get(id);if(k===undefined){k=map.size;map.set(id,k);P.push(...pos.subarray(id*3,id*3+3));N.push(...norm.subarray(id*3,id*3+3));C.push(...col.subarray(id*3,id*3+3));if(withUV)U.push(...uv.subarray(id*2,id*2+2))}I.push(k)}
   const acc=(name,type,data)=>doc.createAccessor(name).setType(type).setArray(data).setBuffer(buf);
   const prim=doc.createPrimitive().setAttribute('POSITION',acc('POSITION','VEC3',new Float32Array(P))).setAttribute('NORMAL',acc('NORMAL','VEC3',new Float32Array(N))).setAttribute('COLOR_0',acc('COLOR_0','VEC3',new Float32Array(C))).setIndices(acc('indices','SCALAR',map.size>65535?new Uint32Array(I):new Uint16Array(I)));
   if(withUV)prim.setAttribute('TEXCOORD_0',acc('TEXCOORD_0','VEC2',new Float32Array(U)));
   prim.setMaterial(mat);glmesh.addPrimitive(prim);
  }
  emit(good,true);emit(bad,false);scene.addChild(doc.createNode(p.name).setMesh(glmesh));
  report.parts.push({name:p.name,triangles:i.length/3,uvTriangles:good.length/3,untexturedTriangles:bad.length/3,unassigned,unassignedZeroArea,verticesBefore:m.position.length/3,verticesAfter:o.vertexCount,atlas:[atlas.width,atlas.height],charts:o.chartCount,degenerateUV});
  fs.writeFileSync(path.join(dir,'uv-progress.json'),JSON.stringify(report.parts,null,2));

 }finally{atlas.delete()}
}
report.uvValidation=await validate(await new NodeIO().writeBinary(doc),'anatomy-uv-static');
report.uvTriangles=report.parts.reduce((a,p)=>a+p.triangles,0);
assert.equal(report.uvTriangles,42877);
assert.equal(report.parts.length,10);
report.uvMappedTriangles=report.parts.reduce((a,p)=>a+p.uvTriangles,0);
report.uvUnmappedTriangles=report.uvTriangles-report.uvMappedTriangles;
report.uvComplete=report.uvUnmappedTriangles===0;
report.note='Real UV attributes on static current anatomy; unassigned and degenerate UV faces preserved in untextured primitives. No baked textures or overlap proof. Separate legacy rig export and numeric clip motion test, no current anatomy skin/animation visual or phone test.';
fs.writeFileSync(path.join(dir,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
assert.ok(report.uvMappedTriangles>0,'UV output empty');
if(!report.uvComplete)console.warn('UV quality gate OPEN: '+report.uvUnmappedTriangles+' triangles without valid atlas coordinates');
