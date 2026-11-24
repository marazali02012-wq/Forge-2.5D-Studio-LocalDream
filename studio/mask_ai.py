"""Optional local U2NetP segmentation; no downloads during inference."""
import os, hashlib, importlib.util, io
from functools import lru_cache
from pathlib import Path
from PIL import Image

MODEL_MD5='8e83ca70e441ab06c318d82300c84806'
ROOT=Path(__file__).resolve().parent
_session=None
_key=None

def model_path():
    return Path(os.environ.get('FORGE_MASK_MODEL') or ROOT/'models'/'u2netp.onnx').expanduser().resolve()

@lru_cache(maxsize=4)
def checksum_ok(path, size, mtime_ns):
    try:
        with open(path,'rb') as f:
            return hashlib.file_digest(f,'md5').hexdigest()==MODEL_MD5
    except OSError:
        return False

def diagnose():
    p=model_path(); issues=[]
    for name in ('onnxruntime','numpy'):
        if importlib.util.find_spec(name) is None:issues.append(name+' eksik')
    try:
        st=p.stat()
        if not p.is_file() or not 1000000<=st.st_size<=20000000:issues.append('u2netp.onnx geçersiz boyut')
        elif not checksum_ok(str(p),st.st_size,st.st_mtime_ns):issues.append('u2netp.onnx sağlama toplamı hatalı')
    except OSError:issues.append('u2netp.onnx eksik')
    return {'configured':not issues,'issues':issues,'engine':'U2NetP CPU','inference_verified':False}

def mask_image(image):
    import numpy as np
    import onnxruntime as ort
    global _session,_key
    p=model_path();key=(str(p),p.stat().st_size,p.stat().st_mtime_ns)
    if _session is None or _key!=key:
        if not checksum_ok(*key):raise ValueError('U2NetP checksum mismatch')
        opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
        _session=ort.InferenceSession(str(p),sess_options=opts,providers=['CPUExecutionProvider']);_key=key
    rgb=image.convert('RGB');a=np.asarray(rgb.resize((320,320),Image.Resampling.LANCZOS),dtype=np.float32)
    peak=float(a.max())
    if peak<=0:raise ValueError('Empty RGB input')
    a=(a/peak-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    pred=np.asarray(_session.run(None,{_session.get_inputs()[0].name:a.transpose(2,0,1)[None]})[0],dtype=np.float32).squeeze()
    if pred.shape!=(320,320) or not np.isfinite(pred).all() or float(np.ptp(pred))<.01:raise ValueError('Invalid mask prediction')
    alpha=Image.fromarray(np.uint8(np.clip((pred-pred.min())/np.ptp(pred),0,1)*255)).resize(rgb.size,Image.Resampling.LANCZOS)
    v=np.asarray(alpha);ratio=float((v>=128).mean())
    if not .01<=ratio<=.995:raise ValueError('Unreliable foreground ratio')
    result=rgb.convert('RGBA');result.putalpha(alpha);buf=io.BytesIO();result.save(buf,format='PNG');return buf.getvalue()
