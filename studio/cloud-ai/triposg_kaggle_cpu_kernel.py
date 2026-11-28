"""F01 private Kaggle CPU session: BiRefNet soft mask -> TripoSG on CPU.

No GPU, TPU or accelerator quota is requested, so the session does not wait in
the GPU queue. The Forge server prepends FORGE_JOB_ID, FORGE_IMAGE_SHA256 and
FORGE_FILES (the exact forge_mask.py and triposg_cpu.py sources it ships).
Research evaluation only.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

assert pathlib.Path("/kaggle/working").is_dir(), "Use Kaggle"
base = pathlib.Path("/tmp/forge-f01-kaggle-cpu")
base.mkdir(exist_ok=True)
venv = base / "py310"
tripo_src = base / "TripoSG"
rev = "fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c"
tripo_rev = "2c1c516d22d58db486a058d98d31bb6177344e06"
sam2_rev = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
sam2_sha = "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
env = dict(os.environ, HF_HUB_DISABLE_XET="1", PYTHONNOUSERSITE="1", SAM2_BUILD_CUDA="0")
env.pop("PYTHONPATH", None)


def run(args, cwd=None, timeout=3600):
    print("RUN:", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True, timeout=timeout)


assert shutil.disk_usage(base).free > 14 * 2**30, "14 GiB free disk required"
# Live 2026-11-28: SAM2 refuses to import when the script's own directory
# contains the sam2 checkout, so Forge sources live in a separate folder.
forge = base / "forge"
forge.mkdir(exist_ok=True)
for name, source in FORGE_FILES.items():  # noqa: F821 - prepended by the server
    assert name in ("forge_mask.py", "triposg_cpu.py")
    compile(source, name, "exec")
    (forge / name).write_text(source)
run([sys.executable, "-m", "pip", "install", "uv==0.9.26"])
run([sys.executable, "-m", "uv", "python", "install", "3.10"])
if not (venv / "bin/python").exists():
    run([sys.executable, "-m", "uv", "venv", "--python", "3.10", "--seed", venv])
py = venv / "bin/python"
run([py, "-m", "pip", "install", "torch==2.5.1", "torchvision==0.20.1",
     "--index-url", "https://download.pytorch.org/whl/cpu"])
run([py, "-m", "pip", "install", "numpy==1.26.4", "scipy==1.11.4", "diffusers==0.32.2",
     "transformers==4.49.0", "huggingface-hub==0.28.1", "safetensors==0.5.3", "accelerate==1.4.0",
     "peft==0.14.0", "einops==0.8.1", "opencv-python-headless==4.10.0.84", "trimesh==4.5.3",
     "omegaconf==2.3.0", "scikit-image==0.24.0", "jaxtyping==0.2.38", "typeguard==2.13.3",
     "pymeshlab==2022.2.post4", "Pillow==11.1.0", "timm==1.0.15", "kornia==0.8.0",
     "hydra-core==1.3.2", "iopath==0.1.10", "setuptools", "wheel"])
if not tripo_src.exists():
    run(["git", "clone", "https://github.com/VAST-AI-Research/TripoSG.git", tripo_src])
run(["git", "-C", tripo_src, "checkout", "--detach", rev])
sam2_src = base / "sam2"
if not sam2_src.exists():
    run(["git", "clone", "https://github.com/facebookresearch/sam2.git", sam2_src])
run(["git", "-C", sam2_src, "checkout", "--detach", sam2_rev])
run([py, "-m", "pip", "install", "--no-build-isolation", "--no-deps", "-e", sam2_src])
checkpoint = base / "sam2.1_hiera_tiny.pt"
run(["curl", "-fsSL", "-o", checkpoint,
     "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt"])
assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == sam2_sha, "SAM2 checksum mismatch"
weights = base / "TripoSG-weights"
run([py, "-c", "from huggingface_hub import snapshot_download as s; s('VAST-AI/TripoSG', revision="
     + repr(tripo_rev) + ", allow_patterns=['*.json','*.safetensors','*.txt'], local_dir=" + repr(str(weights)) + ")"])

out = pathlib.Path("/kaggle/working/forge-f01-auto")
out.mkdir(exist_ok=False)
inputs = [p for p in pathlib.Path("/kaggle/input").rglob("*")
          if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
assert len(inputs) == 1, "Expected exactly one private image"
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()  # noqa: E731
assert sha(inputs[0]) == FORGE_IMAGE_SHA256, "Unexpected input bytes"  # noqa: F821
run([py, "-c", "from PIL import Image, ImageOps; Image.MAX_IMAGE_PIXELS=12_000_000; "
     "im=Image.open(" + repr(str(inputs[0])) + "); assert im.format in ('PNG','JPEG','WEBP'); "
     "ImageOps.exif_transpose(im).convert('RGB').save(" + repr(str(out / "source.png")) + ")"])
run([py, forge / "forge_mask.py", out / "source.png", base / "rgba.png", "--sam2-checkpoint", checkpoint],
    timeout=1800)
# bfloat16 autocast only helps with native AMX/AVX512-BF16; otherwise keep float32.
flags = pathlib.Path("/proc/cpuinfo").read_text()
bf16 = ["--bf16-transformer"] if (FORGE_BF16 and ("amx_bf16" in flags or "avx512_bf16" in flags)) else []  # noqa: F821
run([py, forge / "triposg_cpu.py", tripo_src, weights, base / "rgba.png", out / "model.glb", *bf16],
    timeout=4 * 3600)
local = json.loads((out / "model.report.json").read_text())
mask = json.loads((base / "rgba.mask.json").read_text())
report = dict(local, job_id=FORGE_JOB_ID, original_sha256=sha(inputs[0]),  # noqa: F821
              source_sha256=sha(out / "source.png"), model_revision=tripo_rev,
              background="BiRefNet+SAM2 bridge", mask=mask, visual_accepted=False, editor_accepted=False)
assert report["engine"] == "TripoSG" and report["actual_inference"] is True
(out / "report.json").write_text(json.dumps(report, indent=2))
(out / "model.report.json").unlink()
(out / "model.engine_input.png").unlink(missing_ok=True)
print("FORGE_AUTO_MODEL_READY", flush=True)
