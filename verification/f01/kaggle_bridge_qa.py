"""Exercise Forge's actual HTTP handler against an isolated provider double."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio/cloud-ai"))
os.environ["FORGE_API_TOKEN"] = "forge-local-test-access-not-a-real-key"
os.environ["FORGE_ALLOWED_ORIGINS"] = "null"
from kaggle_provider import Kaggle, ProviderError
from private_api_kaggle import BoundedServer, Jobs, KaggleHandler, MAX_WAIT, ORIGINS, TOKEN


class TestProvider:
    def __init__(self, model=b"test model"):
        self.model = model
        self.submissions = 0
        self.uploads = 0
        self.remote = "queued"
        self.admitted = True
        self.lost_submission_response = False

    def admission(self):
        return self.admitted

    def create_dataset(self, slug, raw, suffix):
        assert slug.startswith("forge-f01-input-") and raw and suffix == "png"
        self.uploads += 1

    def dataset_ready(self, slug):
        return True

    def notebook_exists(self, slug, dataset):
        return self.submissions > 0

    def submit(self, slug, dataset, job, digest):
        assert slug.startswith("forge-f01-job-") and job == digest
        self.submissions += 1
        if self.lost_submission_response:
            raise ProviderError()

    def status(self, slug):
        return self.remote

    def output(self, slug, job, digest):
        return self.model, {}


def image():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


def server_for(jobs):
    handler = type("TestHandler", (KaggleHandler,), {"jobs": jobs})
    return BoundedServer(("127.0.0.1", 0), handler)


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.provider = TestProvider()
        self.jobs = Jobs(Path(self.directory.name), self.provider, lambda model, _: model)
        self.server = server_for(self.jobs)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.directory.cleanup()

    def request(self, method="POST", path="/v1/kaggle-jobs", raw=None, token=TOKEN, origin="null"):
        headers = {"Authorization": "Bearer " + token, "Content-Type": "image/png", "Origin": origin}
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, raw, headers)
            response = connection.getresponse()
            result = response.read()
            if response.getheader("Content-Type") == "application/json":
                result = json.loads(result)
            return response.status, result
        finally:
            connection.close()

    def test_concurrent_retries_timeout_recovery_and_output(self):
        raw = image()
        with ThreadPoolExecutor(4) as pool:
            responses = list(pool.map(lambda _: self.request(raw=raw), range(4)))
        self.assertTrue(all(status == 202 for status, _ in responses))
        job = hashlib.sha256(raw).hexdigest()
        self.assertEqual({body["id"] for _, body in responses}, {job})
        path = "/v1/kaggle-jobs/" + job
        self.assertEqual(self.jobs.add(b"different", "png"), None)

        self.provider.admitted = False
        self.jobs.tick()
        self.assertEqual(self.provider.uploads, 0)
        self.provider.admitted = True
        self.provider.lost_submission_response = True
        self.jobs.tick()
        self.jobs.tick()
        self.assertEqual(self.request("GET", path)[1]["status"], "submitting")

        restarted = Jobs(Path(self.directory.name), self.provider, lambda model, _: model)
        restarted.tick()
        restarted.tick()
        self.assertEqual(self.request("GET", path)[1]["status"], "queued")
        with self.jobs.connect() as db:
            db.execute("UPDATE jobs SET created = ?", (time.time() - MAX_WAIT - 1,))
        self.assertEqual(self.request("GET", path)[1]["status"], "timed_out")
        self.assertIsNone(self.jobs.add(b"another", "png"))
        self.assertEqual(self.request(raw=raw)[1]["id"], job)
        self.assertEqual(self.request("GET", path + "/model")[0], 404)

        self.provider.remote = "running"
        restarted.tick()
        self.assertEqual(restarted.get(job)["state"], "running")
        self.provider.remote = "complete"
        restarted.tick()
        restarted.tick()
        self.assertEqual(self.request("GET", path)[1]["status"], "ready")
        self.assertEqual(self.request("GET", path + "/model"), (200, b"test model"))
        self.assertEqual((self.provider.uploads, self.provider.submissions), (1, 1))

    def test_invalid_upload_access_and_remote_failure(self):
        self.assertEqual(self.request(raw=image(), token="bad")[0], 401)
        self.assertEqual(self.request(raw=image(), origin="https://other.invalid")[0], 403)
        self.assertEqual(self.request(raw=b"not a PNG")[0], 400)
        job = self.request(raw=image())[1]["id"]
        for _ in range(4):
            self.jobs.tick()
        self.provider.remote = "error"
        self.jobs.tick()
        path = "/v1/kaggle-jobs/" + job
        self.assertEqual(self.request("GET", path)[1]["status"], "error")
        self.assertEqual(self.request("GET", path + "/model")[0], 404)
        self.assertEqual(self.request(raw=image())[1]["id"], job)
        self.assertEqual(self.provider.submissions, 1)

    def test_admission_requires_confirmed_free_scaling_and_terminal_job(self):
        provider = Kaggle("fixture", "KGAT_fixture", "existing")
        baseline = {"totalTimeAllowed": "108000s", "timeUsed": "4200s", "timeReserved": "0s"}
        def simulate(state, quota):
            def rpc(service, method, payload):
                if method == "GetKernelSessionStatus":
                    return {"status": state}
                if method == "GetAcceleratorQuotaStatistics":
                    return {"gpuQuota": quota}
                self.fail("Unexpected write or RPC")
            provider.rpc = rpc
        for value in (True, None, 0, "false"):
            with self.subTest(paid=value):
                simulate("COMPLETE", {**baseline, "isPayToScaleEnabled": value})
                self.assertFalse(provider.admission())
        # Live 2026-11-28 reply shape: the default False is omitted by kagglesdk.
        simulate("COMPLETE", baseline)
        self.assertTrue(provider.admission())
        simulate("COMPLETE", {"timeUsed": "4200s"})
        self.assertFalse(provider.admission())
        simulate("COMPLETE", None)
        self.assertFalse(provider.admission())
        for state in ("QUEUED", "RUNNING", "CANCEL_REQUESTED", 0, "UNKNOWN"):
            simulate(state, {**baseline, "isPayToScaleEnabled": False})
            self.assertFalse(provider.admission())
        simulate("COMPLETE", {**baseline, "isPayToScaleEnabled": False})
        self.assertTrue(provider.admission())
        simulate("COMPLETE", {**baseline, "timeUsed": "107000s", "isPayToScaleEnabled": False})
        self.assertFalse(provider.admission())

    def test_kaggle_rpc_status_and_binary_integrity(self):
        provider = Kaggle("fixture", "KGAT_fixture", "existing")
        provider.rpc = lambda *_: {}
        self.assertEqual(provider.status("existing"), "queued")
        self.assertFalse(provider.admission())
        provider.rpc = lambda *_: {"status": "SOMETHING_NEW"}
        self.assertEqual(provider.status("existing"), "unreported")
        provider.rpc = lambda *_: {"status": 0}
        self.assertEqual(provider.status("existing"), "queued")
        provider.rpc = lambda *_: {"status": 3}
        self.assertEqual(provider.status("existing"), "error")
        calls = []
        provider.rpc = lambda *args: calls.append(args)
        provider.submit("test-notebook", "test-dataset", "a" * 64, "b" * 64)
        self.assertEqual(len(calls), 1)
        payload = calls[0][2]
        self.assertTrue(payload["isPrivate"])
        self.assertIn("forge-f01-auto", payload["text"])
        self.assertNotIn(provider.token, payload["text"])

        provider.rpc = lambda *_: {"files": [
            {"fileName": "report.json", "url": "https://storage.googleapis.com/fixture/report.json"},
            {"fileName": "source.png", "url": "https://storage.googleapis.com/fixture/source.png"},
            {"fileName": "model.glb", "url": "https://storage.googleapis.com/fixture/model.glb"},
        ]}
        output = {"report.json": b"{}", "source.png": image(), "model.glb": b"bad"}
        provider.read = lambda request, *_: output[request.full_url.rsplit("/", 1)[1]]
        with self.assertRaises(ValueError):
            provider.output("test-notebook", "id", "digest")

    def test_cpu_session_skips_gpu_queue_and_ships_exact_sources(self):
        provider = Kaggle("fixture", "KGAT_fixture", "existing", accelerator="cpu")
        provider.rpc = lambda *_: self.fail("CPU admission must not query GPU state or quota")
        self.assertTrue(provider.admission())
        calls = []
        provider.rpc = lambda *args: calls.append(args)
        provider.submit("test-notebook", "test-dataset", "a" * 64, "a" * 64)
        payload = calls[0][2]
        self.assertFalse(payload["enableGpu"])
        self.assertFalse(payload["enableTpu"])
        self.assertNotIn("machineShape", payload)
        self.assertTrue(payload["isPrivate"])
        self.assertNotIn(provider.token, payload["text"])
        namespace = {}
        exec(payload["text"].split('"""F01 private Kaggle CPU session', 1)[0], namespace)
        root = Path(__file__).resolve().parents[2] / "studio/cloud-ai"
        for name in ("forge_mask.py", "triposg_cpu.py"):
            self.assertEqual(namespace["FORGE_FILES"][name], (root / name).read_text())
        self.assertEqual(namespace["FORGE_IMAGE_SHA256"], "a" * 64)
        self.assertIs(namespace["FORGE_BF16"], False)
        provider.rpc = lambda *_: {"metadata": {
            "isPrivate": True, "currentVersionNumber": 1,
            "datasetDataSources": ["fixture/test-dataset"]}}
        self.assertTrue(provider.notebook_exists("test-notebook", "test-dataset"))
        gpu = Kaggle("fixture", "KGAT_fixture", "existing")
        gpu.rpc = provider.rpc
        with self.assertRaises(ValueError):
            gpu.notebook_exists("test-notebook", "test-dataset")
        with self.assertRaises(ValueError):
            Kaggle("fixture", "KGAT_fixture", "existing", accelerator="tpu")

    def test_dataset_creation_uses_official_api_without_cli(self):
        provider = Kaggle("fixture", "KGAT_fixture", "existing")
        calls, uploads = [], []

        def rpc(service, method, body):
            calls.append((method, body))
            if method == "GetDatasetStatus":
                raise ProviderError(403)
            if method == "StartBlobUpload":
                return {"token": "blob-token", "createUrl": (
                    "https://www.googleapis.com/upload/storage/v1/b/kaggle-data-sets/o?uploadType=resumable")}
            return {"ref": "https://www.kaggle.com/datasets/fixture/forge-f01-input-x", "status": "Ok"}
        provider.rpc = rpc
        provider.read = lambda request, *_: uploads.append(request) or b""
        raw = image()
        provider.create_dataset("forge-f01-input-x", raw, "png")
        self.assertEqual([name for name, _ in calls], ["GetDatasetStatus", "StartBlobUpload", "CreateDataset"])
        self.assertEqual(calls[1][1]["contentLength"], len(raw))
        self.assertEqual(calls[1][1]["type"], "DATASET")
        created = calls[2][1]
        self.assertIs(created["isPrivate"], True)
        self.assertEqual(created["files"], [{"token": "blob-token"}])
        self.assertEqual((uploads[0].get_method(), uploads[0].data), ("PUT", raw))
        self.assertEqual(uploads[0].get_header("Content-range"), f"bytes 0-{len(raw) - 1}/{len(raw)}")
        self.assertNotIn("KGAT_fixture", json.dumps(created))
        def missing_then(url):
            def rpc(service, method, body):
                if method == "GetDatasetStatus":
                    raise ProviderError(404)
                if method == "StartBlobUpload":
                    return {"token": "t", "createUrl": url}
                self.fail("No dataset without a verified upload")
            return rpc
        for url in ("http://storage.googleapis.com/x", "https://evil.example/x",
                    "https://user@storage.googleapis.com/x", "https://www.googleapis.com/drive/v3/x"):
            provider.rpc = missing_then(url)
            with self.assertRaises(ValueError):
                provider.create_dataset("forge-f01-input-x", raw, "png")
        # An existing dataset with the fixed slug is reused, never duplicated.
        provider.rpc = lambda s, m, b: {"status": "READY"} if m == "GetDatasetStatus" else self.fail(m)
        provider.create_dataset("forge-f01-input-x", raw, "png")
        # Creation is confirmed only by the CLI's success rule.
        def refused(service, method, body):
            if method == "GetDatasetStatus":
                raise ProviderError(404)
            if method == "StartBlobUpload":
                return {"token": "t", "createUrl": "https://storage.googleapis.com/x"}
            return {"status": "Error", "error": "slug in use"}
        provider.rpc = refused
        with self.assertRaises(ValueError):
            provider.create_dataset("forge-f01-input-x", raw, "png")

    def test_failed_dataset_creation_is_retried_once_per_minute(self):
        class Flaky(TestProvider):
            def __init__(self):
                super().__init__()
                self.created = 0

            def create_dataset(self, slug, raw, suffix):
                self.created += 1
                if self.created == 1:
                    raise ValueError("Unexpected Kaggle upload host")

            def dataset_ready(self, slug):
                if self.created < 2:
                    raise ProviderError(403)
                return True

        provider = Flaky()
        jobs = Jobs(Path(self.directory.name) / "flaky", provider, lambda model, _: model)
        job = jobs.add(image(), "png")
        jobs.tick()
        self.assertEqual((jobs.get(job)["state"], provider.created), ("dataset", 1))
        jobs.tick()
        self.assertEqual(provider.created, 1)  # rate limited
        with jobs.connect() as db:
            db.execute("UPDATE jobs SET changed = changed - 61")
        jobs.tick()
        self.assertEqual(provider.created, 2)
        for _ in range(3):
            jobs.tick()
        self.assertEqual(provider.submissions, 1)
        self.assertEqual(jobs.get(job)["state"], "queued")

    def test_missing_private_notebook_403_is_confirmed_by_listing(self):
        provider = Kaggle("fixture", "KGAT_fixture", "existing", accelerator="cpu")
        listing = {"kernels": [{"ref": "fixture/other"}]}

        def rpc(service, method, body):
            if method == "GetKernel":
                raise ProviderError(403)
            if method == "ListKernels":
                self.assertEqual(body["search"], "forge-f01-job-a")
                return listing
            self.fail(method)
        provider.rpc = rpc
        self.assertFalse(provider.notebook_exists("forge-f01-job-a", "forge-f01-input-a"))
        listing["kernels"].append({"ref": "fixture/forge-f01-job-a"})
        with self.assertRaises(ProviderError):
            provider.notebook_exists("forge-f01-job-a", "forge-f01-input-a")

        def unlisted(service, method, body):
            if method == "GetKernel":
                raise ProviderError(403)
            raise ProviderError(401)
        provider.rpc = unlisted
        with self.assertRaises(ProviderError):
            provider.notebook_exists("forge-f01-job-a", "forge-f01-input-a")


def serve_fixture(model):
    provider = TestProvider(Path(model).read_bytes())
    with tempfile.TemporaryDirectory() as directory:
        jobs = Jobs(Path(directory), provider, lambda data, _: data)
        with server_for(jobs) as server:
            ORIGINS.add(f"http://127.0.0.1:{server.server_port}")

            def run():
                while not provider.submissions:
                    jobs.tick()
                    time.sleep(.15)
                for state in ("queued",) * 9 + ("running",) * 7 + ("complete",) * 100:
                    provider.remote = state
                    jobs.tick()
                    time.sleep(.35)
            threading.Thread(target=run, daemon=True).start()
            print(server.server_port, flush=True)
            server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve-fixture":
        serve_fixture(sys.argv[2])
    else:
        unittest.main()
