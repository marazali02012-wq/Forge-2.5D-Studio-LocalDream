"""Server-local, GPU-free generation provider for the F01 job bridge.

Implements the same provider contract as kaggle_provider.Kaggle so the existing
SQLite job state machine, duplicate protection, HTTP API and editor flow are
reused unchanged. Each job runs in its own private directory as one detached
process chain: BiRefNet soft mask -> TripoSG (CPU, float32) -> GLB + report.
No credentials, uploads or third-party inference services are involved.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
STATES = ("queued", "running", "complete", "error")


class LocalTripoSG:
    def __init__(self, work, python, source, weights, steps=50, timeout=3 * 3600, sam2=None):
        self.work = Path(work)
        self.work.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.work.stat().st_mode & 0o077:
            raise ValueError("Forge local generation directory must be private")
        self.python, self.source, self.weights = str(python), str(source), str(weights)
        self.steps, self.timeout = int(steps), int(timeout)
        self.sam2 = str(sam2) if sam2 else ""

    def folder(self, slug):
        if not slug.replace("-", "").isalnum():
            raise ValueError("Invalid job slug")
        return self.work / slug

    def admission(self):
        # One CPU job at a time: the Jobs table already serializes jobs; this
        # also refuses while an orphaned process from a previous server lives.
        for state in self.work.glob("*/state"):
            if state.read_text().strip() in ("queued", "running"):
                pid = state.with_name("pid")
                if pid.exists() and self.alive(int(pid.read_text() or 0)):
                    return False
        return True

    @staticmethod
    def alive(pid):
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def create_dataset(self, slug, raw, suffix):
        folder = self.folder(slug)
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder / f"input.{suffix}").write_bytes(raw)

    def dataset_ready(self, slug):
        return any(self.folder(slug).glob("input.*"))

    def notebook_exists(self, slug, dataset):
        return (self.folder(slug) / "state").exists()

    def submit(self, slug, dataset, job, digest):
        source = self.folder(dataset)
        image = next(source.glob("input.*"))
        if hashlib.sha256(image.read_bytes()).hexdigest() != digest:
            raise ValueError("Input bytes changed")
        folder = self.folder(slug)
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder / "state").write_text("queued")
        env = {key: value for key, value in os.environ.items() if not key.endswith(("_KEY", "_TOKEN"))}
        env["HF_HUB_OFFLINE"] = "1"  # weights are pre-provisioned; never download during a request
        script = (
            "set -e\n"
            "echo running > \"$F/state\"\n"
            "timeout \"$T\" \"$P\" \"$H/forge_mask.py\" \"$I\" \"$F/rgba.png\" ${M:+--sam2-checkpoint \"$M\"}\n"
            "timeout \"$T\" \"$P\" \"$H/triposg_cpu.py\" \"$S\" \"$W\" \"$F/rgba.png\" \"$F/model.glb\" --steps \"$N\"\n"
            "echo complete > \"$F/state\"\n"
        )
        env.update(F=str(folder), T=str(self.timeout), P=self.python, H=str(HERE), I=str(image),
                   S=self.source, W=self.weights, N=str(self.steps), M=self.sam2)
        with (folder / "log.txt").open("wb") as log:
            process = subprocess.Popen(
                ["bash", "-c", script, "forge-local"], env=env, cwd=folder,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
        (folder / "pid").write_text(str(process.pid))

    def status(self, slug):
        folder = self.folder(slug)
        state_file = folder / "state"
        if not state_file.exists():
            return "unreported"
        state = state_file.read_text().strip()
        pid_file = folder / "pid"
        if state in ("queued", "running") and pid_file.exists():
            pid = int(pid_file.read_text() or 0)
            try:
                finished, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                finished = pid
            if finished == pid and not self.alive(pid):
                # Exited without writing "complete": a failed step under set -e.
                state = state_file.read_text().strip()
                if state != "complete":
                    state_file.write_text("error")
                    return "error"
        return state if state in STATES else "unreported"

    def cancel(self, slug):
        pid_file = self.folder(slug) / "pid"
        if pid_file.exists():
            try:
                os.killpg(int(pid_file.read_text()), signal.SIGTERM)
            except (ProcessLookupError, ValueError):
                pass

    def output(self, slug, job, digest):
        folder = self.folder(slug)
        model = (folder / "model.glb").read_bytes()
        report = json.loads((folder / "model.report.json").read_text())
        rgba = (folder / "rgba.png").read_bytes()
        if (report.get("engine") != "TripoSG" or report.get("actual_inference") is not True
                or report.get("glb_sha256") != hashlib.sha256(model).hexdigest()
                or report.get("input_sha256") != hashlib.sha256(rgba).hexdigest()
                or report.get("bytes") != len(model) or len(model) < 28
                or struct.unpack_from("<4sII", model) != (b"glTF", 2, len(model))):
            raise ValueError("Local output integrity check failed")
        # The private input and cut-out are no longer needed once the model is verified.
        dataset = self.folder(slug.replace("forge-f01-job-", "forge-f01-input-", 1))
        for private in [*dataset.glob("input.*"), folder / "rgba.png", folder / "model.engine_input.png"]:
            private.unlink(missing_ok=True)
        return model, report


def from_environment():
    return LocalTripoSG(
        os.environ["FORGE_LOCAL_WORK_DIR"],
        os.environ.get("FORGE_LOCAL_PYTHON", sys.executable),
        os.environ["FORGE_TRIPOSG_SOURCE"],
        os.environ["FORGE_TRIPOSG_WEIGHTS"],
        int(os.environ.get("FORGE_TRIPOSG_STEPS", "50")),
        sam2=os.environ.get("FORGE_SAM2_CHECKPOINT"),
    )
