"""F01 HARD10 batch on private Kaggle CPU sessions (no GPU quota, no queue).

Uses the production provider (kaggle_provider.Kaggle, accelerator="cpu") so
every job gets the same guarantees as the editor bridge: slugs derived from
the image hash, a local record written before any submission, no resubmit
when a notebook may already exist, and verified output hashes. Jobs run in
parallel on Kaggle; this process only polls.

Usage: python kaggle_cpu_batch.py STATE.json OUT_DIR owner case=image.png ...
The Kaggle token comes from KAGGLE_API_TOKEN (KGAT_...).
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio/cloud-ai"))
from kaggle_provider import Kaggle, ProviderError


def main():
    state_path, out, owner = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    cases = dict(item.split("=", 1) for item in sys.argv[4:])
    provider = Kaggle(owner, os.environ["KAGGLE_API_TOKEN"], "unused-for-cpu", accelerator="cpu")
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    def save():
        state_path.write_text(json.dumps(state, indent=1))

    for case, image in cases.items():
        raw = Path(image).read_bytes()
        job = hashlib.sha256(raw).hexdigest()
        row = state.setdefault(case, {"job": job, "phase": "new"})
        if row["job"] != job:
            raise SystemExit(f"{case}: image changed since the recorded job")
    save()
    while True:
        active = 0
        for case, row in state.items():
            if case not in cases or row["phase"] in ("ready", "error"):
                continue
            active += 1
            job = row["job"]
            slug, dataset = f"forge-f01-job-{job[:32]}", f"forge-f01-input-{job[:32]}"
            try:
                if row["phase"] == "new":
                    suffix = Path(cases[case]).suffix.lower().lstrip(".").replace("jpeg", "jpg")
                    provider.create_dataset(dataset, Path(cases[case]).read_bytes(), suffix)
                    row["phase"] = "dataset"
                elif row["phase"] == "dataset":
                    if provider.dataset_ready(dataset):
                        if provider.notebook_exists(slug, dataset):
                            row["phase"] = "submitted"
                        else:
                            row["phase"] = "submitting"   # recorded before the write
                            save()
                            provider.submit(slug, dataset, job, job)
                            row["phase"] = "submitted"
                            row["submitted"] = time.time()
                elif row["phase"] == "submitting":
                    if provider.notebook_exists(slug, dataset):
                        row["phase"] = "submitted"
                elif row["phase"] == "submitted":
                    status = provider.status(slug)
                    row["status"] = status
                    if status == "complete":
                        model, report = provider.output(slug, job, job)
                        folder = out / case
                        folder.mkdir(parents=True, exist_ok=True)
                        (folder / "model.glb").write_bytes(model)
                        (folder / "report.json").write_text(json.dumps(report, indent=1))
                        row.update(phase="ready", seconds=report.get("inference_seconds"))
                    elif status in ("error", "cancelled"):
                        row["phase"] = "error"
            except ProviderError as exc:
                row["last_provider_error"] = exc.status
            except ValueError as exc:
                row.update(phase="error", reason=str(exc)[:200])
            save()
        print(json.dumps({case: (row["phase"], row.get("status")) for case, row in state.items()
                          if case in cases}), flush=True)
        if not active:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
