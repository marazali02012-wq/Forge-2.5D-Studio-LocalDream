"""Single-user Forge API, optional local-only mode; authenticated hosting requires HTTPS."""
from pathlib import Path
from threading import Lock
import io, struct, json, logging, os, secrets, base64
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.concurrency import run_in_threadpool
from PIL import Image
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
ROOT=Path(__file__).resolve().parent
MAX_IMAGE=10*1024*1024
MAX_GLB=75*1024*1024
busy=Lock()
password=os.environ.get('FORGE_PASSWORD','')
if os.environ.get('FORGE_REQUIRE_AUTH')=='1' and len(password)<16:
    raise RuntimeError('FORGE_PASSWORD must contain at least 16 characters')
public_origin=os.environ.get('FORGE_PUBLIC_ORIGIN','').rstrip('/')
expected=('Basic '+base64.b64encode(('forge:'+password).encode()).decode()).encode()
@app.middleware('http')
async def protect(request,call_next):
    if password and not secrets.compare_digest(request.headers.get('authorization','').encode(),expected):
        return PlainTextResponse('Forge: giris gerekli',401,headers={'WWW-Authenticate':'Basic realm="Forge Studio", charset="UTF-8"','Cache-Control':'no-store'})
    if request.method=='POST':
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != (public_origin or str(request.base_url).rstrip('/')):
            return PlainTextResponse('Cross-origin request blocked',403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    return response
@app.get('/')
def home():return FileResponse(ROOT/'index.html')
@app.get('/api/triposr/status')
def status():return {'engine':'TripoSR','busy':busy.locked(),'note':'Server availability is not proof of model readiness'}
def infer(image,texture,resolution=96):
    from engine import generate_checked
    return generate_checked(image,texture,resolution)
def validate_glb(b):
    if len(b)<20 or len(b)>MAX_GLB or struct.unpack_from('<4sII',b)!=(b'glTF',2,len(b)):raise ValueError('Invalid GLB')
    n,t=struct.unpack_from('<II',b,12)
    if t!=0x4e4f534a or n>len(b)-20:raise ValueError('Invalid GLB JSON')
    j=json.loads(b[20:20+n]);p=[p for m in j['meshes'] for p in m['primitives']]
    if not any('POSITION' in x['attributes'] and 'TEXCOORD_0' in x['attributes'] for x in p):raise ValueError('No UV geometry')
    if not any('baseColorTexture' in m.get('pbrMetallicRoughness',{}) for m in j.get('materials',[])):raise ValueError('No base texture')
    if not any('bufferView' in i for i in j.get('images',[])):raise ValueError('No embedded texture')
@app.post('/api/triposr/generate')
async def generate(request:Request,texture:int=512,resolution:int=96):
    if resolution not in (96,128,160,256):raise HTTPException(400,'Geometri çözünürlüğü 96, 128, 160 veya 256 olmalı.')
    if texture not in (512,1024,2048):raise HTTPException(400,'Doku boyutu 512, 1024 veya 2048 olmalı.')
    if request.headers.get('content-type','').split(';')[0]!='image/png':raise HTTPException(415,'PNG gerekli.')
    if not busy.acquire(blocking=False):raise HTTPException(409,'CPU motoru meşgul.')
    try:
        buf=bytearray()
        async for chunk in request.stream():
            if len(buf)+len(chunk)>MAX_IMAGE:raise HTTPException(413,'Görsel 10 MB sınırını aşıyor.')
            buf.extend(chunk)
        try:
            with Image.open(io.BytesIO(buf)) as im:
                if im.format!='PNG' or im.width*im.height>16000000:raise ValueError('PNG/16 MP sınırı')
                image=im.convert('RGBA');image.load()
            lo,hi=image.getchannel('A').getextrema()
            if lo==255 or hi==0:raise ValueError('Şeffaf arka planlı, boş olmayan nesne gerekli.')
        except Exception:raise HTTPException(400,'Geçerli, şeffaf arka planlı PNG gerekli.')
        try:
            result=await run_in_threadpool(infer,image,texture,resolution)
            b,qa=result if isinstance(result,tuple) else (result,None)
            validate_glb(b)
        except Exception:
            logging.exception('TripoSR production failed');raise HTTPException(503,'TripoSR üretimi veya GLB doğrulaması başarısız. Sunucu kaydını kontrol edin.')
        headers={'Cache-Control':'no-store'}
        if qa is not None:headers['X-Forge-QA']=json.dumps(qa,separators=(',',':'),ensure_ascii=True)
        return Response(b,media_type='model/gltf-binary',headers=headers)
    finally:busy.release()

@app.post('/api/model/export-obj')
async def export_obj(request:Request):
    if request.headers.get('content-type','').split(';')[0]!='model/gltf-binary':raise HTTPException(415,'GLB gerekli.')
    if not busy.acquire(blocking=False):raise HTTPException(409,'Motor meşgul.')
    try:
        buf=bytearray()
        async for chunk in request.stream():
            if len(buf)+len(chunk)>MAX_GLB:raise HTTPException(413,'GLB 75 MB sınırı.')
            buf.extend(chunk)
        try:
            result=await run_in_threadpool(convert_obj,bytes(buf))
        except Exception:
            logging.exception('OBJ export failed');raise HTTPException(400,'GLB statik OBJ formatına dönüştürülemedi.')
        return Response(result,media_type='application/zip')
    finally:busy.release()

def convert_obj(b):
    import zipfile, trimesh
    from trimesh.exchange.obj import export_obj
    if len(b)<28 or struct.unpack_from('<4sII',b)!=(b'glTF',2,len(b)):raise ValueError('Invalid GLB')
    n,t=struct.unpack_from('<II',b,12)
    if t!=0x4e4f534a or n>len(b)-20:raise ValueError('Invalid GLB JSON')
    j=json.loads(b[20:20+n])
    if any('uri' in x and not x['uri'].startswith('data:') for x in j.get('buffers',[])+j.get('images',[])):raise ValueError('External resource')
    if j.get('skins') or j.get('animations'):raise ValueError('OBJ loses rig and animations')
    scene=trimesh.load(io.BytesIO(b),file_type='glb',force='scene',process=False)
    if not scene.geometry:raise ValueError('Empty mesh')
    obj,assets=export_obj(scene,include_normals=True,include_texture=True,return_texture=True,write_texture=False,mtl_name='Forge.mtl')
    if not isinstance(obj,str) or not any(x.startswith('f ') for x in obj.splitlines()):raise ValueError('No faces')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('Forge.obj',obj)
        for name,data in (assets or {}).items():
            if Path(name).name!=name:raise ValueError('Invalid asset name')
            z.writestr(name,data)
    return out.getvalue()

def check_embedded_model(b):
    if len(b)<28 or len(b)>MAX_GLB or struct.unpack_from('<4sII',b)!=(b'glTF',2,len(b)):raise ValueError('Invalid GLB')
    n,t=struct.unpack_from('<II',b,12)
    if t!=0x4e4f534a or n>len(b)-28:raise ValueError('Invalid GLB JSON')
    j=json.loads(b[20:20+n]);off=20+n
    bl,bt=struct.unpack_from('<II',b,off)
    if bt!=0x004e4942 or off+8+bl!=len(b):raise ValueError('Invalid binary')
    if any('uri' in x and not str(x['uri']).startswith('data:') for x in j.get('buffers',[])+j.get('images',[])):raise ValueError('External resource')
    if not j.get('meshes'):raise ValueError('Empty mesh')
    return j

def blender_convert(b,op,target):
    import tempfile, subprocess, shutil
    j=check_embedded_model(b)
    if op=='reduce' and (j.get('skins') or j.get('animations') or any(p.get('targets') for m in j['meshes'] for p in m.get('primitives',[]))):raise ValueError('Rig, animation or morph data cannot be reduced safely')
    exe=shutil.which('blender')
    if not exe:raise RuntimeError('Blender not installed')
    with tempfile.TemporaryDirectory(prefix='forge-') as d:
        src=Path(d)/'input.glb';dest=Path(d)/('output.glb' if op=='reduce' else 'output.fbx');src.write_bytes(b)
        res=subprocess.run([exe,'--background','--factory-startup','--disable-autoexec','-t','2','--python-exit-code','7','--python',str(ROOT/'blender_tools.py'),'--',str(src),str(dest),op,str(target)],cwd=d,capture_output=True,timeout=180,check=False)
        if res.returncode or not dest.is_file():raise RuntimeError('Blender conversion failed: '+res.stderr.decode(errors='replace')[-300:])
        if dest.stat().st_size>MAX_GLB:raise ValueError('Output exceeds 75 MB')
        result=dest.read_bytes()
        if op=='reduce':check_embedded_model(result)
        elif not result.startswith(b'Kaydara FBX Binary'):raise ValueError('Invalid FBX')
        return result

@app.get('/api/model/capabilities')
def capabilities():
    import shutil
    return {'obj':True,'reduce':bool(shutil.which('blender')),'fbx':bool(shutil.which('blender'))}

@app.post('/api/model/blender')
async def blender_api(request:Request,operation:str,target:int=5000):
    import shutil
    if operation not in ('reduce','fbx') or target not in (1000,5000,15000,30000):raise HTTPException(400,'Geçersiz işlem veya hedef.')
    if not shutil.which('blender'):raise HTTPException(503,'Blender sunucuda kurulu değil.')
    if request.headers.get('content-type','').split(';')[0]!='model/gltf-binary':raise HTTPException(415,'GLB gerekli.')
    if not busy.acquire(blocking=False):raise HTTPException(409,'Motor meşgul.')
    try:
        buf=bytearray()
        async for chunk in request.stream():
            if len(buf)+len(chunk)>MAX_GLB:raise HTTPException(413,'GLB 75 MB sınırı.')
            buf.extend(chunk)
        try:result=await run_in_threadpool(blender_convert,bytes(buf),operation,target)
        except Exception:
            logging.exception('Blender operation failed');raise HTTPException(400,'İşlem başarısız; model veya sunucu kaydını kontrol edin.')
        return Response(result,media_type='model/gltf-binary' if operation=='reduce' else 'application/octet-stream')
    finally:busy.release()


@app.post('/api/model/components')
async def components(request:Request,index:int=-1,prune:bool=False):
    if prune and index<0:raise HTTPException(400,'Açık parça seçimi gerekli.')
    if index < -1 or index > 4095:raise HTTPException(400,'Geçersiz parça.')
    if request.headers.get('content-type','').split(';')[0]!='model/gltf-binary':raise HTTPException(415,'GLB gerekli.')
    if not busy.acquire(blocking=False):raise HTTPException(409,'Motor meşgul.')
    try:
        buf=bytearray()
        async for chunk in request.stream():
            if len(buf)+len(chunk)>MAX_GLB:raise HTTPException(413,'GLB 75 MB sınırı.')
            buf.extend(chunk)
        try:
            from parts import component_operation
            raw=bytes(buf);j=check_embedded_model(raw)
            result=await run_in_threadpool(component_operation,raw,j,None if index==-1 else index,prune)
            if index==-1:return result
            check_embedded_model(result)
            if len(result)>MAX_GLB:raise ValueError('Output too large')
            return Response(result,media_type='model/gltf-binary')
        except Exception:
            logging.exception('Component operation failed');raise HTTPException(400,'Yalnızca tek statik mesh desteklenir. Temizleme için küçük, ana gövde dışı bir parça seçin.')
    finally:busy.release()
