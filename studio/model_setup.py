"""Explicit local AI provisioning. Never downloads on server startup."""
import argparse, importlib.util, json, os, sys, subprocess, functools
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEFAULTS={'image':ROOT/'models'/'sd-turbo','prompt':ROOT/'models'/'qwen2.5-1.5b-instruct-q4_k_m.gguf'}
PROMPT_PROFILES={'1.5b':('Qwen/Qwen2.5-1.5B-Instruct-GGUF',('qwen2.5-1.5b-instruct-q4_k_m.gguf',)), '7b':('Qwen/Qwen2.5-7B-Instruct-GGUF',('qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf','qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf'))}

def prompt_profile():
    name=os.environ.get('FORGE_PROMPT_PROFILE')
    if name is None:
        # Prefer validated 7B on new installs; retain existing lightweight installs.
        high=all((ROOT/'models'/f).is_file() for f in PROMPT_PROFILES['7b'][1])
        legacy=DEFAULTS['prompt'].is_file() or bool(os.environ.get('FORGE_PROMPT_MODEL'))
        name='7b' if high or not legacy else '1.5b'
    if name not in PROMPT_PROFILES:raise ValueError('Unknown prompt profile')
    return name

IMAGE_PROFILES={'sd-turbo':'stabilityai/sd-turbo','sdxs':'IDKiro/sdxs-512-0.9','sd15':'stable-diffusion-v1-5/stable-diffusion-v1-5'}

ENV={'image':'FORGE_IMAGE_MODEL','prompt':'FORGE_PROMPT_MODEL'}
DEPS={'image':('torch','diffusers','transformers','accelerate'),'prompt':('llama_cpp',)}

def image_profile():
    name=os.environ.get('FORGE_IMAGE_PROFILE','sd-turbo')
    if name not in IMAGE_PROFILES:raise ValueError('Unknown image profile')
    return name

def model_path(kind, profile=None):
    if kind=='image' and profile is not None and profile!=image_profile():
        return Path(os.environ.get('FORGE_IMAGE_FALLBACK_MODEL') or ROOT/'models'/profile).expanduser()
    default=ROOT/'models'/image_profile() if kind=='image' else DEFAULTS[kind]
    if kind=='prompt':default=ROOT/'models'/PROMPT_PROFILES[prompt_profile()][1][0]
    return Path(os.environ.get(ENV[kind]) or default).expanduser()

@functools.lru_cache(maxsize=4)
def probe_prompt_runtime(executable, package_origin, stamp):
    # A module spec is not proof that a native shared library can load.
    try:
        result=subprocess.run([executable,'-c','from llama_cpp import Llama'],capture_output=True,timeout=20)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def diagnose(kind, profile=None):
    p=model_path(kind, profile); missing=[n for n in DEPS[kind] if importlib.util.find_spec(n) is None]; issues=[]
    if kind=='prompt':
        if not p.is_file() or p.suffix.lower()!='.gguf': issues.append('GGUF model dosyası yok')
        else:
            try:
                with p.open('rb') as f: valid=f.read(4)==b'GGUF'
                if not valid or p.stat().st_size<1024:issues.append('GGUF başlığı veya boyutu geçersiz')
            except OSError: issues.append('GGUF okunamıyor')
        if p.name.endswith('-00001-of-00002.gguf'):
            second=p.with_name(p.name.replace('-00001-of-00002.gguf','-00002-of-00002.gguf'))
            try:
                with second.open('rb') as f: valid=f.read(4)==b'GGUF'
                if not valid or second.stat().st_size<1024:raise ValueError()
            except (OSError,ValueError):issues.append('GGUF ikinci parça eksik/geçersiz')
    else:
        try:
            idx=json.loads((p/'model_index.json').read_text());
            if not isinstance(idx,dict) or idx.get('_class_name')!='StableDiffusionPipeline':raise ValueError()
            for component in ('unet','vae','text_encoder'):
                folder=p/component
                if not (folder/'config.json').is_file() or not any(f.is_file() and f.stat().st_size>1024 and '.fp16.' not in f.name for f in folder.glob('*.safetensors')): issues.append(component+' ağırlığı veya yapılandırması eksik')
            if idx.get('safety_checker') not in (None,[None,None]):
                folder=p/'safety_checker'
                if not (folder/'config.json').is_file() or not (folder/'model.safetensors').is_file():issues.append('safety_checker dosyaları eksik')
            for name in ('tokenizer/tokenizer_config.json','tokenizer/vocab.json','tokenizer/merges.txt','scheduler/scheduler_config.json'):
                if not (p/name).is_file(): issues.append(name+' eksik')
        except (OSError,ValueError,TypeError):issues.append('Çizim model dizini veya model_index.json eksik/geçersiz')
    if missing:issues.append('Python paketleri eksik: '+', '.join(missing))
    elif kind=='prompt':
        spec=importlib.util.find_spec('llama_cpp')
        try:
            origin=Path(spec.origin)
            stamp=max([origin.stat().st_mtime_ns]+[f.stat().st_mtime_ns for f in (origin.parent/'lib').glob('*') if f.is_file()])
            if not probe_prompt_runtime(sys.executable,str(origin),stamp):issues.append('GGUF çalışma zamanı açılamıyor (llama_cpp / yerel kütüphane uyumsuzluğu). Kaynaktan yeniden kurun.')
        except (OSError,TypeError,AttributeError):issues.append('GGUF çalışma zamanı doğrulanamadı.')
    return {'configured':not issues,'issues':issues,'inference_verified':False}

