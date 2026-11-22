# Forge 2.5D Studio — TRELLIS.2 GPT-6 doğrulama raporu

**Tarih:** 22 Kasım 2026  
**Kaynak:** `gelistirme/webgl2-v14` (`e47324e0c81c8e1740c1f34bd8591beb92684345`)  
**Geliştirme:** `gelistirme/trellis2-gpt6`  
**Koruma:** `main` ve V14.1'in kaynak HTML'si değiştirilmedi.

## Doğrulanmış sistemler

1. V14.1'den türetilen `Forge_25D_V14_1_TRELLIS2_GPT6.html` HTML'si, mevcut CPU ve WebGL2 motorlarının yanına ayrı glTF 2.0 PBR GLB görüntüleyicisi ekler.
2. Sentetik test GLB'siyle iskeletsiz/çoklu mesh/sahne hiyerarşisi, UV, malzeme, PBR, şeffaflık, ön-yan-arka ekran görüntüsü ve orijinal GLB'nin aynı byte'larla yeniden indirilmesi Playwright/SwiftShader üzerinde geçti.
3. PNG dokulu ve `EXT_texture_webp` kullanan WebP dokulu test GLB'leri Chrome tabanlı otomatik testte açıldı.
4. Sunucu tarafında kimlik doğrulama, bozuk görsel reddi, sahtelenmiş başarılı istek ve GPU yokken doğru hata durumuna geçiş testleri geçti. Testlerde gerçekten Hugging Face GPU kullanılmadı.
5. Resmî Hugging Face Space arayüzü, ZeroGPU üzerinde çalışır durumda ve hesap açılmadan görüntülenebilir. API şemasında `/preprocess_image`, `/image_to_3d` ve `/extract_glb` yer alıyor.

**Otomatik test kanıtı:** [GitHub Actions — TRELLIS2 testleri](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/44970463345).

## Yapılmayan veya doğrulanamayanlar

- Gerçek bir zırhlı savaşçı görseli gönderilip TRELLIS.2 üzerinde 3B üretim yapılmadı.
- Gerçek GPU'nun ürettiği GLB ve gerçek zırhlı savaşçıya ait ön/yan/arka görüntüler bulunmuyor. Test artefaktları **sentetiktir**.
- Anonim kullanımın GPU kotası veya API üzerinden üretim yapabilmesi doğrulanmadı; Space sayfasının açık olması başarılı üretim anlamına gelmez.
- Gerçek Realme C55 / Mali GPU testi ve performans ölçümü yapılmadı.
- Render üzerinde HTTPS sunucu servisi kurulmadı; gizli `FORGE_ACCESS_TOKEN` / `HF_TOKEN` girilmedi.
- Canlı GPU üretim ve uçtan uca Forge import testi geçmediği için üretim entegrasyonu **tamamlandı** sayılamaz.

## Kalan kritik yol

1. Açıkça seçilen bir ücretsiz HTTPS proxy ortamına sunucuyu kur, gizli anahtarları sunucuya yerleştir; ücretli NVIDIA GPU açma.
2. Hugging Face erişimi ve ücretsiz hesap kotası ile zırhlı savaşçı için **gerçek** `image_to_3d` + `extract_glb` işlemlerini tamamla; hata/kotayı kaydet.
3. Gerçek, orijinal kaplamalı GLB'yi Forge'a aç, ön/yan/arka görsellerle kaynak görsele benzerliği incele.
4. Gerçek Realme C55 üzerinde WebGL2 ve CPU geri dönüşünü test et.
5. 26 kemikli rigging'i ilk aşamada ekleme ve orijinal mesh'i değiştirme.

**Kural:** Üçüncü taraf demo/API erişim durumunu, gerçek GPU üretimini ve statik GLB okuyucu testlerini birbirine karıştırma.
