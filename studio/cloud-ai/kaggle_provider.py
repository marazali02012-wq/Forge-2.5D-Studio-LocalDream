"""Server-only Kaggle adapter for the private F01 research worker."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

KERNELS = "kernels.KernelsApiService"
DATASETS = "datasets.DatasetApiService"
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
    def __init__(self, owner, token, existing):
        if not re.fullmatch(r"[\w-]+", owner, re.ASCII) or not re.fullmatch(r"KGAT_[!-~]+", token):
            raise ValueError("Invalid Kaggle server configuration")
        if not re.fullmatch(r"[\w-]+", existing, re.ASCII):
            raise ValueError("Configure the existing Kaggle notebook to guard GPU admission")
        self.owner, self.token, self.existing = owner, token, existing
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
        status = data.get("status")
        states = ("QUEUED", "RUNNING", "COMPLETE", "ERROR",
                  "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED", "NEW_SCRIPT")
        if type(status) is int and 0 <= status < len(states):
            status = states[status]
        return {
            "QUEUED": "queued", "RUNNING": "running", "COMPLETE": "complete",
            "ERROR": "error", "CANCEL_ACKNOWLEDGED": "cancelled",
        }.get(status, "unreported")

    def admission(self):
        if self.status(self.existing) not in TERMINAL:
            return False
        quota = self.rpc(KERNELS, "GetAcceleratorQuotaStatistics", {}).get("gpuQuota")
        if not isinstance(quota, dict) or quota.get("isPayToScaleEnabled", False) is not False:
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
        with tempfile.TemporaryDirectory(prefix="forge-kaggle-input-") as temp:
            folder = Path(temp)
            (folder / f"input.{suffix}").write_bytes(raw)
            (folder / "dataset-metadata.json").write_text(json.dumps({
                "title": slug, "id": f"{self.owner}/{slug}",
                "description": "Private Forge research input.",
                "licenses": [{"name": "unknown"}],
            }))
            subprocess.run(
                ["kaggle", "datasets", "create", "-p", temp, "-q"],
                env={
                    **{key: value for key, value in os.environ.items()
                       if not key.endswith(("_KEY", "_TOKEN"))},
                    "KAGGLE_API_TOKEN": self.token,
                },
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=120, check=True,
            )

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
            if exc.status == 404:
                return False
            raise
        meta = result.get("metadata", {})
        if (meta.get("isPrivate") is not True or meta.get("currentVersionNumber") != 1
                or meta.get("enableGpu") is not True
                or meta.get("datasetDataSources") != [f"{self.owner}/{dataset}"]):
            raise ValueError("Notebook privacy, version or input not confirmed")
        return True

    def submit(self, slug, dataset, job, digest):
        template = Path(__file__).with_name("triposg_kaggle_kernel.py").read_text()
        source = f"FORGE_JOB_ID={job!r}\nFORGE_IMAGE_SHA256={digest!r}\n" + template
        compile(source, "forge_kaggle_kernel.py", "exec")
        self.rpc(KERNELS, "SaveKernel", {
            "slug": f"{self.owner}/{slug}", "newTitle": slug, "text": source,
            "language": "python", "kernelType": "script", "isPrivate": True,
            "enableGpu": True, "enableInternet": True, "enableTpu": False,
            "machineShape": "NvidiaTeslaT4", "sessionTimeoutSeconds": 3600,
            "kernelExecutionType": "SAVE_AND_RUN_ALL",
            "datasetDataSources": [f"{self.owner}/{dataset}"],
            "kernelDataSources": [], "competitionDataSources": [], "modelDataSources": [],
        })

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