def provision(kind, download, accept):
    # install into current Forge venv, not system Python
    if sys.prefix==sys.base_prefix:raise SystemExit('Önce Forge .venv ortamını etkinleştirin.')
    if kind=='image' and download and not accept:raise SystemExit('Seçili modelin lisansını inceleyin; --accept-image-license gerekli: https://huggingface.co/'+IMAGE_PROFILES[image_profile()])
    packages=['diffusers==0.30.3','accelerate==0.34.2','huggingface-hub>=0.23.2,<1'] if kind=='image' else ['llama-cpp-python==0.3.2','huggingface-hub>=0.23.2,<1']
    if kind=='prompt':
        env=os.environ.copy();env.setdefault('CMAKE_BUILD_PARALLEL_LEVEL','2');env.setdefault('CMAKE_ARGS','-DGGML_NATIVE=OFF')
        subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','--no-binary=llama-cpp-python','--force-reinstall','--no-deps','llama-cpp-python==0.3.2'],env=env,check=True)
        subprocess.run([sys.executable,'-m','pip','install','numpy<2','diskcache','typing-extensions','jinja2','huggingface-hub>=0.23.2,<1'],check=True)
        probe_prompt_runtime.cache_clear()
        subprocess.run([sys.executable,'-c','from llama_cpp import Llama'],check=True)
    else:
        subprocess.run([sys.executable,'-m','pip','install',*packages],check=True)
    if download:
        from huggingface_hub import hf_hub_download,snapshot_download
        target=model_path(kind)
        if kind=='prompt':
            target.parent.mkdir(parents=True,exist_ok=True)
            repo,files=PROMPT_PROFILES[prompt_profile()]
            for name in files:hf_hub_download(repo,name,local_dir=str(target.parent))
            file=target.parent/files[0]
            if file!=target: raise SystemExit('İndirilen dosya: '+str(file)+'; FORGE_PROMPT_MODEL değişkenini buna ayarlayın.')
        else:
            snapshot_download(IMAGE_PROFILES[image_profile()],local_dir=str(target),allow_patterns=['model_index.json','README.md','LICENSE*','scheduler/*','tokenizer/*','unet/config.json','unet/diffusion_pytorch_model.safetensors','vae/config.json','vae/diffusion_pytorch_model.safetensors','text_encoder/config.json','text_encoder/model.safetensors','feature_extractor/*','safety_checker/config.json','safety_checker/model.safetensors'])
    result=diagnose(kind);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['configured'] else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['status','install']);p.add_argument('kind',choices=['image','prompt','all']);p.add_argument('--download',action='store_true');p.add_argument('--accept-image-license',action='store_true');a=p.parse_args()
    kinds=('prompt','image') if a.kind=='all' else (a.kind,)
    if a.action=='status':
        result={k:diagnose(k) for k in kinds};print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if all(v['configured'] for v in result.values()) else 1
    return max(provision(k,a.download,a.accept_image_license) for k in kinds)
if __name__=='__main__':sys.exit(main())
