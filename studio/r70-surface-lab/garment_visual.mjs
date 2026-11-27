import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const require=createRequire(import.meta.url);
const base=path.resolve('studio/r70-surface-lab');
const p=await require(path.join(base,'build/forge_pmp.cjs'))();
const out=path.join(base,'build/visual');
fs.mkdirSync(out,{recursive:true});
function cross(a,b,c,pos){
 const u=[0,1,2].map(k=>pos[b*3+k]-pos[a*3+k]),v=[0,1,2].map(k=>pos[c*3+k]-pos[a*3+k]);
 return [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
}
function analyze(q,p){
 const a=new Float32Array(q.position),ix=new Uint32Array(q.index),old=new Float32Array(q.normal);
 const ap=p._malloc(a.byteLength),ip=p._malloc(ix.byteLength);
 if(!ap||!ip){if(ap)p._free(ap);if(ip)p._free(ip);throw Error('allocation failed')}
 let after,code;
 try{p.HEAPF32.set(a,ap/4);p.HEAPU32.set(ix,ip/4);code=p._forge_smooth(ap,a.length/3,ip,ix.length,1,.0025);after=p.HEAPF32.slice(ap/4,ap/4+a.length)}
 finally{p._free(ap);p._free(ip)}
 if(code!==0)return {name:q.name,accepted:false,code};
 const edges=new Map(),normal=new Float32Array(a.length);let maxMove=0,flips=0,degenerate=0;
 for(let k=0;k<ix.length;k+=3){
  const [i,j,l]=ix.slice(k,k+3),before=cross(i,j,l,a),n=cross(i,j,l,after);
  const len=Math.hypot(...n),prev=Math.hypot(...before);
  if(!Number.isFinite(len)||len<1e-10||len<prev*.15)degenerate++;
  if(before.reduce((s,x,k)=>s+x*n[k],0)<=0)flips++;
  for(const u of [i,j,l])for(let k=0;k<3;k++)normal[3*u+k]+=n[k];
  for(const [u,v] of [[i,j],[j,l],[l,i]]){let key=u<v?u+':'+v:v+':'+u;edges.set(key,(edges.get(key)||0)+1)}
 }
 let boundaryMoved=0,nonmanifoldEdges=0;
 for(const [key,count] of edges){if(count>2)nonmanifoldEdges++;if(count===1)for(const u of key.split(':').map(Number))if(a.slice(u*3,u*3+3).some((x,k)=>x!==after[u*3+k]))boundaryMoved++}
 for(let i=0;i<a.length;i+=3){
  maxMove=Math.max(maxMove,Math.hypot(...[0,1,2].map(k=>after[i+k]-a[i+k])));
  let len=Math.hypot(...normal.slice(i,i+3)),dot=normal.slice(i,i+3).reduce((s,x,k)=>s+x*old[i+k],0);
  for(let k=0;k<3;k++)normal[i+k]=len>1e-12?normal[i+k]*(dot<0?-1:1)/len:old[i+k];
 }
 const accepted=after.every(Number.isFinite)&&normal.every(Number.isFinite)&&maxMove<=.002501&&!flips&&!degenerate&&!boundaryMoved&&!nonmanifoldEdges;
 const stats={name:q.name,accepted,code,triangles:ix.length/3,maxMove,flips,degenerate,boundaryMoved,nonmanifoldEdges};
 return accepted?{...stats,position:Array.from(after),normal:Array.from(normal)}:stats;
}
const browser=await chromium.launch({headless:true,args:['--allow-file-access-from-files','--enable-unsafe-swiftshader']});
try{
 const ctx=await browser.newContext({viewport:{width:800,height:360},offline:true,deviceScaleFactor:1,hasTouch:true,isMobile:true});
 const page=await ctx.newPage(),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
 await page.goto(pathToFileURL(path.resolve('Forge_R70_17_Offline_3D_Modeler.html')).href);
 await page.waitForFunction(()=>typeof sourceModel==='function');
 await page.locator('#quickThree').click();await page.waitForFunction(()=>threeEnabled);
 await page.locator('#leftToggle').click();await page.locator('#mhOutfit').click();await page.locator('#leftToggle').click();
 async function views(prefix){for(const view of ['front','side','back']){await page.locator('#quickCamera [data-action='+view+']').click();await page.screenshot({path:path.join(out,prefix+'_'+view+'.png')})}}
 await views('before');
 const pieces=await page.evaluate(()=>[...sourceModel('anatomy')].filter(([name])=>name.startsWith('outfit.')).map(([name,q])=>({name,position:[...q.m.position],index:[...q.m.index],normal:[...q.m.normal]})));
 assert.equal(pieces.length,7);
 const nodeResults=pieces.map(q=>analyze(q,p));
 // Load the same self-contained WASM build inside the offline browser.
 // Each CJS bundle is scoped independently; only its factory is exposed.
 for(const [file,key] of [['forge_pmp.cjs','__forgePmpFactory'],['forge_mc33.cjs','__forgeMcFactory']]){
  const code=fs.readFileSync(path.join(base,'build',file),'utf8');
  await page.addScriptTag({content:'(()=>{const module={exports:{}};const exports=module.exports;\n'+code+'\n;globalThis.'+key+'=module.exports;})();'});
 }
 await page.addScriptTag({content:cross.toString()+'\n'+analyze.toString()+'\n;globalThis.__forgeAnalyze=analyze;'});
 const start=Date.now();
 const result=await page.evaluate(async pieces=>{
  const t0=performance.now(),p=await globalThis.__forgePmpFactory(),m=await globalThis.__forgeMcFactory();
  const initMs=performance.now()-t0,t1=performance.now();
  const results=pieces.map(q=>globalThis.__forgeAnalyze(q,p));
  const smoothMs=performance.now()-t1;
  const n=24,d=new Float32Array(n*n*n);
  for(let z=0,k=0;z<n;z++)for(let y=0;y<n;y++)for(let x=0;x<n;x++,k++)d[k]=(x-11.5)**2+(y-11.5)**2+(z-11.5)**2-64;
  const dp=m._malloc(d.byteLength);if(!dp)throw Error('MC33 allocation failed');
  let mc;
  try{
   m.HEAPF32.set(d,dp/4);const t2=performance.now(),code=m._forge_mc_extract(dp,n,n,n,0);
   const vertices=m._forge_mc_vertices(),triangles=m._forge_mc_triangles();
   const ix=m.HEAPU32.slice(m._forge_mc_indices()/4,m._forge_mc_indices()/4+3*triangles);
   const pos=m.HEAPF32.slice(m._forge_mc_positions()/4,m._forge_mc_positions()/4+3*vertices);
   const edges=new Map();
   for(let i=0;i<ix.length;i+=3)for(let j=0;j<3;j++){let a=ix[i+j],b=ix[i+(j+1)%3],key=a<b?a+':'+b:b+':'+a;edges.set(key,(edges.get(key)||0)+1)}
   mc={code,vertices,triangles,finite:pos.every(Number.isFinite),validIndices:ix.every(x=>x<vertices),closedEdges:[...edges.values()].every(x=>x===2),extractMs:performance.now()-t2};
  }finally{m._forge_mc_clear();m._free(dp)}
  return {results,mc,initMs,smoothMs,heapBytes:{pmp:p.HEAPF32.buffer.byteLength,mc33:m.HEAPF32.buffer.byteLength}};
 },pieces);
 const {results,mc,initMs,smoothMs,heapBytes}=result;
 assert.equal(mc.code,0);assert.ok(mc.vertices>0&&mc.triangles>0&&mc.finite&&mc.validIndices&&mc.closedEdges);
 // Both runs execute the same WASM; compare acceptance and actual position data.
 assert.equal(results.length,nodeResults.length);
 for(let i=0;i<results.length;i++){assert.equal(results[i].accepted,nodeResults[i].accepted);if(results[i].accepted)assert.deepEqual(results[i].position,nodeResults[i].position)}
 const browserWasm={mc,initMs,smoothMs,heapBytes,roundTripMs:Date.now()-start,parity:true};
 await page.evaluate(results=>{const src=sourceModel('anatomy');for(const q of results)if(q.accepted){const m=src.get(q.name).m;m.position.set(q.position);m.normal.set(q.normal)}refresh()},results);
 await views('after');
 const model=await page.evaluate(()=>({triangles:mesh(parts).pos.length/9,rendered:three.renderer.info.render.triangles,parts:parts.length}));
 assert.equal(model.triangles,model.rendered);assert.equal(model.parts,10);assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 const report={model,errors,requests,browserWasm,acceptedParts:results.filter(x=>x.accepted).length,parts:results.map(({position,normal,...r})=>r),note:'Node and offline Chromium WASM parity plus visual comparison. Desktop headless timings and WASM heap, not physical Android performance; not self-intersection proof or visual acceptance.'};
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 // Fail when the real input cannot be safely processed, but retain visual evidence.
 assert.ok(report.acceptedParts>0,'No garment passed geometric guards');
}finally{await browser.close()}
