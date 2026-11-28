// F01 static batch. Each result is the original independently generated GLB.
// Credentials only live in the async call; no persistent storage.
(()=>{
 const dialog=$('forgeBatchDialog'),input=$('forgeBatchFiles'),status=$('forgeBatchStatus'),results=$('forgeBatchResults'),start=$('forgeBatchStart'),stop=$('forgeBatchStop'),close=$('forgeBatchClose');
 let running=false,halt=false,urls=[];
 function clear(){for(const u of urls)URL.revokeObjectURL(u);urls=[];results.replaceChildren()}
 $('forgeBatchOpen').onclick=()=>{if(forgeAiBusy)return;$('aiTools').close();dialog.showModal()};
 close.onclick=()=>{if(!running)dialog.close()};
 dialog.addEventListener('cancel',e=>{if(running)e.preventDefault()});
 stop.onclick=()=>{halt=true;stop.disabled=true;status.textContent='Mevcut üretim tamamlanınca duracak.'};
 start.onclick=async()=>{
  if(running||forgeAiBusy)return;
  const files=Array.from(input.files);
  if(!files.length||files.length>5||files.some(f=>!['image/png','image/jpeg','image/webp'].includes(f.type)||f.size>5*1024*1024||!f.size)){
   status.textContent='1–5 PNG/JPEG/WebP görsel seçin; her biri en fazla 5 MB.';return
  }
  const address=prompt('Forge AI sunucu adresi (HTTPS veya yerel test)','');if(!address)return;
  let url;try{url=new URL(address);if(url.username||url.password||url.search||url.hash||url.pathname!=='/'||!(url.protocol==='https:'||url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))throw Error()}catch{status.textContent='Geçerli HTTPS sunucu kök adresi gerekli';return}
  let token=prompt('Sunucu erişim anahtarı (kaydedilmez)','');if(!token)return;
  if(!confirm(files.length+' görseli '+url.origin+' sunucusuna sırayla gönder?'))return;
  const endpoint=url.origin+($('forgeStaticQuality').value==='192'?'/v1/generate?resolution=192':'/v1/generate');
  clear();running=true;forgeAiBusy=true;halt=false;start.disabled=input.disabled=close.disabled=true;stop.disabled=false;
  let ok=0,failed=0;
  try{
   for(let i=0;i<files.length&&!halt;i++){
    const f=files[i],row=document.createElement('p');row.style.cssText='overflow-wrap:anywhere;margin:6px 0';row.textContent=(i+1)+'. '+f.name+' — üretiliyor';results.append(row);
    status.textContent=(i+1)+' / '+files.length+' üretiliyor';
    const c=new AbortController(),timer=setTimeout(()=>c.abort(),330000);
    try{
     const res=await fetch(endpoint,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':f.type},body:f,signal:c.signal,redirect:'error',cache:'no-store'});
     if(!res.ok){const d=await res.json().catch(()=>({}));throw Error(d.error||'HTTP '+res.status)}
     const n=Number(res.headers.get('Content-Length'));if(res.headers.get('Content-Type')?.split(';')[0]!=='model/gltf-binary'||!Number.isFinite(n)||n<28||n>8e6)throw Error('Geçersiz GLB yanıtı');
     const ab=await res.arrayBuffer();if(ab.byteLength!==n)throw Error('Eksik GLB');
     parseForgeAiGLB(ab);
     const u=URL.createObjectURL(new Blob([ab],{type:'model/gltf-binary'}));urls.push(u);
     row.textContent=(i+1)+'. '+f.name+' — hazır ';
     const a=document.createElement('a');a.href=u;a.download=(i+1)+'-'+f.name.replace(/\.[^.]+$/,'').replace(/[^\p{L}\p{N}_-]/gu,'_')+'.glb';a.style.color='white';a.textContent='GLB indir';row.append(a);ok++;
    }catch(e){row.textContent=(i+1)+'. '+f.name+' — '+String(e.message).slice(0,160);failed++}
    finally{clearTimeout(timer)}
   }
  }finally{token=null;running=false;forgeAiBusy=false;start.disabled=input.disabled=close.disabled=false;stop.disabled=true;status.textContent='Hazır: '+ok+' · Hata: '+failed+' · Atlanan: '+(files.length-ok-failed)}
 };
 window.addEventListener('pagehide',clear);
})();
