"""Opt-in, single-owner Forge research API. All Kaggle credentials stay here."""
from contextlib import closing
import fcntl
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from PIL import Image
from kaggle_provider import Kaggle, ProviderError
from private_api import BoundedServer, LIMIT, ORIGINS, ROOT, TOKEN
from private_api_photos import PhotoHandler

URL = "/v1/kaggle-jobs"
MEDIA = {"image/png": ("PNG", "png"), "image/jpeg": ("JPEG", "jpg"), "image/webp": ("WEBP", "webp")}
LOCAL_TERMINAL = ("ready", "error", "cancelled")
MAX_WAIT = 3 * 3600
QA = ROOT.parent.parent / "verification/f01/triposg_mobile_repair_qa.py"
JOB_ROUTE = re.compile(URL + r"/([0-9a-f]{64})(/model)?")
STATUS = {
    "waiting": "Mevcut Kaggle işi ve ücretsiz kota kontrol ediliyor.",
    "dataset": "Özel görsel Kaggle'da hazırlanıyor.",
    "submitting": "Kaggle gönderimi doğrulanıyor.",
    "unreported": "Kaggle henüz işlem durumunu bildirmedi.",
    "queued": "Kaggle GPU kuyruğunda.",
    "running": "Kaggle modeli üretiyor.",
    "checking": "GLB bütünlüğü ve mobil geometri kontrol ediliyor.",
    "ready": "Model hazır.",
    "error": "Kaggle üretimi veya GLB doğrulaması başarısız.",
    "cancelled": "Kaggle işi iptal edildi.",
    "timed_out": "Bekleme süresi doldu. Aynı görseli seçerek mevcut işi yeniden kontrol edebilirsin.",
}
KAGGLE_CPU_STATUS = {
    **STATUS,
    "waiting": "Kaggle CPU oturumu hazırlanıyor (GPU kotası kullanılmaz).",
    "queued": "Kaggle CPU oturumu başlatılıyor.",
    "running": "Kaggle CPU oturumu maskeyi ve TripoSG modelini üretiyor (yaklaşık 45-75 dk).",
}
LOCAL_STATUS = {
    **STATUS,
    "waiting": "Sunucu işlemci sırası kontrol ediliyor.",
    "dataset": "Görsel sunucuda özel klasöre alınıyor.",
    "submitting": "Sunucuda üretim başlatılıyor.",
    "unreported": "Sunucu üretim durumunu henüz bildirmedi.",
    "queued": "Sunucu işlemci sırasında.",
    "running": "Sunucu işlemcisi maskeyi ve TripoSG modelini üretiyor (CPU, yaklaşık 30-45 dk).",
    "error": "Sunucu üretimi veya GLB doğrulaması başarısız.",
    "cancelled": "Sunucu işi iptal edildi.",
}


def validate_image(raw, media):
    with Image.open(io.BytesIO(raw)) as image:
        expected, suffix = MEDIA[media]
        if (image.format != expected or image.width * image.height > 12_000_000
                or getattr(image, "n_frames", 1) != 1):
            raise ValueError("Invalid image")
        image.verify()
    return suffix


