"""Optional offline GGUF instruction model. No automatic download or external API."""
import os, importlib.util
from pathlib import Path
MODEL=None

from model_setup import diagnose, model_path

def available():
    return diagnose('prompt')["configured"]

def refine(text, purpose):
    global MODEL
    if not available(): raise RuntimeError('Local GGUF model not configured')
    from llama_cpp import Llama
    if MODEL is None:
        MODEL=Llama(model_path=str(model_path('prompt')),n_ctx=2048,n_threads=2,n_gpu_layers=0,verbose=False)
    from prompt_guard import generate_prompt
    return generate_prompt(MODEL,text,purpose)
