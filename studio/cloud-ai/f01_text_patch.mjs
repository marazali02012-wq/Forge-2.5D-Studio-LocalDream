// Optional F01 experimental menu. Existing image/rig controls untouched.
import fs from 'node:fs';
let h=fs.readFileSync('Forge_R70_29_AI_Connected.html','utf8');
function edit(a,b){if(!h.includes(a))throw Error('missing '+a);h=h.replace(a,b)}
edit('<button id="closeAiTools">','<button id="forgeTextOpen">Yazıdan 3D (deneysel)</button><button id="closeAiTools">');
edit('<body>','<body><dialog id="forgeTextDialog" style="box-sizing:border-box;width:min(460px,94vw);max-height:90vh;overflow:auto;background:#202a36;color:white;padding:12px"><b>Yazıdan gerçek 3D · Shap-E (deneysel)</b><p style="font-size:12px">Özel AI sunucusu gerekir. İngilizce açıklama önerilir. Geometri tahminidir; kalite garanti edilmez.</p><label for="forgeTextPrompt">Model açıklaması</label><textarea id="forgeTextPrompt" maxlength="300" rows="3" style="box-sizing:border-box;width:100%;display:block;color:#fff;background:#111a24" placeholder="Örn. a red ceramic teapot"></textarea><p id="forgeTextStatus" role="status" aria-live="polite"></p><button id="forgeTextStart">Üret</button> <button id="forgeTextClose">Kapat</button></dialog>');
const code=String.raw`
const ft=$('forgeTextDialog'),ftStatus=$('forgeTextStatus');let ftBusy=false;
$('forgeTextOpen').onclick=()=>{aiTools.close();ft.showModal()};
$('forgeTextClose').onclick=()=>{if(!ftBusy)ft.close()};
ft.addEventListener('cancel',e=>{if(ftBusy)e.preventDefault()});
$('forgeTextStart').onclick=async()=>{
 if(ftBusy)return;
 const promptText=$('forgeTextPrompt').value.trim();
 if(!promptText||promptText.length>300){ftStatus.textContent='1–300 karakterlik açıklama gerekli.';return}
 let token=null;
 try{
  const server=prompt('Forge AI sunucu adresi (HTTPS veya yerel test)','');if(!server)return;
  const url=new URL(server);
  if(url.username||url.password||url.search||url.hash||url.pathname!=='/'||!(url.protocol==='https:'||url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))throw Error('Geçerli HTTPS sunucu kök adresi gerekli');
  token=prompt('Sunucu erişim anahtarı (kaydedilmez)','');if(!token)return;
  if(!confirm('Açıklamayı '+url.origin+' sunucusuna gönder?'))return;
  ftBusy=true;$('forgeTextStart').disabled=true;$('forgeTextClose').disabled=true;$('forgeTextPrompt').disabled=true;ftStatus.textContent='Gerçek Shap-E üretimi sürüyor…';
  const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),450000);
  let ab;
  try{
   const r=await fetch(url.origin+'/v1/generate-text',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({prompt:promptText}),signal:ctrl.signal,redirect:'error',cache:'no-store'});
   if(!r.ok){const detail=await r.json().catch(()=>({}));throw Error(detail.error||('HTTP '+r.status))}
   if(r.headers.get('Content-Type')?.split(';')[0]!=='model/gltf-binary')throw Error('Sunucu GLB göndermedi');
   const n=Number(r.headers.get('Content-Length'));if(!Number.isInteger(n)||n<28||n>8e6)throw Error('GLB boyutu geçersiz');
   ab=await r.arrayBuffer();if(ab.byteLength!==n)throw Error('Eksik GLB');
  }finally{clearTimeout(timer)}
  const model=parseForgeAiGLB(ab); // Shap-E output is already Y-up; no TripoSR axis rotation.
  if(showForgeAI(model)){ftStatus.textContent='Model hazır.';ft.close()}else ftStatus.textContent='Mevcut model korundu.';
 }catch(e){ftStatus.textContent='Üretim hatası: '+e.message}
 finally{token=null;ftBusy=false;$('forgeTextStart').disabled=false;$('forgeTextClose').disabled=false;$('forgeTextPrompt').disabled=false}
};
`;
edit('</script></body></html>',code+'\n</script></body></html>');
fs.writeFileSync('Forge_R70_34_F01_Text_Experimental.html',h);
