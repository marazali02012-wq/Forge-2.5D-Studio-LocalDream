"""Opt-in local TRELLIS.2 GGML CLI adapter; never downloads, uploads or falls back.
Upstream contract: pwilkin/trellis.cpp v0.8.1. Requires operator-installed runtime/models.
"""
import io, json, os, struct, subprocess, tempfile, time
from pathlib import Path
from PIL import Image
import numpy as np
from rig import unpack, accessor

MAX_GLB=75*1024*1024
# 512 path; 1024 cascade and background model intentionally not enabled here.
REQUIRED=('dinov3.gguf','ss_flow.gguf','ss_dec.gguf','shape_flow_512.gguf','shape_dec.gguf','tex_flow_512.gguf','tex_dec.gguf')

def configuration():
    if os.environ.get('FORGE_TRELLIS_NATIVE_ENABLE')!='1':raise ValueError('Yerel TRELLIS motoru etkin değil.')
    exe=Path(os.environ.get('FORGE_TRELLIS_NATIVE_CLI',''));models=Path(os.environ.get('FORGE_TRELLIS_NATIVE_MODELS',''))
    backend=os.environ.get('FORGE_TRELLIS_NATIVE_BACKEND','CPU')
    if backend not in ('CPU','Vulkan'):raise ValueError('CPU veya Vulkan seçilmeli.')
    if not exe.is_absolute() or not exe.is_file() or not os.access(exe,os.X_OK):raise ValueError('Yerel trellis-cli yürütülebilir dosyası bulunamadı.')
    if not models.is_absolute() or not models.is_dir():raise ValueError('Yerel GGUF klasörü bulunamadı.')
    missing=[]
    for name in REQUIRED:
        p=models/name
        try:
            with p.open('rb') as f: valid=f.read(4)==b'GGUF' and p.stat().st_size>1024
        except OSError:valid=False
        if not valid:missing.append(name)
    if missing:raise ValueError('Eksik/geçersiz GGUF: '+', '.join(missing))
    try:timeout=int(os.environ.get('FORGE_TRELLIS_NATIVE_TIMEOUT','3600'));threads=int(os.environ.get('FORGE_TRELLIS_NATIVE_THREADS','2'))
    except ValueError:raise ValueError('Geçersiz süre/iş parçacığı ayarı.')
    if not 60<=timeout<=7200 or not 1<=threads<=16:raise ValueError('Süre 60–7200 sn, thread 1–16.')
    return exe.resolve(),models.resolve(),backend,timeout,threads

def diagnose():
    try:
        _,_,backend,timeout,threads=configuration()
        return {'configured':True,'backend':backend,'timeout':timeout,'threads':threads,'inference_verified':False,'detail':'Dosyalar mevcut; gerçek AI üretimi ve donanım doğrulanmadı.'}
    except (ValueError,OSError) as e:return {'configured':False,'inference_verified':False,'detail':str(e)}

