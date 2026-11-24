"""Optional local-only diffusion image inference. No automatic downloads."""
import os, io, importlib.util
from pathlib import Path
from PIL import Image
PIPE=None
PIPE_KEY=None

from model_setup import diagnose, model_path, image_profile

def available():
    return diagnose('image')["configured"]

def draw(prompt, seed, reference_frame=False):
    return draw_profile(prompt, seed, image_profile(), reference_frame=reference_frame)

def draw_profile(prompt, seed, profile, reference_frame=False):
    global PIPE, PIPE_KEY
    if profile not in ('sd-turbo','sdxs','sd15') or not diagnose('image',profile)['configured']: raise RuntimeError('Local image model not configured')
    import torch
    from diffusers import AutoPipelineForText2Image, EulerDiscreteScheduler, DPMSolverMultistepScheduler
    device='cuda' if torch.cuda.is_available() else 'cpu'
    key=(profile,str(model_path('image',profile)),device)
    if PIPE is None or PIPE_KEY!=key:
        PIPE=None; PIPE_KEY=None
        import gc
        gc.collect()
        if device=='cuda':torch.cuda.empty_cache()
        options={}
        if profile=='sdxs':
            options['scheduler']=EulerDiscreteScheduler.from_pretrained(str(model_path('image',profile)),subfolder='scheduler',local_files_only=True)
        elif profile=='sd15':
            options['scheduler']=DPMSolverMultistepScheduler.from_pretrained(str(model_path('image',profile)),subfolder='scheduler',local_files_only=True)
        PIPE=AutoPipelineForText2Image.from_pretrained(str(model_path('image',profile)),local_files_only=True,torch_dtype=torch.float16 if device=='cuda' and profile!='sdxs' else torch.float32,**options).to(device)
        PIPE_KEY=key
    steps,guidance={'sdxs':(1,0.0),'sd-turbo':(4,0.0),'sd15':(16,7.0)}[profile]
    kwargs={}
    if profile=='sd15' and reference_frame:kwargs['negative_prompt']='cropped object, close-up, cut off edges, out of frame, extra objects, cluttered background'
    with torch.inference_mode():
        result=PIPE(prompt=prompt,num_inference_steps=steps,guidance_scale=guidance,width=512,height=512,generator=torch.Generator(device=device).manual_seed(seed),**kwargs)
    if getattr(result,'nsfw_content_detected',None) and any(result.nsfw_content_detected):raise ValueError('Image rejected by safety checker')
    im=result.images[0]
    if not isinstance(im,Image.Image) or im.size!=(512,512): raise ValueError('Invalid image output')
    out=io.BytesIO(); im.convert('RGB').save(out,format='PNG'); return out.getvalue()
