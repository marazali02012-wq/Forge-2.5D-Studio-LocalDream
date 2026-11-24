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
def infer(image,texture):
    from engine import generate
    return generate(image,texture)
def validate_glb(b):
    if len(b)<20 or len(b)>MAX_GLB or struct.unpack_from('<4sII',b)!=(b'glTF',2,len(b)):raise ValueError('Invalid GLB')
    n,t=struct.unpack_from('<II',b,12)
    if t!=0x4e4f534a or n>len(b)-20:raise ValueError('Invalid GLB JSON')
    j=json.loads(b[20:20+n]);p=[p for m in j['meshes'] for p in m['primitives']]
    if not any('POSITION' in x['attributes'] and 'TEXCOORD_0' in x['attributes'] for x in p):raise ValueError('No UV geometry')
    if not any('baseColorTexture' in m.get('pbrMetallicRoughness',{}) for m in j.get('materials',[])):raise ValueError('No base texture')
    if not any('bufferView' in i for i in j.get('images',[])):raise ValueError('No embedded texture')
@app.post('/api/triposr/generate')
async def generate(request:Request,texture:int=512):
    if texture not in (512,1024):raise HTTPException(400,'Doku boyutu 512 veya 1024 olmalı.')
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
            b=await run_in_threadpool(infer,image,texture);validate_glb(b)
        except Exception:
            logging.exception('TripoSR production failed');raise HTTPException(503,'TripoSR üretimi veya GLB doğrulaması başarısız. Sunucu kaydını kontrol edin.')
        return Response(b,media_type='model/gltf-binary',headers={'Cache-Control':'no-store'})
    finally:busy.release()
