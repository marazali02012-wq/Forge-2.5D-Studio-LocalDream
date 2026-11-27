---
title: Forge 2.5D CPU
emoji: 🧊
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
---
Dedicated TripoSR CPU preview. Use CPU Basic. Configure a private FORGE_API_TOKEN of at least 32 characters and FORGE_ALLOWED_ORIGINS as the exact HTTPS editor origin. POST /v1/generate or /v1/generate-rig with the image bytes and a Bearer key. /health reports availability. No persistent image storage. Rebuild with the Dockerfile and source files produced by prepare_space.py. A sleeping or restarted Space can interrupt a generation.
