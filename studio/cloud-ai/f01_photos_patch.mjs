// Separate experimental build; no change to existing deployed HTML.
import fs from 'node:fs';
let h=fs.readFileSync('Forge_R70_34_F01_Text_Experimental.html','utf8');
function edit(a,b){if(!h.includes(a))throw Error('missing '+a);h=h.replace(a,b)}
edit('<button id="closeAiTools">','<button id="forgePhotosOpen">Çok açılı 3D (deneysel)</button><button id="closeAiTools">');
edit('<body>','<body><dialog id="forgePhotosDialog" style="box-sizing:border-box;width:min(470px,94vw);max-height:90vh;overflow:auto;background:#202a36;color:white;padding:12px"><b>Çok açılı fotoğraftan 3D</b><p style="font-size:12px">Aynı kamera, aynı boyut, düz fon; nesnenin çevresinden örtüşen 12–48 fotoğraf. Alt yüzey açık kalabilir. Özel AI sunucusu gerekir.</p><input id="forgePhotosFiles" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden><button id="forgePhotosChoose">Fotoğrafları seç</button> <span id="forgePhotosCount">0 fotoğraf</span><p><label for="forgePhotosUp">Fotoğrafta yukarı yön: </label><select id="forgePhotosUp"><option value="top">Üst</option><option value="right">Sağ</option><option value="bottom">Alt</option><option value="left">Sol</option></select></p><p id="forgePhotosStatus" role="status" aria-live="polite"></p><button id="forgePhotosStart">Üret</button> <button id="forgePhotosClose">Kapat</button></dialog>');
const code=String.raw`
const fp=$('forgePhotosDialog'),fpStatus=$('forgePhotosStatus');let fpBusy=false;
$('forgePhotosOpen').onclick=()=>{aiTools.close();fp.showModal()};
$('forgePhotosClose').onclick=()=>{if(!fpBusy)fp.close()};
fp.addEventListener('cancel',e=>{if(fpBusy)e.preventDefault()});
$('forgePhotosChoose').onclick=()=>{if(!fpBusy)$('forgePhotosFiles').click()};
$('forgePhotosFiles').onchange=()=>{$('forgePhotosCount').textContent=$('forgePhotosFiles').files.length+' fotoğraf';fpStatus.textContent=''};
$('forgePhotosStart').onclick=async()=>{
 if(fpBusy)return;
 const files=Array.from($('forgePhotosFiles').files);
 if(files.length<12||files.length>48){fpStatus.textContent='12–48 fotoğraf seçin.';return}
 if(files.some(f=>!['image/png','image/jpeg','image/webp'].includes(f.type)||f.size<1||f.size>5*1024*1024)){fpStatus.textContent='PNG/JPEG/WebP; fotoğraf başına en fazla 5 MiB.';return}
 const meta=new TextEncoder().encode(JSON.stringify({sizes:files.map(f=>f.size),image_up:$('forgePhotosUp').value}));
 const prefix=new ArrayBuffer(4);new DataView(prefix).setUint32(0,meta.length);
 const body=new Blob([prefix,meta,...files],{type:'application/octet-stream'});
 if(body.size>60*1024*1024){fpStatus.textContent='Fotoğraf grubu en fazla 60 MiB.';return}
 let token=null;
 try{
  const server=prompt('Forge AI sunucu adresi (HTTPS veya yerel test)','');if(!server)return;
  const url=new URL(server);
  if(url.username||url.password||url.search||url.hash||url.pathname!=='/'||!(url.protocol==='https:'||url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))throw Error('Geçerli HTTPS sunucu kök adresi gerekli');
  token=prompt('Sunucu erişim anahtarı (kaydedilmez)','');if(!token)return;
  if(!confirm(files.length+' fotoğrafı '+url.origin+' sunucusuna gönder?'))return;
  fpBusy=true;for(const id of ['forgePhotosChoose','forgePhotosStart','forgePhotosClose','forgePhotosUp'])$(id).disabled=true;
  fpStatus.textContent='Fotoğraflar işleniyor; gerçek yoğun 3D üretimi…';
  const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),1140000);
  let ab;
  try{
   const r=await fetch(url.origin+'/v1/generate-multiview',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/octet-stream'},body,signal:ctrl.signal,redirect:'error',cache:'no-store'});
   if(!r.ok){const detail=await r.json().catch(()=>({}));throw Error(detail.error||('HTTP '+r.status))}
   if(r.headers.get('Content-Type')?.split(';')[0]!=='model/gltf-binary')throw Error('Sunucu GLB göndermedi');
   const n=Number(r.headers.get('Content-Length'));if(!Number.isInteger(n)||n<28||n>8e6)throw Error('GLB boyutu geçersiz');
   ab=await r.arrayBuffer();if(ab.byteLength!==n)throw Error('Eksik GLB');
  }finally{clearTimeout(timer)}
  if(showForgeAI(parseForgeAiGLB(ab))){fpStatus.textContent='Model hazır; alt yüzey açık olabilir.';fp.close()}else fpStatus.textContent='Mevcut model korundu.';
 }catch(e){fpStatus.textContent='Üretim hatası: '+e.message}
 finally{token=null;fpBusy=false;for(const id of ['forgePhotosChoose','forgePhotosStart','forgePhotosClose','forgePhotosUp'])$(id).disabled=false}
};
`;
edit('</script></body></html>',code+'\n</script></body></html>');
fs.writeFileSync('Forge_R70_34_F01_Multiview_Experimental.html',h);
