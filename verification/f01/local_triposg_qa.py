"""Regression for the GPU-free local provider with real detached processes.

A stub interpreter stands in for the heavy BiRefNet/TripoSG steps so the job
state machine, process lifecycle, restart reconciliation, failure handling,
output integrity and private-file cleanup are exercised in seconds. The real
models are exercised separately by triposg_cpu.py runs recorded as evidence.
"""
import hashlib
import io
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import time
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio/cloud-ai"))
os.environ.setdefault("FORGE_API_TOKEN", "forge-local-test-access-not-a-real-key")
from local_triposg_provider import LocalTripoSG
from private_api_kaggle import Jobs, LOCAL_STATUS

STUB = r'''#!/usr/bin/env python3
import hashlib, json, os, shutil, struct, sys, time
script, args = os.path.basename(sys.argv[1]), sys.argv[2:]
if os.environ.get("STUB_FAIL") == script:
    sys.exit(3)
if script == "forge_mask.py":
    shutil.copy(args[0], args[1])
    sys.exit(0)
time.sleep(float(os.environ.get("STUB_SLEEP", "0")))
doc = json.dumps({"asset": {"version": "2.0"}}).encode()
doc += b" " * (-len(doc) % 4)
glb = struct.pack("<4sII", b"glTF", 2, 20 + len(doc)) + struct.pack("<I4s", len(doc), b"JSON") + doc
out = args[3]
open(out, "wb").write(glb)
rgba = open(args[2], "rb").read()
report = {"engine": "TripoSG", "actual_inference": True, "faces": 1, "vertices": 3,
          "glb_sha256": hashlib.sha256(glb).hexdigest(), "bytes": len(glb),
          "input_sha256": hashlib.sha256(rgba).hexdigest()}
open(out[:-4] + ".report.json", "w").write(json.dumps(report))
'''


def image(color="navy"):
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(buffer, format="PNG")
    return buffer.getvalue()


class LocalProviderTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.stub = root / "python-stub"
        self.stub.write_text(STUB)
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IXUSR)
        self.state = root / "state"
        self.work = root / "work"
        os.environ.pop("STUB_FAIL", None)
        os.environ.pop("STUB_SLEEP", None)

    def tearDown(self):
        self.temp.cleanup()

    def jobs(self):
        provider = LocalTripoSG(self.work, self.stub, "/nonexistent-src", "/nonexistent-weights")
        return Jobs(self.state, provider, lambda model, report: model, LOCAL_STATUS), provider

    def run_until(self, jobs, job, states, limit=15):
        deadline = time.time() + limit
        seen = []
        while time.time() < deadline:
            jobs.tick()
            state = jobs.get(job)["state"]
            if not seen or seen[-1] != state:
                seen.append(state)
            if state in states:
                return seen
            time.sleep(.05)
        self.fail(f"Timed out in {seen}")

    def test_full_chain_restart_and_cleanup(self):
        os.environ["STUB_SLEEP"] = "1.0"
        jobs, provider = self.jobs()
        raw = image()
        job = jobs.add(raw, "png")
        self.assertEqual(job, hashlib.sha256(raw).hexdigest())
        self.run_until(jobs, job, {"queued", "running"})
        # Server restart while the detached generation keeps running.
        restarted, _ = self.jobs()
        seen = self.run_until(restarted, job, {"ready", "error"})
        self.assertEqual(seen[-1], "ready", seen)
        folder = self.work / f"forge-f01-job-{job[:32]}"
        self.assertEqual(len(list(self.work.glob("forge-f01-job-*/pid"))), 1)
        self.assertFalse(list((self.work / f"forge-f01-input-{job[:32]}").glob("input.*")))
        self.assertFalse((folder / "rgba.png").exists())
        self.assertEqual(struct.unpack_from("<4sII", restarted.model(job))[:2], (b"glTF", 2))
        self.assertEqual(oct(self.work.stat().st_mode & 0o777), "0o700")
        # Same image again: no new process, same verified model.
        self.assertEqual(restarted.add(raw, "png"), job)
        restarted.tick()
        self.assertEqual(len(list(self.work.glob("forge-f01-job-*/pid"))), 1)

    def test_failure_is_terminal_without_resubmission(self):
        os.environ["STUB_FAIL"] = "triposg_cpu.py"
        jobs, _ = self.jobs()
        raw = image("maroon")
        job = jobs.add(raw, "png")
        self.assertEqual(self.run_until(jobs, job, {"ready", "error"})[-1], "error")
        self.assertEqual(jobs.add(raw, "png"), job)
        for _ in range(3):
            jobs.tick()
        self.assertEqual(len(list(self.work.glob("forge-f01-job-*/pid"))), 1)
        # A different image may start once the failed job is terminal.
        os.environ.pop("STUB_FAIL")
        other = jobs.add(image("teal"), "png")
        self.assertEqual(self.run_until(jobs, other, {"ready", "error"})[-1], "ready")

    def test_tampered_output_is_rejected(self):
        os.environ["STUB_SLEEP"] = "0.3"
        jobs, provider = self.jobs()
        job = jobs.add(image("olive"), "png")
        self.run_until(jobs, job, {"queued", "running"})
        slug = f"forge-f01-job-{job[:32]}"
        while provider.status(slug) != "complete":
            time.sleep(.05)
        model = self.work / slug / "model.glb"
        model.write_bytes(model.read_bytes() + b"    ")
        self.assertEqual(self.run_until(jobs, job, {"ready", "error"})[-1], "error")
        self.assertIsNone(jobs.model(job))

    def test_admission_waits_for_live_process(self):
        os.environ["STUB_SLEEP"] = "1.5"
        _, provider = self.jobs()
        provider.create_dataset("forge-f01-input-a", image(), "png")
        digest = hashlib.sha256(image()).hexdigest()
        provider.submit("forge-f01-job-a", "forge-f01-input-a", digest, digest)
        self.assertFalse(provider.admission())
        with self.assertRaises(ValueError):
            provider.folder("../escape")
        deadline = time.time() + 10
        while provider.status("forge-f01-job-a") not in ("complete", "error") and time.time() < deadline:
            time.sleep(.05)
        self.assertEqual(provider.status("forge-f01-job-a"), "complete")
        self.assertTrue(provider.admission())


if __name__ == "__main__":
    unittest.main()
