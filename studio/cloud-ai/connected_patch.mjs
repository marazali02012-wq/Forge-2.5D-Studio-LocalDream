import fs from 'node:fs';
let h=fs.readFileSync('Forge_R70_28_AI_Import.html','utf8');
function edit(a,b){if(!h.includes(a))throw Error('Missing anchor '+a);h=h.replace(a,b)}
edit('id="forgeAiImport">AI / GLB aç</button>','id="forgeAiImport">GLB aç</button><button id="forgeAiRaw">TripoSR ham GLB aç</button><input id="forgeAiRawFile" type="file" accept=".glb" hidden><button id="forgeAiGenerate">Resimden 3D üret</button><input id="forgeAiImage" type="file" accept="image/png,image/jpeg,image/webp" hidden>');
const code=String.raw`
function orientRawTripo(p){
 // Upstream TripoSR cameras use Z-up; observed input front is +X.
 // Proper rotation (x,y,z)->(y,z,x), determinant +1, no winding reversal.
 for(const a of [p.geometry.v,p.geometry.n])for(let i=0;i<a.length;i+=3){
  const x=a[i],y=a[i+1],z=a[i+2];a[i]=y;a[i+1]=z;a[i+2]=x;
 }
 return p;
}
function showForgeAI(p){
 if(!confirm('Üretilen modeli aç? Mevcut modeli önce kaydet.'))return false;
 parts=[p];selected=0;yaw=0;pitch=0;ui();refresh();msg.textContent='AI / GLB · '+p.geometry.i.length/3+' üçgen';return true;
}
$('forgeAiRaw').onclick=()=>$('forgeAiRawFile').click();
$('forgeAiRawFile').onchange=async()=>{
 const input=$('forgeAiRawFile'),f=input.files[0];
 try{if(!f)return;if(f.size>8e6)throw Error('GLB en fazla 8 MB');showForgeAI(orientRawTripo(parseForgeAiGLB(await f.arrayBuffer())))}
 catch(e){alert(e.message)}finally{input.value=''}
};
let forgeAiBusy=false;
$('forgeAiGenerate').onclick=()=>{if(!forgeAiBusy)$('forgeAiImage').click()};
$('forgeAiImage').onchange=async()=>{
 const input=$('forgeAiImage'),file=input.files[0];if(!file||forgeAiBusy){input.value='';return}
 let token=null;
 try{
  if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>5*1024*1024)throw Error('PNG, JPEG veya WebP; en fazla 5 MB');
  const server=prompt('Forge AI sunucu adresi (HTTPS veya yerel test)','');if(!server)return;
  const url=new URL(server);
  if(url.username||url.password||url.search||url.hash||url.pathname!=='/'||!(url.protocol==='https:'||url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))throw Error('Geçerli HTTPS sunucu kök adresi gerekli');
  token=prompt('Sunucu erişim anahtarı (kaydedilmez)','');if(!token)return;
  if(!confirm('Resmi '+url.origin+' sunucusuna gönder ve 3D model üret?'))return;
  forgeAiBusy=true;$('forgeAiGenerate').disabled=true;msg.textContent='Yapay zekâ modeli üretiyor…';
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),330000);
  let ab;
  try{
   const r=await fetch(url.origin+'/v1/generate',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':file.type},body:file,signal:controller.signal,redirect:'error',cache:'no-store'});
   if(!r.ok)throw Error('Üretim başarısız: HTTP '+r.status);
   if(r.headers.get('Content-Type')?.split(';')[0]!=='model/gltf-binary')throw Error('Sunucu GLB göndermedi');
   const length=Number(r.headers.get('Content-Length'));if(!Number.isFinite(length)||length<28||length>8e6)throw Error('GLB boyutu geçersiz');
   ab=await r.arrayBuffer();if(ab.byteLength!==length)throw Error('Eksik GLB');
  }finally{clearTimeout(timer)}
  showForgeAI(orientRawTripo(parseForgeAiGLB(ab)));
 }catch(e){msg.textContent='AI hatası: '+e.message}
 finally{token=null;forgeAiBusy=false;$('forgeAiGenerate').disabled=false;input.value=''}
};
`;
edit('</script></body></html>',code+'\n</script></body></html>');
h=h.replace('FORGE R70.17','FORGE R70.29');fs.writeFileSync('Forge_R70_29_AI_Connected.html',h);