def checked_glb(raw):
    if len(raw)<28 or len(raw)>MAX_GLB or struct.unpack_from('<4sII',raw)!=(b'glTF',2,len(raw)):raise ValueError('Geçersiz GLB.')
    j,b=unpack(raw)
    if len(j.get('buffers',[]))!=1 or any('uri' in x for x in j['buffers']+j.get('images',[])):raise ValueError('Harici GLB kaynağı yasak.')
    if j['buffers'][0].get('byteLength',-1)>len(b):raise ValueError('Geçersiz buffer.')
    if set(j.get('extensionsRequired',[]))-{'EXT_texture_webp'}:raise ValueError('Desteklenmeyen zorunlu GLB uzantısı.')
    # Native default is WebP; Forge needs core glTF texture.source. Decode once to PNG
    # and preserve UV, geometry, normal, roughness and metallic texture references.
    converted={}
    for tex in j.get('textures',[]):
        ext=tex.get('extensions',{}).get('EXT_texture_webp')
        if ext is None:continue
        idx=ext['source']
        if type(idx)!=int or not 0<=idx<len(j.get('images',[])):raise ValueError('WebP kaynak indeksi.')
        if idx not in converted:
            im=j['images'][idx];view=j['bufferViews'][im['bufferView']];off=view.get('byteOffset',0);size=view['byteLength']
            if view.get('buffer',0)!=0 or off<0 or size<=0 or off+size>len(b):raise ValueError('Geçersiz doku aralığı.')
            with Image.open(io.BytesIO(b[off:off+size])) as p:
                if p.format!='WEBP' or p.width*p.height>4096**2:raise ValueError('Geçersiz WebP dokusu.')
                tmp=io.BytesIO();p.save(tmp,'PNG');png=tmp.getvalue()
            if len(b)+len(png)>MAX_GLB:raise ValueError('Doku dönüşümü boyut sınırı.')
            b.extend(b'\0'*((-len(b))%4));new={'buffer':0,'byteOffset':len(b),'byteLength':len(png)};b.extend(png);j['bufferViews'].append(new)
            im['bufferView']=len(j['bufferViews'])-1;im['mimeType']='image/png';converted[idx]=True
        tex['source']=idx;del tex['extensions']['EXT_texture_webp']
        if not tex['extensions']:del tex['extensions']
    for key in ('extensionsUsed','extensionsRequired'):
        if key in j:
            j[key]=[x for x in j[key] if x!='EXT_texture_webp']
            if not j[key]:del j[key]
    if j.get('skins') or j.get('animations'):raise ValueError('Statik üretim bekleniyor.')
    tris=verts=0;texture_count=0
    for m in j.get('meshes',[]):
        for p in m.get('primitives',[]):
            if p.get('mode',4)!=4 or 'indices' not in p:raise ValueError('Üçgen mesh gerekli.')
            pos=accessor(j,b,p['attributes']['POSITION']);uv=accessor(j,b,p['attributes']['TEXCOORD_0']);ix=accessor(j,b,p['indices']).reshape(-1)
            if pos.shape[1]!=3 or uv.shape!=(len(pos),2) or len(ix)%3 or not np.issubdtype(ix.dtype,np.unsignedinteger) or ix.max()>=len(pos) or not np.isfinite(pos).all() or not np.isfinite(uv).all() or np.min(np.ptp(pos,axis=0))<=1e-6:raise ValueError('Geometri/UV doğrulaması başarısız.')
            mat=j['materials'][p['material']]['pbrMetallicRoughness'];t=j['textures'][mat['baseColorTexture']['index']];im=j['images'][t['source']];v=j['bufferViews'][im['bufferView']];o=v.get('byteOffset',0);n=v['byteLength']
            if v.get('buffer',0)!=0 or o<0 or n<=0 or o+n>len(b):raise ValueError('Doku aralığı.')
            with Image.open(io.BytesIO(b[o:o+n])) as pic:
                if pic.format not in ('PNG','JPEG') or pic.width*pic.height>4096**2:raise ValueError('Doku biçimi/boyutu.')
                pic.verify()
            texture_count+=1;tris+=len(ix)//3;verts+=len(pos)
    if tris<4 or verts<4 or tris>1000000 or verts>1500000 or not texture_count:raise ValueError('Geometri bütçesi.')
    if converted:
        b.extend(b'\0'*((-len(b))%4));j['buffers'][0]['byteLength']=len(b)
        js=json.dumps(j,separators=(',',':'),ensure_ascii=True).encode();js+=b' '*((-len(js))%4)
        raw=struct.pack('<4sII',b'glTF',2,28+len(js)+len(b))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(b),0x004e4942)+b
    if len(raw)>MAX_GLB:raise ValueError('GLB 75 MB sınırı.')
    return bytes(raw),{'vertices':verts,'triangles':tris,'webp_converted':len(converted),'quality_verified':False}

def generate(image,seed=1234,cancel=None):
    exe,models,backend,timeout,threads=configuration()
    if type(seed)!=int or not 0<=seed<=2147483647:raise ValueError('Geçersiz seed.')
    image=image.convert('RGBA');alpha=np.asarray(image.getchannel('A'))
    if not (alpha<=16).any() or not (alpha>=128).any():raise ValueError('Onaylanmış şeffaf PNG gerekli.')
    with tempfile.TemporaryDirectory(prefix='forge-trellis-') as tmp:
        work=Path(tmp);src=work/'source.png';dest=work/'output.glb';image.save(src)
        cmd=[str(exe),str(src),str(dest),'--models',str(models),'--model','trellis','--res','512','--atlas','1024','--seed',str(seed),'--backend',backend,'--threads',str(threads),'--steps','12']
        if backend=='Vulkan':cmd.append('--require-gpu')
        start=time.monotonic()
        logpath=work/'runtime.log'
        with logpath.open('wb') as log:
            proc=subprocess.Popen(cmd,cwd=work,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    if cancel is not None and cancel.is_set():raise RuntimeError('TRELLIS işlemi iptal edildi.')
                    if time.monotonic()-start>timeout:raise TimeoutError('TRELLIS zaman aşımı.')
                    if logpath.stat().st_size>10*1024*1024 or (dest.is_file() and dest.stat().st_size>MAX_GLB):raise ValueError('Çıktı boyutu sınırı.')
                    time.sleep(.2)
                if cancel is not None and cancel.is_set():raise RuntimeError('TRELLIS işlemi iptal edildi.')
                if proc.returncode or not dest.is_file() or dest.is_symlink() or dest.stat().st_size>MAX_GLB:raise RuntimeError('TRELLIS yerel çıkarımı geçerli GLB üretmedi.')
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
        raw,report=checked_glb(dest.read_bytes());report.update(backend=backend,seconds=round(time.monotonic()-start,2),resolution=512,engine='trellis.cpp')
        return raw,report
