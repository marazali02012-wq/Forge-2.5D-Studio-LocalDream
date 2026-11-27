FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl libgomp1 && rm -rf /var/lib/apt/lists/*
RUN git init /opt/triposr && git -C /opt/triposr fetch --depth 1 https://github.com/VAST-AI-Research/TripoSR.git 107cefdc244c39106fa830359024f6a2f1c78871 && git -C /opt/triposr checkout FETCH_HEAD
RUN case "$(uname -m)" in \
    aarch64) pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 ;; \
    x86_64) pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu ;; \
    *) exit 1 ;; \
    esac
RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.13.1 trimesh==4.4.9 networkx==3.4.2 shapely==2.0.6 scikit-image==0.24.0 transformers==4.46.3 einops==0.7.0 omegaconf==2.3.0 huggingface-hub==0.26.5 'rembg[cpu]==2.0.61' opencv-python-headless==4.10.0.84 numba==0.60.0 Pillow==10.4.0 onnxruntime==1.20.1 imageio-ffmpeg==0.5.1
ENV PYTHONPATH=/opt/triposr HF_HOME=/opt/cache FORGE_MODEL_PATH=/opt/model U2NET_HOME=/opt/u2 FORGE_BIND=0.0.0.0 PORT=7860 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 FORGE_CPU_THREADS=2
RUN mkdir -p /opt/model /opt/u2
RUN python -c "from huggingface_hub import hf_hub_download as get; [get('stabilityai/TripoSR', f, revision='5b521936b01fbe1890f6f9baed0254ab6351c04a',local_dir='/opt/model') for f in ('config.yaml','model.ckpt')];get('facebook/dino-vitb16','config.json',revision='f205d5d8e640a89a2b8ef0369670dfc37cc07fc2')"
RUN mkdir -p /opt/cache/hub/models--facebook--dino-vitb16/refs && printf %s f205d5d8e640a89a2b8ef0369670dfc37cc07fc2 > /opt/cache/hub/models--facebook--dino-vitb16/refs/main && curl -fsSL --retry 2 https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx -o /opt/u2/u2netp.onnx && echo '8e83ca70e441ab06c318d82300c84806  /opt/u2/u2netp.onnx' | md5sum -c -
ENV HF_HUB_OFFLINE=1 NUMBA_CACHE_DIR=/tmp/numba
COPY torchmcubes.py /opt/triposr/torchmcubes.py
WORKDIR /app
COPY *.py ./
RUN useradd -m -u 1000 forge && chown -R forge /opt/cache
USER forge
CMD ["python","private_api.py"]
