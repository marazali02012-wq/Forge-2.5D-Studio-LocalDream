"""Optional Hunyuan3D worker. Operator-configured HTTPS endpoint or local worker.
No browser-supplied destinations, redirects, or implicit third-party upload.
"""
import base64,json,os,urllib.request,urllib.parse,ssl,ipaddress
BASE='http://127.0.0.1:8081'
MAX_GLB=75*1024*1024
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def configuration():
    raw=os.environ.get('FORGE_HUNYUAN_URL',BASE).strip().rstrip('/')
    u=urllib.parse.urlsplit(raw)
    if not u.hostname or u.username is not None or u.password is not None or u.query or u.fragment or u.path not in ('','/') or any(c.isspace() for c in raw):raise ValueError('Invalid worker URL')
    port=u.port  # validates port
    local=u.hostname in ('127.0.0.1','localhost','::1')
    if local:
        if u.scheme not in ('http','https'):raise ValueError('Invalid local protocol')
    else:
        if u.scheme!='https':raise ValueError('Remote worker requires HTTPS')
        # External GPU endpoint must be a named host, not a private or literal IP.
        try:ipaddress.ip_address(u.hostname)
        except ValueError:pass
        else:raise ValueError('Remote worker requires a DNS hostname')
        if '.' not in u.hostname or u.hostname.endswith(('.local','.internal','.localhost')):raise ValueError('Invalid remote hostname')
    token=os.environ.get('FORGE_HUNYUAN_TOKEN','')
    if not local and (len(token)<16 or not token.isascii() or any(c.isspace() for c in token)):raise ValueError('Remote worker requires a bearer token of at least 16 characters')
    if token and (not token.isascii() or any(c.isspace() for c in token)):raise ValueError('Invalid worker token')
    return raw,token,'local' if local else 'remote'

def request(path, payload=None, limit=4096, timeout=4):
    if path not in ('/health','/generate'):raise ValueError('Invalid worker route')
    base,token,_=configuration()
    data=None if payload is None else json.dumps(payload).encode()
    headers={'Content-Type':'application/json'} if data else {}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(base+path,data=data,headers=headers)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(req,timeout=timeout) as r:
        length=r.headers.get('Content-Length')
        if length and int(length)>limit:raise ValueError('Yanıt boyutu sınırı aşıldı')
        result=r.read(limit+1)
        if len(result)>limit:raise ValueError('Yanıt boyutu sınırı aşıldı')
        return result

def health():
    if os.environ.get('FORGE_HUNYUAN_ENABLE')!='1':return {'configured':False,'reachable':False,'inference_verified':False,'detail':'Hunyuan worker etkin değil.'}
    try:_,_,mode=configuration()
    except Exception:return {'configured':False,'reachable':False,'inference_verified':False,'detail':'Worker ayarı geçersiz. Uzak sunucu için HTTPS ve erişim anahtarı gerekli.'}
    try:ok=json.loads(request('/health')).get('status')=='healthy'
    except Exception:ok=False
    return {'configured':True,'reachable':ok,'inference_verified':False,'connection':mode,'detail':'Worker erişilebilir; üretim kalitesi doğrulanmadı.' if ok else 'GPU worker erişilemiyor.'}

def generate(png,texture,seed):
    if os.environ.get('FORGE_HUNYUAN_ENABLE')!='1':raise RuntimeError('Worker disabled')
    return request('/generate',{'image':base64.b64encode(png).decode(),'texture':texture,'seed':seed,'type':'glb'},MAX_GLB,600)
