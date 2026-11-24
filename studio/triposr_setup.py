"""Explicit, local TripoSR asset provisioning. No downloads on health or inference."""
import argparse, importlib.util, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEPS=('torch','numpy','trimesh','PIL','omegaconf','einops','transformers','huggingface_hub','skimage','xatlas','rembg')

def model_dir():
    return Path(os.environ.get('FORGE_TRIPOSR_MODEL') or ROOT/'models'/'triposr').expanduser().resolve()

def diagnose():
    p=model_dir(); issues=[]
    if not (ROOT/'upstream-triposr'/'tsr'/'system.py').is_file():issues.append('TripoSR kaynak motoru eksik')
    missing=[n for n in DEPS if importlib.util.find_spec(n) is None]
    if missing:issues.append('Eksik paketler: '+', '.join(missing))
    try:
        if (p/'config.yaml').stat().st_size<100:raise ValueError()
    except (OSError,ValueError):issues.append('TripoSR config.yaml eksik/geçersiz')
    try:
        if (p/'model.ckpt').stat().st_size<100*1024*1024:raise ValueError()
    except (OSError,ValueError):issues.append('TripoSR model.ckpt eksik veya çok küçük')
    try:
        d=json.loads((p/'dino-config.json').read_text());
        if d.get('model_type')!='vit' or d.get('hidden_size')!=768 or d.get('patch_size')!=16:raise ValueError()
    except (OSError,ValueError,AttributeError):issues.append('DINO ViT-B/16 yapılandırması eksik/geçersiz')
    return {'configured':not issues,'issues':issues,'inference_verified':False,'network_at_inference':False,'detail':'Dosya ön kontrolü; gerçek çıkarım doğrulanmadı.'}

def install():
    from huggingface_hub import hf_hub_download
    import shutil
    p=model_dir();p.mkdir(parents=True,exist_ok=True)
    for name in ('config.yaml','model.ckpt'):
        hf_hub_download('stabilityai/TripoSR',name,local_dir=str(p))
    source=hf_hub_download('facebook/dino-vitb16','config.json')
    shutil.copyfile(source,p/'dino-config.json')
    return diagnose()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['status','download']);args=a.parse_args()
    try:r=install() if args.action=='download' else diagnose()
    except Exception as e:r={'configured':False,'issues':['İndirme başarısız: '+type(e).__name__],'inference_verified':False}
    print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(0 if r['configured'] else 1)
