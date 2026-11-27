import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {chromium} from 'playwright';
import {NodeIO} from '@gltf-transform/core';
const require=createRequire(import.meta.url),validator=require('gltf-validator');
const dir=path.resolve('studio/r70-surface-lab'),out=path.join(dir,'m2m-qa'),dep=path.join(dir,'deps/mesh2motion');
fs.mkdirSync(out,{recursive:true});
const bundle=await build({entryPoints:[path.join(dir,'m2m_browser.js')],bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const pageCode=bundle.outputFiles[0].text;
const target=fs.readFileSync(path.join(dir,'rig-qa/anatomy-skin.glb'));
const asset=path.join(dep,'static/assets/human');
const names={idle:'idle-a',walk:'walk',attack:'punch-cross',hurt:'hit-chest',death:'death-a'};
const enc=f=>fs.readFileSync(f).toString('base64');
const input={target:target.toString('base64'),source:enc(path.join(asset,'model.glb')),clips:Object.fromEntries(Object.entries(names).map(([k,v])=>[k,enc(path.join(asset,'animations',v+'.glb'))]))};
const b=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
try{
 const ctx=await b.newContext({viewport:{width:800,height:480},offline:true});
 const page=await ctx.newPage(),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});
 await page.setContent('<style>body{margin:0;background:#17212c;color:white;font:16px sans-serif}#label{height:30px;padding-left:12px;line-height:30px}</style><div id="label">Forge motion QA</div>');
 await page.addScriptTag({content:pageCode});
 const retarget=await page.evaluate(input=>window.forgeRetarget(input),input);
 const io=new NodeIO(),doc=await io.readBinary(new Uint8Array(target)),buffer=doc.getRoot().listBuffers()[0];
 const nodes=new Map(doc.getRoot().listNodes().map(n=>[n.getName(),n]));
 assert.equal(retarget.clips.length,5);
 const report={source:'Mesh2Motion calibrated anatomical segment axes + CC0 clip library',sourceCommit:'2609e0345371763c4c390f751d79021285da04b1',clips:[],sourceBones:retarget.sourceBones,targetBones:retarget.targetBones};
 for(const c of retarget.clips){
  const a=doc.createAnimation(c.name);
  for(const t of c.tracks){
   const n=nodes.get(t.name);assert.ok(n,t.name);
   const inp=doc.createAccessor().setType('SCALAR').setArray(new Float32Array(t.times)).setBuffer(buffer);
   const values=new Float32Array(t.values);
   if(t.type==='quaternion')for(let k=0;k<values.length;k+=4){
    const len=Math.hypot(...values.subarray(k,k+4));assert.ok(len>.1&&Number.isFinite(len));for(let j=0;j<4;j++)values[k+j]/=len;
    if(k&&values.subarray(k,k+4).reduce((s,v,j)=>s+v*values[k-4+j],0)<0)for(let j=0;j<4;j++)values[k+j]*=-1;
   }
   const o=doc.createAccessor().setType(t.type==='quaternion'?'VEC4':'VEC3').setArray(values).setBuffer(buffer);
   const sampler=doc.createAnimationSampler().setInput(inp).setOutput(o).setInterpolation('LINEAR');
   a.addSampler(sampler).addChannel(doc.createAnimationChannel().setSampler(sampler).setTargetNode(n).setTargetPath(t.type==='quaternion'?'rotation':'translation'));
  }
  report.clips.push({name:c.name,duration:c.duration,tracks:c.tracks.length,maxGroundCorrection:c.maxGroundCorrection});
 }
 const bytes=await io.writeBinary(doc);
 fs.writeFileSync(path.join(out,'anatomy-mesh2motion.glb'),bytes);
 const vr=await validator.validateBytes(bytes,{uri:'anatomy-mesh2motion.glb'});
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(vr,null,2));
 report.validation={errors:vr.issues.numErrors,warnings:vr.issues.numWarnings};assert.equal(vr.issues.numErrors,0);
 report.preview=await page.evaluate(b=>window.forgeLoadPreview(b),Buffer.from(bytes).toString('base64'));
 report.frames=[];
 for(const name of [...Object.keys(names),...Object.keys(names).map(x=>'m2m_'+x)]){
  for(const fraction of [.1,.25,.45,.65,.85,.98]){
   const frame=await page.evaluate(([name,t])=>window.forgeFrame(name,t,0),[name,fraction]);
   assert.ok(frame.finite&&frame.vertices>0&&frame.maxRadiusOverHeight<3,'Exploding/nonfinite mesh '+name);assert.equal(frame.clippedVertices,0,'Visual clipping '+name);
   if(name.startsWith('m2m_'))assert.ok(Math.abs(frame.groundOffset)<.012,'Ground residual '+name+' '+frame.groundOffset);
   await page.screenshot({path:path.join(out,name+'-'+fraction+'-front.png')});
   if(fraction===.65){const side=await page.evaluate(name=>window.forgeFrame(name,.65,Math.PI/2),name);assert.equal(side.clippedVertices,0,'Side clipping '+name);await page.screenshot({path:path.join(out,name+'-side.png')})}
   report.frames.push({name,fraction,...frame});
  }
 }
 report.pageErrors=errors;report.network=network;
 report.note='Offline desktop Chromium: numerical bounds and screenshots only. No human visual acceptance, self-intersection, UV textures, real Android or full editor integration.';
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
}finally{await b.close()}
