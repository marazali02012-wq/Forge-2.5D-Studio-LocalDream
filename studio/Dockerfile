FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 LIBGL_ALWAYS_SOFTWARE=1 HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 FORGE_REQUIRE_AUTH=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git libegl1 libegl-dev libgl1 libgl-dev libgl1-mesa-dri libegl-mesa0 blender && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir 'numpy<2' omegaconf==2.3.0 pillow==10.4.0 einops==0.7.0 transformers==4.35.0 trimesh==4.5.3 'huggingface-hub<1' imageio rembg onnxruntime scikit-image==0.24.0 xatlas==0.0.9 moderngl==5.10.0 fastapi uvicorn
RUN git clone https://github.com/VAST-AI-Research/TripoSR.git upstream-triposr && git -C upstream-triposr checkout --detach 107cefdc244c39106fa830359024f6a2f1c78871
COPY torchmcubes.py /app/upstream-triposr/torchmcubes.py
COPY index.html engine.py quality.py color_qa.py atlas_qa.py parts.py server.py blender_tools.py /app/
RUN useradd -m -u 1000 forge && chown -R forge:forge /app
USER forge
EXPOSE 7860
CMD ["uvicorn","server:app","--host","0.0.0.0","--port","7860","--workers","1"]
