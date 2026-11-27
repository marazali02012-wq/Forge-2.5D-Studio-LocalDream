import fs from 'node:fs';
let h=fs.readFileSync('studio/r70-reference/Forge_R70_16_template.html','utf8');
function rep(a,b){if(!h.includes(a))throw Error('missing '+a.slice(0,100));h=h.replace(a,b)}
// All distances below are expressed in original hm08 units (converted by 0.145).
rep('function anatomyModel(){',`function fittedGarments(body){
 const {position,index,normal}=body.m,scale=.145,output=new Map();
 const specs=[
  {name:"outfit.tunic",min:-.35,max:5.92,x:3.75,gap:.10,color:[.32,.40,.46]},
  {name:"outfit.trousers",min:-6.25,max:.30,x:3.10,gap:.075,color:[.29,.25,.21]},
  {name:"outfit.boots",min:-8.5,max:-5.95,x:3.25,gap:.13,color:[.23,.20,.18]},
  {name:"outfit.vest",min:1.55,max:5.22,x:1.80,gap:.23,color:[.58,.62,.65]},
  {name:"outfit.belt",min:.02,max:.40,x:2.20,gap:.21,color:[.50,.36,.18]},
  {name:"outfit.bracers.L",min:2.70,max:4.05,x:3.85,loX:2.85,gap:.17,color:[.57,.60,.63]},
  {name:"outfit.bracers.R",min:2.70,max:4.05,x:-2.85,loX:-3.85,gap:.17,color:[.57,.60,.63]}
 ];
 const mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
 function clip(poly,axis,bound,sign){const out=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],da=(a[axis]-bound)*sign,db=(b[axis]-bound)*sign;if(da>=0)out.push(a);if((da>=0)!=(db>=0))out.push(mix(a,b,da/(da-db)))}return out}
 for(const spec of specs){
  const pos=[],nor=[],col=[],idx=[],lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity],map=new Map();
  function vertex(a){
   const len=Math.hypot(a[3],a[4],a[5])||1,n=a.slice(3,6).map(x=>x/len),p=a.slice(0,3).map((x,i)=>x+n[i]*spec.gap*scale);
   const key=p.map(x=>Math.round(x*1e6)).join(",");if(map.has(key))return map.get(key);
   const id=pos.length/3;map.set(key,id);pos.push(...p);nor.push(...n);col.push(...spec.color);
   for(let i=0;i<3;i++){lo[i]=Math.min(lo[i],p[i]);hi[i]=Math.max(hi[i],p[i])}return id;
  }
  for(let i=0;i<index.length;i+=3){
   let poly=[0,1,2].map(k=>{let j=index[i+k]*3;return [...position.slice(j,j+3),...normal.slice(j,j+3)]});
   for(const [axis,bound,sign] of [[1,spec.min*scale,1],[1,spec.max*scale,-1],[0,(spec.loX??-spec.x)*scale,1],[0,spec.x*scale,-1]]){if(poly.length<3)break;poly=clip(poly,axis,bound,sign)}
   if(poly.length<3)continue;
   let ids=poly.map(vertex);for(let j=1;j<ids.length-1;j++){let a=ids[0],b=ids[j],c=ids[j+1];if(a===b||b===c||a===c)continue;
     let u=[0,1,2].map(k=>pos[b*3+k]-pos[a*3+k]),v=[0,1,2].map(k=>pos[c*3+k]-pos[a*3+k]);if(Math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])<1e-9)continue;idx.push(a,b,c)}
  }
  if(!idx.length)throw Error("Kıyafet üretilemedi: "+spec.name);
  output.set(spec.name,{m:{position:new Float32Array(pos),normal:new Float32Array(nor),color:new Float32Array(col),index:new Uint32Array(idx)},p:{istart:0,iend:idx.length},center:lo.map((x,i)=>(x+hi[i])/2)});
 }
 return output;
}
function anatomyModel(){`);
rep('function fullAnatomyParts(style="normal"){',`function outfitParts(style="normal"){
 const p=fullAnatomyParts(style),base=p[0],source=sourceModel("anatomy"),body=source.get("human.body");
 for(const [name,q] of source)if(name.startsWith("outfit."))p.push({type:"reference",style:"anatomy",name,t:q.center.map((v,i)=>(v-body.center[i])*base.s[i]+base.t[i]),s:base.s.slice(),r:[0,0,0],color:"#ffffff",mirror:false});
 return p;
}
function fullAnatomyParts(style="normal"){`);
rep('result.set(name,{m:{position,index,normal,color},p:{istart:0,iend:index.length},center});\n }\n return result;', 'result.set(name,{m:{position,index,normal,color},p:{istart:0,iend:index.length},center});\n }\n for(const [name,q] of fittedGarments(result.get("human.body")))result.set(name,q);\n return result;');
rep('<button id="mhFull">Tam anatomi</button>', '<button id="mhOutfit">Zırhlı anatomi</button><button id="mhFull">Tam anatomi</button>');
rep('$("mhFull").onclick=', '$("mhOutfit").onclick=()=>{if(!parts.length||confirm("Mevcut model zırhlı anatomik taslakla değişsin mi?")){parts=outfitParts($("bodyType").value);selected=0;ui();refresh()}};\n$("mhFull").onclick=');
h=h.replaceAll("R70.16","R70.17").replaceAll("Forge_R70_16","Forge_R70_17");
const s=h.slice(h.indexOf("<script>")+8,h.lastIndexOf("</script>"));
new Function(s);
const api=new Function("const self=globalThis;\n"+s.split("let parts=[],selected")[0]+";return {mesh,glb,outfitParts,validPart,sourceModel}")();
const results=[];
for(const style of ["normal","lean","heavy"]){
 const p=api.outfitParts(style),m=api.mesh(p);if(p.length!==10||!p.every(api.validPart)||!m.pos.every(Number.isFinite)||!m.nor.every(Number.isFinite))throw Error("model "+style);
 const copy=api.mesh(JSON.parse(JSON.stringify(p)));if(!copy.pos.every((x,i)=>x===m.pos[i]))throw Error("roundtrip");
 results.push({style,parts:p.length,triangles:m.pos.length/9,bytes:api.glb(m).length});
}
console.log(results);
fs.writeFileSync("studio/r70-reference/Forge_R70_17_template.html",h);
fs.writeFileSync("studio/r70-reference/R70_17_geometry.json",JSON.stringify(results,null,2));
