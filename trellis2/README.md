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

**Dengeli kalite (varsayılan):** TRELLIS çözünürlük `1024`, en fazla `200000` yüz, `2048` px kaplama. Bunlar canlı GPU üretiminde henüz doğrulanmadı. Ücretsiz GPU kotası yetersizse sunucuda `FORGE_TRELLIS_RESOLUTION=512`, `FORGE_TRELLIS_FACES=100000`, `FORGE_TRELLIS_TEXTURE=1024` seçilebilir. 1536 daha ağırdır; telefon hedefi için varsayılan değildir.

## Kullanım (sunucusuz)

Yeni Forge HTML'de **3D Model** bölümüne gir, **TRELLIS.2 kaynak resmi** alanından PNG/JPG/WEBP seç ve **TRELLIS.2 ile gerçek 3D üret** düğmesine bas. Varsayılan yol doğrudan resmî `microsoft/TRELLIS.2` Gradio API'sidir; özel HTTPS proxy adresi/anahtarı **gerektirmez**. Gradio JS istemcisi jsDelivr üzerinden yüklenir, **internet şarttır**. Ücretsiz ZeroGPU kotası, Hugging Face oturumu veya tarayıcı CORS politikası yüzünden engellenebilir. Gerçek üretim testi olmadan başarı garantisi yoktur.

**Özel sunucu** alanına URL girilirse önceki güvenli proxy yolu kullanılmaya devam edilir; alan boşsa doğrudan yol seçilir. Önceki V14.1 GPU/CPU/animasyon ve eski GLB import davranışı korunmuştur.

## Gerçek bağlantı testi (GPU kullanmaz)

`trellis2/test_live_connection.py`, GitHub Actions üzerinde Forge HTML'nin kullandığı **gerçek jsDelivr Gradio modülünü** indirmeyi ve `microsoft/TRELLIS.2` API'sine bağlanmayı dener. `test-sonuclari/trellis2/gercek_api_baglanti.json` dosyasına sonucu yazar. Dış hizmet erişilemezse ana regresyon testini düşürmez, fakat test sonucu hatadır. **Bu test hiçbir 3D üretimi başlatmaz; resmi Space'te GPU testinde Generate -> Error, Extract -> Empty value görüldü.** API bağlantısı başarılı olsa da 3D üretim hazır demek değildir.
