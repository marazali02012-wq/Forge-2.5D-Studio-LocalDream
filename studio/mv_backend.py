"""Local calibrated PNG bundle runner; no external service."""
import io,json,os,re,sys,tempfile,subprocess,time,zipfile,stat,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'multiview'
LIMIT=25*1024*1024

def interpreter():
    p=Path(os.environ.get('FORGE_MULTIVIEW_PYTHON',sys.executable))
    if not p.is_absolute() or not p.is_file() or not os.access(p,os.X_OK):raise ValueError('Çok açılı Python ortamı bulunamadı.')
    return str(p)

def diagnose():
    try:
        p=subprocess.run([interpreter(),'-c','import numpy, scipy, cv2, trimesh, numba, skimage, PIL, networkx'],capture_output=True,timeout=5)
        if p.returncode:raise ValueError('Çok açılı motor bağımlılıkları eksik.')
        return {'configured':True,'detail':'Kalibre edilmiş PNG motoru hazır. AI üretimi değildir.'}
    except (ValueError,OSError,subprocess.TimeoutExpired):return {'configured':False,'detail':'Yerel motor kurulumu eksik veya kontrol başarısız.'}

def unpack_bundle(raw,folder):
    if not 0<len(raw)<=LIMIT:raise ValueError('ZIP boyutu 25 MB sınırı dışında.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members=z.infolist();names=[m.filename for m in members]
            if not 4<=len(names)<=25 or len(set(names))!=len(names) or 'manifest.json' not in names:raise ValueError('ZIP içinde manifest.json ve 3–24 PNG olmalı.')
            if sum(m.file_size for m in members)>40*1024*1024:raise ValueError('Açılmış ZIP 40 MB sınırını aşıyor.')
            for m in members:
                if not re.fullmatch(r'(?:manifest\.json|[A-Za-z0-9_-]{1,64}\.png)',m.filename) or m.is_dir() or m.flag_bits&1 or stat.S_ISLNK(m.external_attr>>16) or m.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('ZIP yalnız düz PNG ve manifest dosyaları içermeli.')
                if not 0<m.file_size<=(65536 if m.filename=='manifest.json' else 8*1024*1024):raise ValueError('Girdi dosyası boyut sınırı.')
            manifest=json.loads(z.read('manifest.json'));files=[r['file'] for r in manifest['views']]
            if manifest.get('schema')!='forge-orthographic-v1' or not 3<=len(files)<=24 or len(files)!=len(set(files)) or set(files)!=set(names)-{'manifest.json'}:raise ValueError('Manifest ve ZIP görüntüleri uyuşmuyor.')
            for m in members:
                data=z.read(m)
                if len(data)!=m.file_size:raise ValueError('Geçersiz ZIP üyesi.')
                (folder/m.filename).write_bytes(data)
    except (zipfile.BadZipFile,KeyError,TypeError,AttributeError,UnicodeError,RuntimeError,NotImplementedError) as e:raise ValueError('Geçersiz ZIP veya manifest.') from e

def generate(raw,tile=0,cancel=None):
    if tile not in (0,10,12,14):raise ValueError('UV modu geçersiz.')
    with tempfile.TemporaryDirectory(prefix='forge-multiview-') as tmp:
        work=Path(tmp);unpack_bundle(raw,work);out=work/'output';log=work/'runtime.log'
        cmd=[interpreter(),str(ROOT/'pipeline.py'),str(work/'manifest.json'),str(out),'--tile',str(tile)]
        start=time.monotonic()
        with log.open('wb') as f:
            proc=subprocess.Popen(cmd,cwd=work,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMBA_NUM_THREADS='2',NUMBA_CACHE_DIR=str(work/'numba')))
            try:
                while proc.poll() is None:
                    if cancel is not None and cancel.is_set():raise RuntimeError('İşlem iptal edildi.')
                    if time.monotonic()-start>180:raise TimeoutError('Çok açılı üretim zaman aşımı.')
                    if log.stat().st_size>2*1024*1024:raise RuntimeError('Motor kayıt sınırı.')
                    time.sleep(.1)
                if cancel is not None and cancel.is_set():raise RuntimeError('İşlem iptal edildi.')
                if proc.returncode:raise RuntimeError('Kalibrasyon, görüntüler veya yerel üretim başarısız.')
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
        file=out/'model.glb';report=out/'report.json'
        if not file.is_file() or not 0<file.stat().st_size<=75*1024*1024 or not report.is_file() or report.stat().st_size>512*1024:raise RuntimeError('GLB veya rapor doğrulaması başarısız.')
        r=json.loads(report.read_text());b=file.read_bytes()
        if r['glb_roundtrip'] is not True or r['removed_components']!=0 or hashlib.sha256(b).hexdigest()!=r['sha256']:raise RuntimeError('GLB bütünlüğü bozuk.')
        return b,{'views':r['views'],'triangles':r['triangles'],'components':r['components'],'coverage':r['bake']['area_weighted_coverage'],'removed_components':0,'seconds':round(time.monotonic()-start,2),'scope':'calibrated_multiview_rgb_not_ai'}
