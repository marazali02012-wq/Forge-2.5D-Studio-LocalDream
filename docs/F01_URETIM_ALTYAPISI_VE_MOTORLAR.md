# F01 — Ücretsiz üretim altyapısı ve 3D motor karşılaştırması

Tarih: 2026-11-28. Kaynaklar birincil kaynaktır (model kartı, lisans metni, resmî README veya
belge). "Gerçek test" sütunu yalnız bu depoda kanıtı olan çalıştırmaları gösterir; araştırma
bulgusu test sonucu sayılmaz.

## 1. Motorlar

| Motor | Lisans (doğrulanan) | Donanım (resmî) | Forge'da gerçek test | Durum |
| --- | --- | --- | --- | --- |
| TripoSR | MIT ([model kartı](https://huggingface.co/stabilityai/TripoSR)) | ~6 GB VRAM; CPU yolu Forge'da mevcut | Evet: HARD10 CPU (CI 46104582666) | Korunuyor. İnce yapıda zayıf: tavuskuşu kuyruğu ve kafe kişisi girdi maskesinde kayboldu. |
| TripoSG | MIT, kod ve ağırlık ([model kartı](https://huggingface.co/VAST-AI/TripoSG), revizyon `2c1c516d`) | Resmî yol CUDA (DiffDMC); Forge CPU yolu ekledi | Evet: Kaggle T4 (savaşçı, 183,8 sn) ve bu oturumda CPU ile Kaggle CPU | **Seçilen motor.** |
| TRELLIS.2 | MIT ([model kartı](https://huggingface.co/microsoft/TRELLIS.2-4B)) | En az 24 GB VRAM'li NVIDIA GPU, yalnız Linux, A100/H100'de doğrulanmış ([README](https://github.com/microsoft/TRELLIS.2)) | Hayır | Ücretsiz T4 (16 GB) ve CPU ile çalıştırılamaz. Yalnız ZeroGPU Space'te çalışıyor; anonim kota 0 sn olduğu için denenemedi. |
| Hunyuan3D 2 / 2.1 / 2mini | Tencent Hunyuan Community License: AB, Birleşik Krallık ve Güney Kore'de geçersiz; aylık 1 milyonun üzerinde aktif kullanıcı için ayrı izin gerekir ([lisans](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/LICENSE)) | Yalnız şekil için 6 GB, şekil ve doku için 16 GB VRAM ([README](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)) | Hayır | Bölge kısıtı nedeniyle Forge'un genel dağıtımı için riskli. Teknik olarak T4'e sığar. |
| Stable Fast 3D | Stability AI Community License; HF'de kapılı (gated: auto) ([model kartı](https://huggingface.co/stabilityai/stable-fast-3d)) | ~6 GB VRAM; resmî CPU arka ucu var ([README](https://github.com/Stability-AI/stable-fast-3d)) | Hayır. Bu dalın ana listesinde sonuç kaydı yok; eski `forge-r58`/`forge-r59` dalları incelenmedi. | Lisans kabulü ve HF anahtarı gerekiyor. |

Arka plan ve maske:

| Model | Lisans | Kullanım |
| --- | --- | --- |
| BiRefNet (`ZhengPeng7/BiRefNet`, `e2bf8e44`) | MIT | Forge yumuşak alfa maskesi (`forge_mask.py`) |
| SAM2.1 hiera tiny (checkpoint SHA-256 `7402e0d8…`) | Apache-2.0 | Konuyu bölen kapatan nesneyi geri bağlama (kafe masası) |
| RMBG-1.4 | Ticari olmayan kullanım | Yalnız TripoSG'nin resmî ön işleminde, karşılaştırma amacıyla. Forge'un yeni yollarında kullanılmıyor. |

## 2. Ücretsiz altyapı

| Seçenek | Gerçek durum (2026-11-28) | Forge entegrasyonu |
| --- | --- | --- |
| Kaggle T4 ×2 | Haftalık 30 sa kota. Özel iş ~2 sa kuyrukta bekledi, sonra ~6 dk GPU ile tamamlandı. Çıktı önceki elle üretimle bit düzeyinde aynı (GLB SHA-256 `bca8b2a0…`). | Var (`FORGE_KAGGLE_ACCELERATOR=gpu`). |
| **Kaggle CPU oturumu** | Kuyruk yok, hemen RUNNING. GPU kotası değişmedi (4.561,6 sn önce ve sonra). | **Yeni** (`FORGE_KAGGLE_ACCELERATOR=cpu`). |
| Sunucu CPU'su | 4 vCPU'da float32 TripoSG (ölçüm bölüm 3'te) | **Yeni** (`FORGE_LOCAL_TRIPOSG=1`). |
| Hugging Face ZeroGPU | Kota: anonim 2 dk/gün, ücretsiz hesap 5 dk/gün, PRO 40 dk/gün ([belge](https://huggingface.co/docs/hub/spaces-zerogpu)). Bu bulut ortamının IP'sinde anonim kota 0 sn kaldı. | Hesap anahtarı olmadan denenemiyor. Görseli üçüncü tarafa gönderdiği için yalnız herkese açık test görselleri için uygun. |
| Google Colab | Otomasyon API'si yok; ücretsiz GPU garanti değil, en fazla 12 sa ([SSS](https://research.google.com/colaboratory/faq.html)). | Elle çalıştırılan R2 not defteri mevcut (kullanıcı T4'te doğruladı). Bu bulut oturumundan Google oturumu açılamıyor. |

## 3. Ölçümler

| Vaka | Altyapı | Süre | Ham çıktı | Mobil kapı | Kanıt |
| --- | --- | --- | --- | --- | --- |
| Savaşçı (özel) | Kaggle T4, otomatik iş | 183,8 sn (model yükleme dahil) + ~2 sa kuyruk | 1.905.082 yüz, GLB `bca8b2a0…` | Geçti: 59.050 üçgen, 27/27 bileşen, en büyük sapma %0,16450 | Yalnız sayısal (özel) |
| Bisiklet (CC0) | Bu oturumun sunucusu, 4 vCPU, float32 | 55 dk: difüzyon 27,6, yoğun ızgara 19,1, 512 bandı 8,3 | 730.036 yüz, 118 bileşen, kapalı, Khronos 0/0 | Geçti: 58.494 üçgen, 118/118, en büyük sapma %0,146 | [görüntü](../verification/f01/evidence/hard10-bicycle-triposg-cpu.jpg), [json](../verification/f01/evidence/hard10-bicycle-triposg-cpu.json) |

Hassasiyet A/B (aynı gizli temsil, 32³/64³ duman ızgarası): bf16 çözücü 2,6 kat hızlı, ama
37→34 bileşen ve en büyük sapma %15,2 verdi; reddedildi. 1024³ çıkarım (derinlik 10)
float32 ızgaralarla 15 GB RAM'e sığmıyor; 24 GB üzeri RAM veya GPU gerekiyor.

Kaggle CPU oturumları kuyruksuz başlıyor ve kurulumu yaklaşık 4 dakikada bitiriyor. Üretim
süresi bu sunucudan uzun; kesin süreler tamamlanan işlerle eklenecek.