def mobile_model(raw, report):
    import numpy as np
    import trimesh

    mesh = trimesh.load(io.BytesIO(raw), file_type="glb", force="mesh", process=False)
    if (len(mesh.vertices) != report.get("vertices") or len(mesh.faces) != report.get("faces")
            or len(mesh.faces) < 100 or not np.isfinite(mesh.vertices).all()
            or not np.all(mesh.extents > 0) or mesh.visual.defined):
        raise ValueError("Unexpected TripoSG geometry")
    with tempfile.TemporaryDirectory(prefix="forge-kaggle-model-") as temp:
        source = Path(temp) / "source.glb"
        source.write_bytes(raw)
        output = Path(temp) / "lod"
        # Private research only. Never install dependencies during a request.
        subprocess.run(
            [sys.executable, str(QA), str(source), str(output), "--topology-first"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=300, check=True,
            env={key: value for key, value in os.environ.items() if not key.endswith(("_KEY", "_TOKEN"))},
        )
        if json.loads((output / "report.json").read_text()).get("geometry_gate_passed") is not True:
            raise ValueError("Mobile geometry gate rejected model")
        model = output / "candidate.glb"
        if not 28 <= model.stat().st_size <= 8_000_000:
            raise ValueError("Mobile model size exceeded")
        return model.read_bytes()


class Jobs:
    def __init__(self, directory, provider, convert=mobile_model, messages=STATUS):
        self.provider, self.convert, self.messages = provider, convert, messages
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        if directory.stat().st_mode & 0o077:
            raise ValueError("Forge Kaggle state directory must be private")
        self.database = directory / "jobs.sqlite3"
        self.worker_lock = directory / "worker.lock"
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, created REAL NOT NULL, changed REAL NOT NULL,
                state TEXT NOT NULL, suffix TEXT NOT NULL, input BLOB, model BLOB
            )""")

    def connect(self):
        db = sqlite3.connect(self.database, timeout=8)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete = ON")
        return db

    def add(self, raw, suffix):
        # One owner uses this store. Hash identity and the SQLite transaction
        # serialize retries even if two requests arrive from different devices.
        job = hashlib.sha256(raw).hexdigest()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT id FROM jobs WHERE id = ?", (job,)).fetchone()
            if prior:
                return job
            active = db.execute("SELECT 1 FROM jobs WHERE state NOT IN ('ready','error','cancelled')").fetchone()
            if active:
                return None
            now = time.time()
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL)",
                (job, now, now, "waiting", suffix, raw),
            )
        return job

    def get(self, job):
        with closing(self.connect()) as db:
            return db.execute("SELECT id, state, created FROM jobs WHERE id = ?", (job,)).fetchone()

    def model(self, job):
        with closing(self.connect()) as db:
            row = db.execute("SELECT model FROM jobs WHERE id = ? AND state = 'ready'", (job,)).fetchone()
            return row["model"] if row else None

    def move(self, job, state, model=None):
        erase_input = state in {*LOCAL_TERMINAL, "submitting"}
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE jobs SET state=?,changed=?,model=?,input=CASE WHEN ? THEN NULL ELSE input END WHERE id=?",
                (state, time.time(), model, erase_input, job),
            )

    def tick(self):
        # The OS releases this lock on crash. Writes to Kaggle follow a committed
        # local transition, so recovery only reads/reconciles uncertain writes.
        with self.worker_lock.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            with closing(self.connect()) as db:
                row = db.execute("SELECT * FROM jobs WHERE state NOT IN ('ready','error','cancelled')").fetchone()
            if row:
                self.advance(row)

    def advance(self, row):
        job, state = row["id"], row["state"]
        # Use different slugs for the dataset and notebook. Slugs are derived
        # server-side and never include the original filename.
        slug = f"forge-f01-job-{job[:32]}"
        dataset = f"forge-f01-input-{job[:32]}"
        aged = time.time() - row["created"] >= MAX_WAIT
        provider = self.provider
        try:
            if state == "waiting":
                if aged:
                    self.move(job, "error")
                elif provider.admission():
                    self.move(job, "dataset")
                    provider.create_dataset(dataset, row["input"], row["suffix"])
                return
            if state == "dataset":
                if aged:
                    self.move(job, "error")
                    return
                try:
                    ready = provider.dataset_ready(dataset)
                except ProviderError as exc:
                    # A create call that failed before the dataset existed leaves
                    # nothing to wait for. The slug is fixed, so a retry cannot
                    # produce a second dataset; it is rate limited to one a minute.
                    if (exc.status in (403, 404) and row["input"] is not None
                            and time.time() - row["changed"] >= 60):
                        self.move(job, "dataset")
                        provider.create_dataset(dataset, row["input"], row["suffix"])
                        return
                    raise
                if ready:
                    if provider.notebook_exists(slug, dataset):
                        self.move(job, "unreported")
                    elif provider.admission():
                        self.move(job, "submitting")
                        provider.submit(slug, dataset, job, job)
                return
            if state == "submitting":
                if provider.notebook_exists(slug, dataset):
                    self.move(job, "unreported")
                return
            if state == "checking":
                model, report = provider.output(slug, job, job)
                self.move(job, "ready", self.convert(model, report))
                return
            remote = provider.status(slug)
            if remote == "complete":
                self.move(job, "checking")
            elif remote != state:
                self.move(job, remote)
        except ProviderError:
            # Temporary network errors and missing Kaggle metadata cannot free a
            # possibly occupied GPU slot or trigger a second submission.
            if state == "checking" and time.time() - row["changed"] >= 900:
                self.move(job, "error")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            if state == "checking" or (state == "dataset" and isinstance(exc, ValueError)):
                self.move(job, "error")

    def run(self):
        while True:
            self.tick()
            time.sleep(15)


class KaggleHandler(PhotoHandler):
    jobs = None

    def authorize(self):
        origin = self.headers.get("Origin")
        if origin and origin not in ORIGINS:
            self.respond(403, {"error": "Origin not permitted"})
        elif not hmac.compare_digest(self.headers.get("Authorization", "").encode(), f"Bearer {TOKEN}".encode()):
            self.respond(401, {"error": "Unauthorized"})
        elif self.jobs is None:
            self.respond(503, {"error": "Kaggle araştırma motoru etkin değil."})
        else:
            return True
        return False

    def status_response(self, job, code=200):
        row = self.jobs.get(job)
        if row is None:
            self.respond(404, {"error": "İş bulunamadı."})
            return
        state = row["state"]
        if state not in LOCAL_TERMINAL and time.time() - row["created"] >= MAX_WAIT:
            state = "timed_out"
        self.respond(code, {"id": job, "status": state, "message": self.jobs.messages[state]})

    def do_GET(self):
        route = JOB_ROUTE.fullmatch(self.path)
        if not route:
            return super().do_GET()
        if not self.authorize():
            return
        job, model_path = route.groups()
        if not model_path:
            self.status_response(job)
            return
        data = self.jobs.model(job)
        if data:
            self.respond(200, data, "model/gltf-binary")
        else:
            self.respond(404, {"error": "Doğrulanmış GLB hazır değil."})

    def do_POST(self):
        if self.path != URL:
            return super().do_POST()
        if not self.authorize():
            return
        media = self.headers.get("Content-Type", "").partition(";")[0]
        if media not in MEDIA:
            self.respond(415, {"error": "PNG, JPEG veya WebP gerekli."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not 0 < size <= LIMIT or self.headers.get("Transfer-Encoding"):
            self.respond(413, {"error": "Görsel en fazla 5 MiB olabilir."})
            return
        try:
            deadline = time.monotonic() + 60
            raw = bytearray()
            while len(raw) < size:
                if time.monotonic() > deadline:
                    raise TimeoutError()
                chunk = self.rfile.read1(min(65536, size - len(raw)))
                if not chunk:
                    raise ValueError("Incomplete upload")
                raw.extend(chunk)
            suffix = validate_image(raw, media)
        except TimeoutError:
            self.respond(408, {"error": "Görsel yüklemesi zaman aşımına uğradı."})
            return
        except (OSError, ValueError, Image.DecompressionBombError):
            self.respond(400, {"error": "Görsel dosyası geçersiz."})
            return
        job = self.jobs.add(raw, suffix)
        if job is None:
            self.respond(409, {"error": "Başka bir Forge Kaggle işi etkin."})
        else:
            self.status_response(job, 202)


def main():
    kaggle_token = os.environ.pop("KAGGLE_API_TOKEN", "")
    if os.getenv("FORGE_KAGGLE_RESEARCH") == "1" and os.getenv("FORGE_LOCAL_TRIPOSG") == "1":
        raise RuntimeError("Enable either the Kaggle or the local TripoSG provider, not both")
    if os.getenv("FORGE_LOCAL_TRIPOSG") == "1":
        # GPU-free path: same job API, state machine and mobile gate; no third party.
        from local_triposg_provider import from_environment

        jobs = Jobs(Path(os.environ["FORGE_KAGGLE_STATE_DIR"]), from_environment(), messages=LOCAL_STATUS)
        KaggleHandler.jobs = jobs
        threading.Thread(target=jobs.run, daemon=True).start()
    elif os.getenv("FORGE_KAGGLE_RESEARCH") == "1":
        accelerator = os.getenv("FORGE_KAGGLE_ACCELERATOR", "gpu")
        provider = Kaggle(
            os.environ["FORGE_KAGGLE_OWNER"], kaggle_token,
            os.environ["FORGE_KAGGLE_EXISTING_SLUG"],
            accelerator=accelerator, bf16=os.getenv("FORGE_KAGGLE_BF16") == "1",
        )
        jobs = Jobs(Path(os.environ["FORGE_KAGGLE_STATE_DIR"]), provider,
                    messages=KAGGLE_CPU_STATUS if accelerator == "cpu" else STATUS)
        KaggleHandler.jobs = jobs
        threading.Thread(target=jobs.run, daemon=True).start()
    BoundedServer((os.getenv("FORGE_BIND", "127.0.0.1"), int(os.getenv("PORT", "8765"))),
                  KaggleHandler).serve_forever()


if __name__ == "__main__":
    main()
