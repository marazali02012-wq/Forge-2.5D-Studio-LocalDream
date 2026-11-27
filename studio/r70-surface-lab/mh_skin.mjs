import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {Document,NodeIO} from '@gltf-transform/core';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),validator=require('gltf-validator');
const dir=path.resolve('studio/r70-surface-lab/rig-qa');
fs.mkdirSync(dir,{recursive:true});
const raw=fs.readFileSync('vendor/makehuman/base.obj','utf8').split(/\r?\n/).filter(l=>/^v\s/.test(l)).map(l=>l.trim().split(/\s+/).slice(1,4).map(Number));
const data=JSON.parse(fs.readFileSync(path.join(dir,'default_weights.mhw'),'utf8'));
const official=JSON.parse(fs.readFileSync(path.join(dir,'default.mhskel'),'utf8'));
assert.equal(data.license,'CC0');assert.equal(official.license,'CC0');
for(const v of raw)assert.ok(v.every(Number.isFinite));
const Ffiles=['f3d_math.js','f3d_rig.js'];
for(const f of Ffiles)new Function(fs.readFileSync(path.join('studio/r70-reference',f),'utf8'))();
const F=globalThis.Forge3D,names=F.BONES.map(b=>b[0]),ids=new Map(names.map((n,i)=>[n,i]));
assert.equal(names.length,26);
const map=new Map([['root','root'],['spine05','hips'],['spine04','hips'],['spine03','spine'],['spine02','chest'],['spine01','chest'],['neck01','neck'],['neck02','neck'],['neck03','neck'],['head','head']]);
for(const s of ['L','R']){
 for(const [a,b] of [['pelvis','hips'],['clavicle','shoulder'],['shoulder01','shoulder'],['upperarm01','upperarm'],['upperarm02','upperarm'],['lowerarm01','forearm'],['lowerarm02','forearm'],['wrist','hand'],['upperleg01','thigh'],['upperleg02','thigh'],['lowerleg01','shin'],['lowerleg02','shin'],['foot','foot']])map.set(a+'.'+s,b==='hips'?b:b+'.'+s);
}
function mapped(b){
 if(map.has(b))return ids.get(map.get(b));
 if(/^toe/.test(b))return ids.get('toe.'+b.slice(-1));
 if(/^(finger|metacarpal)/.test(b))return ids.get('hand.'+b.slice(-1));
 if(/^(eye|jaw|tongue|oculi|oris|orbicularis|temporalis|risorius|levator)/.test(b))return ids.get('head');
 let p=official.bones[b]?.parent;if(p)return mapped(p);throw Error('Unmapped source bone '+b);
}
const weights=Array.from({length:raw.length},()=>new Float64Array(26));
for(const [bone,list] of Object.entries(data.weights)){
 const j=mapped(bone);assert.ok(Number.isInteger(j));
 for(const [i,w] of list){assert.ok(Number.isInteger(i)&&i>=0&&i<raw.length&&Number.isFinite(w)&&w>=0);weights[i][j]+=w}
}
const grid=new Map(),key=v=>v.map(x=>Math.round(x*1e6)).join(',');
const scaled=raw.map(v=>v.map(x=>x*.145));
for(let i=0;i<raw.length;i++){const k=key(scaled[i]);if(!grid.has(k))grid.set(k,[]);grid.get(k).push(i)}
function lookup(v){
 let k=v.map(x=>Math.round(x*1e6)),c=[];
 for(let x=-1;x<=1;x++)for(let y=-1;y<=1;y++)for(let z=-1;z<=1;z++)for(const id of grid.get([k[0]+x,k[1]+y,k[2]+z].join(','))||[])if(Math.hypot(...scaled[id].map((a,i)=>a-v[i]))<=1.6e-6)c.push(id);
 if(!c.length)throw Error('No exact source vertex match '+v.join(','));
 const first=weights[c[0]],sum=first.reduce((s,x)=>s+x,0);
 if(sum<=0)throw Error('Source vertex has no official weight: '+c[0]);
 for(const i of c){const w=weights[i],s=w.reduce((a,b)=>a+b,0);if(s<=0||w.some((x,j)=>Math.abs(x/s-first[j]/sum)>1e-5))throw Error('Ambiguous coincident vertex weights '+c.join(','))}
 return Array.from(first,x=>x/sum);
}
let html=fs.readFileSync('Forge_R70_17_Offline_3D_Modeler.html','utf8');
let js=html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>')).split('let parts=[],selected')[0];
function patch(a,b){assert.ok(js.includes(a),'source patch anchor missing: '+a.slice(0,70));js=js.replace(a,b)}
// Preserve barycentric weights through the original polygon clipping pipeline.
patch('const {position,index,normal}=body.m,scale=.145,output=new Map();','const {position,index,normal}=body.m,scale=.145,output=new Map(),sourceWeights=Array.from({length:position.length/3},(_,i)=>lookup(Array.from(position.slice(i*3,i*3+3))));body.m.rigWeights=sourceWeights;');
patch('const pos=[],nor=[],col=[],idx=[],lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity],map=new Map();','const pos=[],nor=[],col=[],idx=[],lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity],map=new Map(),rigWeights=[];');
patch('const id=pos.length/3;map.set(key,id);pos.push(...p);nor.push(...n);col.push(...spec.color);','const id=pos.length/3;map.set(key,id);pos.push(...p);nor.push(...n);col.push(...spec.color);rigWeights.push(a.slice(6));');
patch('return [...position.slice(j,j+3),...normal.slice(j,j+3)]','return [...position.slice(j,j+3),...normal.slice(j,j+3),...sourceWeights[index[i+k]]]');
patch('color:new Float32Array(col),index:new Uint32Array(idx)},p:{istart:0,iend:idx.length}','color:new Float32Array(col),index:new Uint32Array(idx),rigWeights},p:{istart:0,iend:idx.length}');
const api=new Function('lookup','const self=globalThis;\n'+js+';return {sourceModel,outfitParts}')(lookup);
const parts=api.outfitParts('normal'),source=api.sourceModel('anatomy'),body=source.get('human.body');
const bp=parts[0],world=v=>v.map((x,i)=>(x-body.center[i])*bp.s[i]+bp.t[i]);
const sourceJoint={root:'root',hips:'spine05',spine:'spine03',chest:'spine01',neck:'neck01',head:'head'};
for(const s of ['L','R'])for(const [name,b] of [['shoulder','clavicle'],['upperarm','upperarm01'],['forearm','lowerarm01'],['hand','wrist'],['thigh','upperleg01'],['shin','lowerleg01'],['foot','foot'],['toe','toe1-1']])sourceJoint[name+'.'+s]=b+'.'+s;
const jointHead=name=>{
 const joint=official.joints[official.bones[name].head];assert.ok(joint?.length);
 return world([0,1,2].map(k=>joint.reduce((a,i)=>a+scaled[i][k],0)/joint.length));
};
const pos=names.map(n=>sourceJoint[n]?jointHead(sourceJoint[n]):null);
pos[ids.get('weapon')]=pos[ids.get('hand.R')].slice();pos[ids.get('shield')]=pos[ids.get('hand.L')].slice();pos[ids.get('cape.1')]=pos[ids.get('chest')].slice();pos[ids.get('cape.2')]=pos[ids.get('hips')].slice();
const doc=new Document(),buf=doc.createBuffer(),scene=doc.createScene('Anatomy skin test');
const bones=names.map((n,i)=>doc.createNode(n).setTranslation(pos[i].map((x,k)=>x-(F.BONES[i][1]<0?0:pos[F.BONES[i][1]][k]))));
F.BONES.forEach((b,i)=>{if(b[1]<0)scene.addChild(bones[i]);else bones[b[1]].addChild(bones[i])});
const ibm=new Float32Array(26*16);for(let i=0;i<26;i++){let k=i*16;ibm[k]=ibm[k+5]=ibm[k+10]=ibm[k+15]=1;for(let j=0;j<3;j++)ibm[k+12+j]=-pos[i][j]}
const acc=(name,type,array)=>doc.createAccessor(name).setType(type).setArray(array).setBuffer(buf);
const skin=doc.createSkin('MakeHuman CC0 reduced 26').setSkeleton(bones[0]).setInverseBindMatrices(acc('IBM','MAT4',ibm));bones.forEach(b=>skin.addJoint(b));
const report={sourceVertices:raw.length,bodyVertices:body.m.position.length/3,parts:[],joints:names,skinOnly:true};
let maxDropped=0,maxSumError=0;
for(const p of parts){
 const q=source.get(p.name),m=q.m,n=m.position.length/3,positions=new Float32Array(n*3),normals=new Float32Array(n*3),color=new Float32Array(n*3),joints=new Uint16Array(n*4),wts=new Float32Array(n*4);
 for(let i=0;i<n;i++){
  positions.set(Array.from(m.position.slice(i*3,i*3+3), (x,k)=>(x-q.center[k])*p.s[k]+p.t[k]),i*3);
  const no=Array.from(m.normal.slice(i*3,i*3+3),(x,k)=>x/p.s[k]),len=Math.hypot(...no)||1;normals.set(no.map(x=>x/len),i*3);
  color.set(Array.from(m.color.slice(i*3,i*3+3),x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4),i*3);
  const ww=m.rigWeights?.[i]|| (p.name.startsWith('human.eye.')?names.map(x=>x==='head'?1:0):null);
  assert.ok(ww&&ww.length===26,p.name+' no weights');
  const order=ww.map((w,j)=>[j,w]).sort((a,b)=>b[1]-a[1]),sum=order.slice(0,4).reduce((s,x)=>s+x[1],0),total=ww.reduce((s,x)=>s+x,0);
  assert.ok(sum>0&&Number.isFinite(sum)&&total>0);
  maxDropped=Math.max(maxDropped,1-sum/total);
  for(let j=0;j<4;j++){joints[i*4+j]=order[j][0];wts[i*4+j]=order[j][1]/sum}
  maxSumError=Math.max(maxSumError,Math.abs(wts.slice(i*4,i*4+4).reduce((s,x)=>s+x,0)-1));
 }
 const primitive=doc.createPrimitive().setAttribute('POSITION',acc('position','VEC3',positions)).setAttribute('NORMAL',acc('normal','VEC3',normals)).setAttribute('COLOR_0',acc('color','VEC3',color)).setAttribute('JOINTS_0',acc('joint','VEC4',joints)).setAttribute('WEIGHTS_0',acc('weight','VEC4',wts)).setIndices(acc('index','SCALAR',m.index));
 primitive.setMaterial(doc.createMaterial(p.name).setDoubleSided(true).setMetallicFactor(0).setRoughnessFactor(.8));
 scene.addChild(doc.createNode(p.name).setMesh(doc.createMesh(p.name).addPrimitive(primitive)).setSkin(skin));
 report.parts.push({name:p.name,vertices:n,triangles:m.index.length/3,weightSource:p.name.startsWith('outfit.')?'clipped source triangle interpolation':p.name==='human.body'?'exact source coordinate match':'rigid head'});
}
assert.ok(maxSumError<1e-6);assert.equal(report.parts.length,10);
report.maxDroppedWeight=maxDropped;report.maxWeightSumError=maxSumError;report.note='Bind-pose skin candidate only; no animation, UV, collision, visual or Android approval. Source weights reduced to 26 joints and four influences. Accessory joints without geometry are placeholders.';
const glb=await new NodeIO().writeBinary(doc);fs.writeFileSync(path.join(dir,'anatomy-skin.glb'),glb);
const valid=await validator.validateBytes(glb,{uri:'anatomy-skin.glb'});report.validation={errors:valid.issues.numErrors,warnings:valid.issues.numWarnings};
fs.writeFileSync(path.join(dir,'validation.json'),JSON.stringify(valid,null,2));fs.writeFileSync(path.join(dir,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));assert.equal(valid.issues.numErrors,0);
