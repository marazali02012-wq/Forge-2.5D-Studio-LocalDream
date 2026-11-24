"""Reject malformed or repetitive generation prompts; not a semantic verifier."""
import re
from collections import Counter

SYSTEM = {
    'image': 'Translate the request into concise English for image generation. Preserve the subject and every explicit constraint. Add no new objects. Use a plain background only if compatible with the request.',
    'texture': 'Translate the request into concise English for texture generation. Preserve material, color, finish and exclusions; do not add geometry.',
    'model': 'Translate the request into concise English for 3D generation. Preserve the subject, proportions, counts, materials and exclusions.'
}

def checked_prompt(result):
    choice = result['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Incomplete AI prompt')
    out = choice['message']['content']
    if not isinstance(out, str) or not 1 <= len(out.strip()) <= 1000:
        raise ValueError('Invalid AI prompt length')
    out = out.strip()
    words = re.findall(r"[^\W_]+", out.casefold())
    if not words or not re.search(r'[A-Za-z]', out) or any(ord(c)<32 and c not in '\n\t\r' for c in out):
        raise ValueError('Invalid AI prompt text')
    for n in (1, 2, 3, 4):
        grams = [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
        if grams and max(Counter(grams).values()) >= max(5, len(grams)*0.30):
            raise ValueError('Repetitive AI prompt')
    return out

def generate_prompt(model, text, purpose):
    if purpose not in SYSTEM or not isinstance(text,str) or not 1<=len(text.strip())<=500:
        raise ValueError('Invalid prompt request')
    messages=[{'role':'system','content':SYSTEM[purpose]+' Understand the original language, including mixed scripts. Return only the English prompt, at most 1000 characters. Preserve negations. If uncertain, avoid inventing details.'},{'role':'user','content':text.strip()}]
    result=model.create_chat_completion(messages=messages,max_tokens=240,temperature=0.0,repeat_penalty=1.15)
    return checked_prompt(result)
