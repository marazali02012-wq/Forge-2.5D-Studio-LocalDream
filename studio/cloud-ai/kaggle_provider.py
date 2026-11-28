"""Server-only Kaggle adapter for the private F01 research worker."""
import hashlib
import json
from pathlib import Path
import re
import struct
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

KERNELS = "kernels.KernelsApiService"
DATASETS = "datasets.DatasetApiService"
BLOBS = "blobs.BlobApiService"
UPLOAD_HOSTS = ("storage.googleapis.com", "www.kaggle.com", "api.kaggle.com")
TERMINAL = {"complete", "error", "cancelled"}
ENGINE_REVISION = "2c1c516d22d58db486a058d98d31bb6177344e06"


class ProviderError(Exception):
    def __init__(self, status=0):
        self.status = status
        super().__init__("Kaggle request failed")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Kaggle:
    def __init__(self, owner, token, existing, accelerator="gpu", bf16=False):
        if not re.fullmatch(r"[\w-]+", owner, re.ASCII) or not re.fullmatch(r"KGAT_[!-~]+", token):
            raise ValueError("Invalid Kaggle server configuration")
        if not re.fullmatch(r"[\w-]+", existing, re.ASCII):
            raise ValueError("Configure the existing Kaggle notebook to guard GPU admission")
        if accelerator not in ("gpu", "cpu"):
            raise ValueError("Kaggle accelerator must be gpu or cpu")
        self.owner, self.token, self.existing = owner, token, existing
        self.accelerator, self.bf16 = accelerator, bool(bf16)
        self.opener = build_opener(NoRedirect())

    def read(self, request, limit, timeout):
        try:
            with self.opener.open(request, timeout=timeout) as response:
                data = response.read(limit + 1)
        except HTTPError as exc:
            raise ProviderError(exc.code) from None
        except (OSError, ValueError):
            raise ProviderError() from None
        if len(data) > limit:
            raise ProviderError()
        return data

    def rpc(self, service, method, body):
        request = Request(
            f"https://api.kaggle.com/v1/{service}/{method}",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            data = json.loads(self.read(request, 4 * 1024 * 1024, 20))
        except (ValueError, UnicodeError):
            raise ProviderError() from None
        if not isinstance(data, dict) or data.get("error") or data.get("errorMessage"):
            raise ProviderError()
        if type(data.get("code")) is int and data["code"] >= 400:
            raise ProviderError(data["code"])
        return data

    def target(self, slug):
        return {"userName": self.owner, "kernelSlug": slug}

    def status(self, slug):
        # Each slug belongs to exactly one version. The version-label endpoint
        # has returned HTTP 404 even for a valid version during reconciliation.
        data = self.rpc(KERNELS, "GetKernelSessionStatus", self.target(slug))
        # kagglesdk serializes proto3 defaults by omission: a successful reply
        # without "status" is KernelWorkerStatus.QUEUED (0), not a lost job.
        status = data.get("status", 0)
        states = ("QUEUED", "RUNNING", "COMPLETE", "ERROR",
                  "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED", "NEW_SCRIPT")
        if type(status) is int and 0 <= status < len(states):
            status = states[status]
        return {
            "QUEUED": "queued", "RUNNING": "running", "COMPLETE": "complete",
            "ERROR": "error", "CANCEL_ACKNOWLEDGED": "cancelled",
        }.get(status, "unreported")

    def admission(self):
        if self.accelerator == "cpu":
            # CPU sessions consume no GPU/TPU quota and skip the GPU queue. The
            # job table still serialises Forge work to one active session.
            return True
        if self.status(self.existing) not in TERMINAL:
            return False
        quota = self.rpc(KERNELS, "GetAcceleratorQuotaStatistics", {}).get("gpuQuota")
        if not isinstance(quota, dict) or not isinstance(quota.get("totalTimeAllowed"), str):
            return False
        # ApiAcceleratorQuota.isPayToScaleEnabled is a non-optional bool whose
        # default (False) kagglesdk omits. Absence in a quota reply that carries
        # the required allowance is therefore "free only"; any explicit value
        # other than the JSON literal false still fails closed.
        if quota.get("isPayToScaleEnabled", False) is not False:
            return False

        def seconds(value):
            if not isinstance(value, str) or not re.fullmatch(r"\d+(\.\d+)?s", value):
                raise ProviderError()
            return float(value[:-1])

        remaining = (
            seconds(quota.get("totalTimeAllowed")) - seconds(quota.get("timeUsed", "0s"))
            - seconds(quota.get("timeReserved", "0s"))
        )
        return remaining >= 7200

    def create_dataset(self, slug, raw, suffix):
        # Official API flow (kagglesdk 0.1.38 StartBlobUpload -> PUT -> CreateDataset).
        # The former `kaggle datasets create` subprocess failed with CLI 2.2.5,
        # which does not declare its `six` import, and needed the token in a
        # child environment. Nothing here leaves the server except the image.
        media = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[suffix]
        try:
            # Idempotent: a dataset from an earlier attempt with this fixed slug
            # is reused; dataset_ready() still verifies privacy and version 1.
            self.rpc(DATASETS, "GetDatasetStatus", {"ownerSlug": self.owner, "datasetSlug": slug})
            return
        except ProviderError as exc:
            if exc.status not in (403, 404):
                raise
        started = self.rpc(BLOBS, "StartBlobUpload", {
            "type": "DATASET", "name": f"input.{suffix}", "contentType": media,
            "contentLength": len(raw), "lastModifiedEpochSeconds": int(time.time()),
        })
        token, url = started.get("token"), started.get("createUrl")
        if not isinstance(token, str) or not token or not isinstance(url, str):
            raise ProviderError()
        self.upload(url, raw, media)
        created = self.rpc(DATASETS, "CreateDataset", {
            "ownerSlug": self.owner, "slug": slug, "title": slug, "licenseName": "unknown",
            "isPrivate": True, "description": "Private Forge research input.",
            "files": [{"token": token}],
        })
        # Same success rule as the official CLI (status "ok", no error text).
        if str(created.get("status", "")).lower() != "ok" or created.get("error"):
            raise ValueError("Kaggle dataset creation not confirmed")

    def upload(self, url, raw, media):
        parts = urlsplit(url)
        host = parts.hostname or ""
        # Live 2026-11-28: createUrl is the GCS JSON upload endpoint
        # https://www.googleapis.com/upload/storage/v1/b/kaggle-data-sets/o?...
        gcs_json = host == "www.googleapis.com" and parts.path.startswith("/upload/storage/")
        if (parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443)
                or not (gcs_json or host in UPLOAD_HOSTS or host.endswith(".storage.googleapis.com"))):
            raise ValueError("Unexpected Kaggle upload host")
        request = Request(url, data=bytes(raw), method="PUT", headers={
            "Content-Type": media, "Content-Length": str(len(raw)),
            "Content-Range": f"bytes 0-{len(raw) - 1}/{len(raw)}",
        })
        # Signed upload URLs carry their own authorisation; never log them.
        self.read(request, 65536, 120)

    def dataset_ready(self, slug):
        target = {"ownerSlug": self.owner, "datasetSlug": slug}
        data = self.rpc(DATASETS, "GetDatasetStatus", target)
        status = data.get("status")
        if status in (6, 7, "FAILED", "DELETED"):
            raise ValueError("Kaggle dataset failed")
        if status not in (5, "READY"):
            return False
        metadata = self.rpc(DATASETS, "GetDataset", target)
        if metadata.get("isPrivate") is not True or metadata.get("currentVersionNumber") != 1:
            raise ValueError("Dataset privacy or version not confirmed")
        return True

    def notebook_exists(self, slug, dataset):
        try:
            result = self.rpc(KERNELS, "GetKernel", self.target(slug))
        except ProviderError as exc:
            # Live 2026-11-28: GetKernel answers HTTP 403, not 404, for a private
            # slug that does not exist yet. Treat it as missing only when the
            # owner's own notebook listing succeeds and does not contain it.
            if exc.status in (403, 404) and not self.listed(slug):
                return False
            raise
        meta = result.get("metadata", {})
        if (meta.get("isPrivate") is not True or meta.get("currentVersionNumber") != 1
                or bool(meta.get("enableGpu", False)) is not (self.accelerator == "gpu")
                or meta.get("datasetDataSources") != [f"{self.owner}/{dataset}"]):
            raise ValueError("Notebook privacy, version or input not confirmed")
        return True

    def kernel_source(self, job, digest):
        header = f"FORGE_JOB_ID={job!r}\nFORGE_IMAGE_SHA256={digest!r}\n"
        if self.accelerator == "gpu":
            source = header + Path(__file__).with_name("triposg_kaggle_kernel.py").read_text()
        else:
            here = Path(__file__).parent
            files = {name: (here / name).read_text() for name in ("forge_mask.py", "triposg_cpu.py")}
            source = (header + f"FORGE_FILES={files!r}\nFORGE_BF16={self.bf16!r}\n"
                      + (here / "triposg_kaggle_cpu_kernel.py").read_text())
        compile(source, "forge_kaggle_kernel.py", "exec")
        return source

    def listed(self, slug):
        rows = self.rpc(KERNELS, "ListKernels", {
            "user": self.owner, "search": slug, "sortBy": "DATE_CREATED", "pageSize": 100,
        }).get("kernels", [])
        if not isinstance(rows, list):
            raise ProviderError()
        return any(isinstance(row, dict) and row.get("ref") == f"{self.owner}/{slug}" for row in rows)

    def submit(self, slug, dataset, job, digest):
        source = self.kernel_source(job, digest)
        gpu = self.accelerator == "gpu"
        body = {
            "slug": f"{self.owner}/{slug}", "newTitle": slug, "text": source,
            "language": "python", "kernelType": "script", "isPrivate": True,
            "enableGpu": gpu, "enableInternet": True, "enableTpu": False,
            "sessionTimeoutSeconds": 3600 if gpu else 5 * 3600,
            "kernelExecutionType": "SAVE_AND_RUN_ALL",
            "datasetDataSources": [f"{self.owner}/{dataset}"],
            "kernelDataSources": [], "competitionDataSources": [], "modelDataSources": [],
        }
        if gpu:
            body["machineShape"] = "NvidiaTeslaT4"
        self.rpc(KERNELS, "SaveKernel", body)

    def output(self, slug, job, digest):
        target = {**self.target(slug), "versionLabel": "v1", "pageSize": 100}
        entries = self.rpc(KERNELS, "ListKernelSessionOutput", target).get("files", [])
        if not isinstance(entries, list) or not all(isinstance(row, dict) for row in entries):
            raise ValueError("Unexpected output manifest")

        def download(name, limit):
            matches = [row["url"] for row in entries
                       if row.get("fileName") in (name, f"forge-f01-auto/{name}")]
            if len(matches) != 1:
                raise ProviderError()
            url = urlsplit(matches[0])
            host = url.hostname or ""
            if (url.scheme != "https" or url.username or url.password or url.port not in (None, 443)
                    or not (host in ("storage.googleapis.com", "kaggleusercontent.com")
                            or host.endswith((".storage.googleapis.com", ".kaggleusercontent.com")))):
                raise ValueError("Unexpected output host")
            # Signed download URLs are never logged or returned to the client.
            return self.read(Request(matches[0]), limit, 90)

        report = json.loads(download("report.json", 65536))
        source = download("source.png", 60 * 1024 * 1024)
        model = download("model.glb", 150 * 1024 * 1024)
        if (not isinstance(report, dict) or report.get("job_id") != job or report.get("actual_inference") is not True
                or report.get("original_sha256") != digest or report.get("engine") != "TripoSG"
                or report.get("model_revision") != ENGINE_REVISION
                or report.get("source_sha256") != hashlib.sha256(source).hexdigest()
                or report.get("glb_sha256") != hashlib.sha256(model).hexdigest()
                or report.get("bytes") != len(model) or len(model) < 28
                or struct.unpack_from("<4sII", model) != (b"glTF", 2, len(model))):
            raise ValueError("Kaggle output integrity check failed")
        return model, report
