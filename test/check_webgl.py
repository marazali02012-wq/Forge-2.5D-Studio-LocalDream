"""Run against the delivered HTML, with Chrome's offline SwiftShader renderer."""
from pathlib import Path
from io import BytesIO
import base64, json, os, time, zipfile
from PIL import Image
from playwright.sync_api import sync_playwright
root=Path.cwd()
out=root/'test-sonuclari'
out.mkdir(exist_ok=True)
rows=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME_BIN','/usr/bin/google-chrome'),headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage','--no-sandbox'])
 ctx=browser.new_context(offline=True,viewport={'width':740,'height':360},accept_downloads=True)
 page=ctx.new_page()
 page.on('pageerror', lambda e: print('PAGE ERROR',e,flush=True))
 page.goto((root/'Forge_25D_V14_WebGL2.html').as_uri())
 page.wait_for_function('window.ForgeV12 && ForgeV11.ready')
 page.evaluate("ForgeShell.go('model');ForgeV12.S3.playing=false")
 for name in ['sade','zirhli','png']:
  if name=='png':
   page.locator('#importFile').set_input_files(str(root/'test'/'izci.png'))
   page.wait_for_function('ForgeV11.state.custom')
   page.evaluate("document.getElementById('s3-analyze').click()")
   page.wait_for_function('ForgeV12.S3.ch.mesh.texture')
  else:
   page.evaluate("""name=>{const f=Forge3D;ForgeV12.setSource({body:{},style:name==='sade'?{armor:'light',cape:false,helmet:'nohelm',hair:'none',tabard:false,pauldrons:'none'}:{armor:'heavy',cape:true,shield:true},palette:f.DEFAULT_PALETTE},[],null,'tarif',name)}""",name)
  result=page.evaluate("""async name=>{
    const f=Forge3D,e=f.renderEngine,ch=ForgeV12.S3.ch,refs=[],images=[],rows=[];
    const load0=performance.now();
    ch.framing=f.computeFraming(ch);const framingMs=performance.now()-load0;
    for(const mode of ['cpu','gpu']){
      e.set(mode);
      const start=performance.now();f.renderFrame(ch,'idle',0,0,{ss:1});const firstMs=performance.now()-start;
      const startFrame=performance.now();let iou=1,mae=0;
      const frames=[];
      for(const clip of f.CLIP_KEYS)for(const d of [0,2,4,6])for(const frame of [0,3,7]){
        const r=f.renderFrame(ch,clip,frame,d,{ss:1});frames.push(r.rgba);
      }
      const ms=(performance.now()-startFrame)/frames.length;
      if(mode==='cpu')refs.push(...frames);
      else{
        if(!e.path.startsWith('WebGL2'))throw Error('Shader testi CPU yoluna düştü: '+e.reason);
        for(let i=0;i<frames.length;i++){
          const a=refs[i],b=frames[i];let union=0,both=0,err=0;
          for(let j=0;j<a.length;j+=4){const p=a[j+3]>100,q=b[j+3]>100;union+=+(p||q);if(p&&q){both++;for(let k=0;k<3;k++)err+=Math.abs(a[j+k]-b[j+k]);}}
          iou=Math.min(iou,both/union);mae=Math.max(mae,err/(3*both));
        }
        if(iou<.84||mae>45)throw Error('Görsel eşik: '+iou+'/'+mae);
      }
      const c=document.createElement('canvas');c.width=c.height=256;c.getContext('2d').putImageData(new ImageData(frames[1],256,256),0,0);
      images.push(c.toDataURL().split(',')[1]);
      rows.push({name,mode,actual:e.path,frames:frames.length,ms,fps:1000/ms,firstMs,framingMs,iou,mae,profile:e.metrics,jsHeap:performance.memory?.usedJSHeapSize??null});
    }
    return {images,rows}
  }""",name)
  for mode,b64 in zip(['cpu','gpu'],result['images']):
   (out/f'{name}-{mode}.png').write_bytes(base64.b64decode(b64))
  for row in result['rows']:
   mode=row['mode'];page.evaluate("""mode=>{const s=document.getElementById('render-mode');s.value=mode;s.onchange();ForgeShell.go('aktar');document.getElementById('s3-cool').value='0'}""",mode)
   t=time.monotonic()
   with page.expect_download(timeout=480000) as dl:page.evaluate("document.getElementById('s3-zip').click()")
   path=out/f'{name}-{mode}.zip';dl.value.save_as(path);row['spriteSeconds']=time.monotonic()-t
   with zipfile.ZipFile(path) as z:
    assert not z.testzip();man=json.loads(z.read('manifest.json'))
    assert man['glbVerify']['ok']
    backend=man['renderBackend'];assert len(backend)==40
    assert all((v.startswith('WebGL2') if mode=='gpu' else v=='CPU') for v in backend.values()),man
    for fn in backend:
     sheet=Image.open(BytesIO(z.read(fn))).convert('RGBA');assert sheet.size==(1024,512)
     cells=[sheet.crop((i%4*256,i//4*256,i%4*256+256,i//4*256+256)) for i in range(8)]
     assert all(c.getchannel('A').getbbox() and c.getpixel((0,0))[3]==0 for c in cells)
     assert len(set(c.tobytes() for c in cells))>1
    if name=='png' and mode=='gpu':
     (out/'UV_Animasyon.glb').write_bytes(z.read('model/forge_savasci.glb'))
     page.locator('#s3-verify-file').set_input_files(str(out/'UV_Animasyon.glb'))
     page.wait_for_function("ForgeV12.S3.viewer==='glb'")
     assert page.evaluate("Forge3D.crc32(ForgeV12.S3.glbChar.mesh.texture.rgba)===parseInt(ForgeV12.S3.atlas.key,16)")
   if name!='png' or mode!='gpu':path.unlink()
   print('PASS',row,flush=True);rows.append(row)
  (out/'olcumler.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False))
 # Trigger a genuine loss on the preview context and verify a CPU frame.
 page.evaluate("ForgeShell.go('model');const s=document.getElementById('render-mode');s.value='gpu';s.onchange();ForgeV12.draw();Forge3D.renderEngine.renderer.gl.getExtension('WEBGL_lose_context').loseContext()")
 page.wait_for_function("Forge3D.renderEngine.reason.includes('kayb')")
 page.evaluate("ForgeV12.draw()");assert page.evaluate("Forge3D.renderEngine.path==='CPU'")
 browser.close()
