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
5. Resmî Hugging Face Space arayüzü hesap açılmadan görüntülenebildi; API şemasında `/preprocess_image`, `/image_to_3d`, `/extract_glb` yer alıyor.
6. **Gerçek CDN + API testi:** Playwright'ta gerçek `@gradio/client@2.7.0` jsDelivr modülü `file://` HTML'den yüklendi; `Client.connect("microsoft/TRELLIS.2")` ve `view_api()` çalıştı; 4 gerekli uç nokta doğrulandı. Bu aşamada GPU kullanılmadı.
7. **Canlı resmî arayüz testi başarısız:** TRELLIS.2 içindeki hazır *taç* örneğiyle `1024` çözünürlükte Generate denendi; önizleme yalnızca `Error` gösterdi. Extract GLB sonrası `Empty value` çıktı; indirilebilir GLB üretilemedi. Neden ayrıntılı hata verilmediği için kesinleştirilemedi.

**Otomatik test kanıtı:** [GitHub Actions — TRELLIS2 testleri](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/44973690777).

## Yapılmayan veya doğrulanamayanlar

- Gerçek bir zırhlı savaşçı görseli gönderilip TRELLIS.2 üzerinde 3B üretim yapılmadı.
- Gerçek GPU'nun ürettiği GLB ve gerçek zırhlı savaşçıya ait ön/yan/arka görüntüler bulunmuyor. Test artefaktları **sentetiktir**.
- Anonim kullanımda en az bir gerçek üretim denemesi **başarısız** oldu. Bunun kesin nedeni (GPU sırası, kota, sunucu hatası veya başka neden) bilinmiyor. API bağlantısı başarılı olsa bile üretim sağlıklı değil.
- Gerçek Realme C55 / Mali GPU testi ve performans ölçümü yapılmadı.
- Render üzerinde HTTPS sunucu servisi kurulmadı; gizli `FORGE_ACCESS_TOKEN` / `HF_TOKEN` girilmedi.
- Resmî Space üzerinden yapılan canlı Generate/Extract denemesinde GLB oluşturulamadığı ve uçtan uca Forge import testi geçmediği için entegrasyon **tamamlandı** sayılamaz.

## Kalan kritik yol

1. Mevcut **doğrudan API bağlantısını** kullan; ayrıca HTTPS proxy kurmak artık zorunlu değil. Resmî Space üretimi yine çalışmıyorsa yalnızca istemciyi değiştirerek çözülmez.
2. Microsoft/Hugging Face servisinin gerçekten GLB üretebildiği erişim koşullarını doğrula. Gerekirse kullanıcı tarafından seçilen, erişilebilen NVIDIA GPU ortamı gerekir; ücretli GPU kendiliğinden açılmaz.
3. Gerçek, orijinal kaplamalı GLB'yi Forge'a aç, ön/yan/arka görsellerle kaynak görsele benzerliği incele.
4. Gerçek Realme C55 üzerinde WebGL2 ve CPU geri dönüşünü test et.
5. 26 kemikli rigging'i ilk aşamada ekleme ve orijinal mesh'i değiştirme.

## Son düzeltme

- Eski proxy adresinin tarayıcı belleğinden kendiliğinden geri gelmesi kaldırıldı.
- **API bağlantısını kontrol et** işlemi eklendi; yalnızca Gradio CDN + resmî uç noktaları denetler, GPU çalıştırmaz.
- Sahte yanıtlı tarayıcı testi ve **gerçek internet/CDN/API testi** ayrı tutuldu.
- Başarısız gerçek Generate denemesi resmî arayüzde kaydedildi. Çalışmayan TRELLIS servisini “tamamlandı” göstermek yasaktır.

**Kural:** Üçüncü taraf API erişim durumunu, gerçek GPU üretimini ve statik GLB okuyucu testlerini birbirine karıştırma.
