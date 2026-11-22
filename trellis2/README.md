# TRELLIS.2 sunucu aracısı (deneysel)

Bu servis yerel GPU kullanmaz; sadece `microsoft/TRELLIS.2` Hugging Face Space API'sine bağlanır. Ücretsiz ZeroGPU kotası ve erişimi garanti değildir.

Gereksinimler: Python 3.11+, `pip install -r trellis2/requirements.txt`.

Ortam değişkenleri:
- `FORGE_ACCESS_TOKEN`: En az 16 karakterli gizli servis erişim anahtarı (zorunlu).
- `HF_TOKEN`: Kullanıcıya ait Hugging Face token'ı. ZeroGPU kota/kimlik doğrulaması gerekebilir; HTML içine gömülmez.
- `FORGE_ALLOWED_ORIGINS`: İzin verilen HTTPS Forge adresleri, virgülle ayrılmış. Yerel HTML için `null` origin varsayılan olarak açıktır; X-Forge-Token yine zorunludur.

Çalıştırma: `uvicorn trellis2.server:app --host 0.0.0.0 --port 8000`.

Sunucu: `POST /api/jobs` (multipart `image`), `GET /api/jobs/{id}`, `GET /api/jobs/{id}/glb`. İsteklerde `X-Forge-Token` gerekir. 90MB üstü GLB reddedilir.

**Uyarı:** Hugging Face Space API değişebilir; `image_to_3d` ve `extract_glb` canlı GPU üretiminde henüz doğrulanmadı. Sunucu kullanıma açılmadan canlı test edilmelidir. Render servisi başlatılmadı; ücretli kaynak açılmadı.
