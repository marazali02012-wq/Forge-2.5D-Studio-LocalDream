"""Forge TRELLIS.2 proxy — remote ZeroGPU only; never starts a paid GPU."""
from __future__ import annotations
import os
import hmac
import shutil
import struct
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client, handle_file
from PIL import Image, UnidentifiedImageError

ACCESS_TOKEN = os.environ.get("FORGE_ACCESS_TOKEN", "")
if len(ACCESS_TOKEN) < 16:
    raise RuntimeError("FORGE_ACCESS_TOKEN must have at least 16 characters")
HF_TOKEN = os.environ.get("HF_TOKEN") or None
SPACE = "microsoft/TRELLIS.2"
ORIGINS = ["null"] + [x.strip() for x in os.environ.get("FORGE_ALLOWED_ORIGINS", "").split(",") if x.strip()]
app = FastAPI(title="Forge TRELLIS.2 proxy", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["X-Forge-Token", "Content-Type"])
pool = ThreadPoolExecutor(max_workers=1)
jobs: dict[str, dict] = {}
lock = threading.Lock()

def auth(x_forge_token: str | None) -> None:
    if not x_forge_token or not hmac.compare_digest(x_forge_token, ACCESS_TOKEN):
        raise HTTPException(401, detail="Erişim anahtarı geçersiz")

def validate_glb(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 40 or path.stat().st_size > 90 * 1024 * 1024:
        return False
    with path.open("rb") as f:
        head = f.read(20)
        magic, version, length, json_length, json_type = struct.unpack("<IIIII", head)
        if magic != 0x46546C67 or version != 2 or length != path.stat().st_size or json_type != 0x4E4F534A:
            return False
        import json
        body = json.loads(f.read(json_length).decode("utf-8"))
        return body.get("asset", {}).get("version") == "2.0" and bool(body.get("meshes"))

def set_state(id: str, status: str, message: str, glb: str | None = None) -> None:
    with lock:
        jobs[id].update(status=status, message=message)
        if glb:
            jobs[id]["glb"] = glb

def run_job(id: str, image_path: Path, folder: Path) -> None:
    try:
        set_state(id, "running", "Hugging Face bağlantısı kuruluyor")
        client = Client(SPACE, hf_token=HF_TOKEN)
        # Keep one Gradio Client/session for generation and export: gr.State holds the latent.
        client.predict(api_name="/start_session")
        set_state(id, "running", "Resim hazırlanıyor")
        preprocessed = client.predict(handle_file(str(image_path)), api_name="/preprocess_image")
        if not isinstance(preprocessed, str) or not Path(preprocessed).is_file():
            raise RuntimeError("Hugging Face hazırlanmış resim döndürmedi")
        set_state(id, "running", "Gerçek 3D geometri ve PBR kaplama üretiliyor")
        client.predict(
            handle_file(preprocessed), 0, "512",
            7.5, 0.7, 12, 5.0,
            7.5, 0.5, 12, 3.0,
            1.0, 0.0, 12, 3.0,
            api_name="/image_to_3d",
        )
        set_state(id, "running", "Kaplamalı GLB dışa aktarılıyor")
        out = client.predict(100000, 1024, api_name="/extract_glb")
        candidates = out if isinstance(out, (tuple, list)) else [out]
        path = next((Path(p) for p in candidates if isinstance(p, str) and Path(p).is_file()), None)
        if path is None:
            raise RuntimeError("Hugging Face GLB dosyası döndürmedi")
        dest = folder / "output.glb"
        shutil.copyfile(path, dest)
        if not validate_glb(dest):
            dest.unlink(missing_ok=True)
            raise RuntimeError("Alınan GLB dosyası geçersiz ya da mesh içermiyor")
        set_state(id, "done", "Gerçek GLB doğrulandı", str(dest))
    except Exception as exc:
        # Never fake completion; detailed upstream trace stays server-side.
        message = str(exc)[:320]
        set_state(id, "failed", "Üretim başarısız (ZeroGPU kota, sıra veya API): " + message)
    finally:
        image_path.unlink(missing_ok=True)

@app.get("/health")
def health():
    return {"status": "ready", "space": SPACE, "paid_gpu_started": False, "hf_token_configured": bool(HF_TOKEN)}

@app.post("/api/jobs", status_code=202)
async def create_job(image: UploadFile = File(...), x_forge_token: str | None = Header(default=None)):
    auth(x_forge_token)
    with lock:
        if any(v["status"] in ("queued", "running") for v in jobs.values()):
            raise HTTPException(429, detail="Bir üretim devam ediyor")
    if image.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(415, detail="Yalnızca PNG/JPG/WEBP kabul edilir")
    content = await image.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024 or len(content) < 32:
        raise HTTPException(413, detail="Resim 10 MB altında olmalı")
    folder = Path(tempfile.mkdtemp(prefix="forge_trellis_"))
    original = folder / "input.png"
    try:
        from io import BytesIO
        with Image.open(BytesIO(content)) as im:
            if im.format not in ("PNG", "JPEG", "WEBP") or im.width > 4096 or im.height > 4096:
                raise ValueError("Desteklenmeyen görsel biçimi veya ölçüsü")
            im.convert("RGBA").save(original, "PNG")
    except (UnidentifiedImageError, ValueError, OSError) as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(415, detail="Geçersiz resim") from exc
    id = uuid.uuid4().hex
    with lock:
        jobs[id] = {"status": "queued", "message": "Sıraya alındı", "glb": None}
    pool.submit(run_job, id, original, folder)
    return {"id": id, "status": "queued"}

@app.get("/api/jobs/{id}")
def job_status(id: str, x_forge_token: str | None = Header(default=None)):
    auth(x_forge_token)
    with lock:
        j = jobs.get(id)
        if j is None:
            raise HTTPException(404, detail="İş bulunamadı")
        return {"id": id, "status": j["status"], "message": j["message"]}

@app.get("/api/jobs/{id}/glb")
def download(id: str, x_forge_token: str | None = Header(default=None)):
    auth(x_forge_token)
    with lock:
        j = jobs.get(id)
        if not j:
            raise HTTPException(404, detail="İş bulunamadı")
        path = j["glb"] if j["status"] == "done" else None
    if not path or not validate_glb(Path(path)):
        raise HTTPException(409, detail="Doğrulanmış GLB hazır değil")
    return FileResponse(path, media_type="model/gltf-binary", filename=f"trellis2_{id}.glb")
