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
const here=new URL('.',import.meta.url);
const read=name=>fs.readFileSync(new URL(name,here),'utf8');
edit('<button id="forgeAiGenerate">','<button id="openRig">Animasyonlu GLB aç</button><input id="rigFile" type="file" accept=".glb" hidden><button id="forgeRigGenerate">Resimden animasyonlu GLB</button><button id="forgeAiGenerate">');
edit("let forgeAiBusy=false;", "let forgeAiBusy=false, rigRequested=false; $('forgeRigGenerate').onclick=()=>{if(!forgeAiBusy){rigRequested=true;$('forgeAiImage').click()}};");
edit("if(!forgeAiBusy)$('forgeAiImage').click()", "if(!forgeAiBusy){rigRequested=false;$('forgeAiImage').click()}");
edit("url.origin+'/v1/generate'", "url.origin+(rigRequested?'/v1/generate-rig':($('forgeStaticQuality').value==='192'?'/v1/generate?resolution=192':'/v1/generate'))");
edit('controller.abort(),330000','controller.abort(),rigRequested?430000:330000');
edit("length>8e6","length>(rigRequested?32*1024*1024:8e6)");
edit("showForgeAI(orientRawTripo(parseForgeAiGLB(ab)));","if(rigRequested){openAnimated(new Blob([ab],{type:'model/gltf-binary'}));msg.textContent='Animasyonlu GLB hazır'}else showForgeAI(orientRawTripo(parseForgeAiGLB(ab)));");
edit("if(!r.ok)throw Error('Üretim başarısız: HTTP '+r.status);","if(!r.ok){const detail=await r.json().catch(()=>({}));throw Error(detail.error||('HTTP '+r.status))}");
const {execFileSync}=await import('node:child_process');
const {createHash}=await import('node:crypto');
const viewer=process.env.FORGE_VIEWER_JS?fs.readFileSync(process.env.FORGE_VIEWER_JS):execFileSync('curl',['-fsSL','--retry','2','--max-time','90','https://unpkg.com/@google/model-viewer@4.1.0/dist/model-viewer.min.js'],{maxBuffer:2e6});
if(createHash('sha256').update(viewer).digest('hex')!=='8367184a607fbe07a78b650c0d359e5ebbd96f7e2b22f95f761f559b63430386')throw Error('Viewer checksum mismatch');
edit('</head>', '<!-- '+read('MODEL_VIEWER_LICENSE.txt').replaceAll('--','—')+' -->'+'<script type="module" src="data:text/javascript;base64,'+viewer.toString('base64')+'"></script></head>');
edit('<div id="panelNav">','<button id="quickAi" aria-label="Yapay zekâ araçları">AI / 3D</button><div id="panelNav">');
const dialog=read('rig_dialog.html');
const qualityAnchor='<button data-forge-action="forgeAiGenerate">';
if(!dialog.includes(qualityAnchor))throw Error('Static quality anchor missing');
edit('<body>','<body>'+dialog.replace(qualityAnchor,'<label for="forgeStaticQuality" style="display:block;margin:6px 0">3D model detayı <select id="forgeStaticQuality" aria-label="3D model detayı"><option value="128" selected>Standart (128)</option><option value="192">Yüksek (192)</option></select></label>'+qualityAnchor));
edit('</script></body></html>',read('rig_viewer.js')+'\n</script></body></html>');
h=h.replaceAll(/(Forge Studio |FORGE |Forge )R70\.(17|29)/g,'$1R70.34');
for(const file of ['Forge_R70_34_Studio.html','Forge_R70_29_AI_Connected.html']) fs.writeFileSync(file,h);
