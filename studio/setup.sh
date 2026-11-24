#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Ubuntu 24.04 / Python 3.11 environment. Run locally, not on a phone.
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends libegl1 libegl-dev libgl1 libgl-dev libgl1-mesa-dri libegl-mesa0 git blender
python3.11 -m venv .venv
source .venv/bin/activate
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install 'numpy<2' omegaconf==2.3.0 pillow==10.4.0 einops==0.7.0 transformers==4.35.0 trimesh==4.5.3 'huggingface-hub<1' imageio rembg onnxruntime scikit-image==0.24.0 xatlas==0.0.9 moderngl==5.10.0 fastapi uvicorn
if [ ! -d upstream-triposr ]; then git clone https://github.com/VAST-AI-Research/TripoSR.git upstream-triposr; fi
git -C upstream-triposr checkout --detach 107cefdc244c39106fa830359024f6a2f1c78871
cat > upstream-triposr/torchmcubes.py <<'PY'
import torch,numpy as np
from skimage.measure import marching_cubes as mc
def marching_cubes(volume,level):
    v,f,_,_=mc(volume.detach().cpu().numpy(),level=level,gradient_direction='ascent',allow_degenerate=False)
    return torch.from_numpy(v[:,::-1].copy()).float(),torch.from_numpy(f.copy().astype(np.int64))
PY
python -c "import ctypes,moderngl; ctypes.CDLL('libEGL.so'); c=moderngl.create_standalone_context(backend='egl'); print(c.info['GL_RENDERER']); c.release()"
echo 'Run: source .venv/bin/activate && uvicorn server:app --host 127.0.0.1 --port 8000'
