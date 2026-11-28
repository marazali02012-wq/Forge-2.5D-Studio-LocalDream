# Forge Studio — Ana geliştirme listesi ve sıralı kabul şartnamesi

Kullanıcı talimatı, 28 Kasım 2026: Geliştirme her zaman bu liste üzerinden yürütülür. Bir aşama tamamen bitmeden sonraki aşamaya başlanmaz. Referans: Tripo Studio'nun işlevleri, genel amaçlı ve şablondan bağımsız gerçek 3D üretim. Bu belge mevcut geliştirme dalındaki birincil sıra kaynağıdır; önceki teknik kayıtlar kanıt ve ayrıntı olarak korunur.

## Kesin hedef ve kurallar

- Herhangi bir yeni görselden gerçek 3D geometri; insan, hayvan, eşya, mekanik nesne, çok nesneli sahne ve farklı pozlar sadece test kategorileridir, hazır üretim kalıpları değildir.
- Tek görüntüde görünmeyen yüzeyler tahmindir; kesin kopya garantisi verilmez. Ayrılan her parça kendi gerçek 3D hacmine sahip olmalıdır. 2D maske, düz kart, rastgele üçgen bölme veya hazır model yerleştirme yeterli değildir.
- Statik nesnelere zorunlu iskelet uygulanmaz. Rig/animasyon istenirse nesnenin anatomisine veya mekanizmasına uyarlanır; 26 kemik sistemi sadece uygun insansı modeller için korunur.
- Mevcut TripoSR, editör ve doğrulanmış R70.34/R70.35 çıktıları korunur. Yeni yöntemler deneysel ve geri alınabilir olmalıdır.
- Önce mevcut kod ve kanıtı oku; önceki çalışma tekrar edilmez. X10, kök neden, RED TEAM, FACT CHECK, gerektiğinde ALT3 ve gerçek regresyon testi uygula.
- /GÖRSEL-DENETİM: her önemli değişiklikte gerçek çıktı görüntüleri, ön/arka/yan/çapraz ve gerekiyorsa üst/alt; hareketlerde tam döngü veya yeterli kare örnekleri. Görsel kusuru varsa yalnız sayısal başarıyla aşamayı kapatma.
- Sıradaki ilk tamamlanmamış aşama dışında geliştirme başlatma. Aşamanın kendi bağımlılıklarını o aşamada çöz; kapsamı genişletme. Engellenirse aynı aşamada alternatif dene, gerçek engeli kaydet. Kullanıcı açıkça sıra/kapsam değişikliği onaylamadan atlama, bitmiş gösterme veya sonraki aşamaya geçme.
- Araştırma sonucunu uygulama sonucu sayma. Açık kaynak adayının lisansı, ağırlık erişimi, API ve gerçek testi doğrulanmadan entegrasyon tamamlanmış sayılmaz. Ticari Tripo'nun yayımlanmamış motorunun birebir kopyası vaat edilmez.
- Arena Forge Pro ve Kırık Mühür'e dokunma. Onaysız ücretli servis açma. Canlı servis anahtarlarını repoya/HTML'ye yazma.
- Her aşama kapanışında gerçek işlevsel test, regresyon, görsel kanıt, uygun GLB validator raporu ve commit bağlantısı gerekir. Gerekli kalite veya test sonucu yoksa durum AÇIK/ENGELLİ kalır.

## Ana sıra ve başlangıç durumu

| ID | Öncelik | Durum |
| --- | --- | --- |
| F01 | Genel amaçlı gerçek 3D üretim | AKTİF — kısmen mevcut |
| F02 | Akıllı nesne ve semantik parça ayrıştırma | BEKLİYOR |
| F03 | Her parçanın bağımsız 3D hacmi ve sahne bütünlüğü | BEKLİYOR |
| F04 | Geometri onarımı ve parça düzenleme | BEKLİYOR |
| F05 | UV, doku ve PBR materyal | BEKLİYOR |
| F06 | Genel, anatomiye uyarlanabilir iskelet | BEKLİYOR |
| F07 | Serbest animasyon ve hareket kalitesi | BEKLİYOR |
| F08 | Genel editör, sahne, kütüphane ve dışa aktarma | BEKLİYOR |
| F09 | Canlı AI, uçtan uca doğrulama ve fiziksel Android kabulü | BEKLİYOR |

### F01 — Genel amaçlı gerçek 3D üretim
- Mevcut TripoSR statik yolunu ve giriş/çıktı sınırlamalarını incele; zorunlu insan anatomisi, sınıf, poz veya rig bağımlılığını kaldır.
- Tek görselden geometri, arka plan temizleme, çizim/fotoğraf girişi, farklı nesne/pozlar, yüksek/düşük detay seçenekleri, içe aktarma, toplu üretim. Çok açılı ve yazıdan üretim için uygun gerçek motorları değerlendir ve kabul kapsamındaki işlevleri uygula; sahte üretim kullanma.
- Adaylar: TripoSR, TripoSG, TripoSF, Stable Fast 3D, TRELLIS, Hunyuan3D; lisans ve gerçek yetenek doğrulanacak.
- Kapanış: daha önce görülmemiş çeşitli görüntüler (örn. oturan insan, hayvan, eşya, mekanik nesne, çok nesneli sahne) gerçek statik GLB üretir; örnekler kalıp olmaz. Geometri, siluet, hacim, ön/arka/yan görseller, yeniden içe aktarma, geçerli GLB ve üretim süresi ölçülür. Çok nesneli ayrıştırma F02/F03 kabulüdür, F01'de zorunlu değildir. Kapsamda desteklenemeyen bir giriş tipi varsa açık engel olarak kaydedilir, kullanıcı karar vermeden kapanmaz.
- Başlangıç kanıtı: R70.34 on insansı örnek geçti; genel nesne/poz kapsaması henüz doğrulanmadı. İlk iş F01.

### F02 — Akıllı ayrıştırma
- Görüntüdeki nesneleri ve 3D modeldeki anlamlı parçaları otomatik tanı; kullanıcı seçimi, fırça/maskeyle sınır düzeltme, ayrıştırma detay seviyesi ve parça etiketleri.
- Adaylar: GeoSAM2, SAM 3D Objects, genel görüntü segmentasyonu + TripoSR, PartCrafter. 2D maske yalnız ara çıktı.
- Kapanış: çeşitli yeni sahne ve tek nesnelerde anlamlı parça sınırları gerçek 3D yüzey üzerinde seçilebilir; kayıp/yanlış birleşim, örtüşme ve kullanıcı düzeltme testi; görüntüler ve ölçümler. F03'ün hacim tamamlama kabulüyle karıştırılmaz.

### F03 — Bağımsız gerçek 3D parçalar
- HoloPart, PartCrafter, SAM 3D Objects ve uygun alternatifleri değerlendir. Eksik/örtülü yüzeyleri tamamla, doku/ölçek/konum ve sahne ilişkilerini koru.
- Seçilen parçayı ayrı GLB üret/indir; sahne GLB'si bağımsız node/mesh yapısı içersin; seçili parçayı yeniden üretme imkânı.
- Kapanış: örn. masada çay içen insan sahnesindeki insan, masa, sandalye ve bardak ayrı hacimli modeller olarak döner, taşınır ve geri birleştirilir; başka yeni örneklerle de test edilir. Tek görselden tahmin edilen görünmeyen alanlar ayrıca belirtilir. Geçerli GLB, gerçek parça hacmi ve görsel denetim.

### F04 — Geometri düzenleme
- Yüzey yumuşatma, bozuk/dejenere üçgen temizliği, delik onarımı, poligon azaltma, simetri, tel kafes, üçgen/dörtgen topoloji, seçili bölge şekillendirme, parça ekle/sil/gizle/birleştir/taşı/döndür/ölçekle, bölgesel yeniden üretme.
- Mevcut Manifold, Meshoptimizer, SculptGL, PMP ve MC33'ü yeniden yazmadan değerlendir; dörtgen topoloji ve AI onarım için yeni adayları test et.
- Kapanış: işlem öncesi/sonrası topoloji, sınır, hacim, doku kaybı, siluet ve GLB doğrulaması; editör işlevleri gerçek modellerde çalışır.

### F05 — UV ve materyal
- Gerçek UV atlası, dikişler, UV görüntüleme, görselden doku, elle boya, parça materyali, metalik/pürüzlülük/normal haritası, doku leke onarımı, yüksek detay, ışık ayrıştırma, yazıyla/bölgesel AI doku üretimi.
- Aday: xatlas ve mevcut atlas kodu, lisansı doğrulanmış doku motorları.
- Kapanış: farklı parçalarda ve arka/yan yüzeylerde UV ve PBR haritaları gerçek GLB'ye gömülür, dikiş/lekeler görsel ve sayısal olarak kontrol edilir; arka doku tahmini açıkça belirtilir.

### F06 — Uyarlanabilir iskelet
- İnsan (farklı pozlar), hayvan, çok bacaklı, kanatlı, balık/yılan ve mekanik hareket gibi farklı yapıların uygun rig'i; parmak ve aksesuarlar; elle kemik ve ağırlık düzenleme. İskeletsiz statik yol korunur.
- Adaylar: UniRig, SkinTokens, AniGen, mevcut 26 kemik sistemi; isim/lisans/gerçek model desteği doğrulanır.
- Kapanış: farklı anatomilerde gerçek eklem hiyerarşisi, geçerli skin ağırlıkları, düzenleme ve GLB round-trip; her modele aynı kemik sayısı dayatılmaz. Görsel deformasyon testi.

### F07 — Serbest animasyon
- Uygun rig ile doğal yürüyüş, bekleme, saldırı, hasar, ölüm, oturma/nesne tutma, mekanik hareket; animasyon aktarımı/kütüphane, hız, birleştirme, oynat/duraklat ve istenen özgün hareket üretimi.
- R70.35 iki kemikli IK, ayak teması, parmak, aksesuar ve Mesh2Motion korunur; gerekli gerçek hareket motoru değerlendirilir.
- Kapanış: farklı anatomiler ve pozlarda gerçek GLB animasyonları; tam döngü görsel denetimi, temas, deformasyon, hareket genliği, kemik uzunluğu, nesne etkileşimi; hareketi küçülterek test geçme yok.

### F08 — Editör ve sahne
- 360° kamera, dokunmatik kontrol, ızgara, nesne/katman paneli, parça düzenleme, çoklu model sahne, kütüphane, çoğaltma, geri/ileri, otomatik kayıt, sürüm geçmişi, bağlantılı üretim akışı ve uygun otomatik düzenleme.
- GLB/OBJ/STL, uygun FBX/USDZ/3MF dışa aktarma; bağımsız parçalar ve tüm sahne. Üç mobil yatay boyutta arayüz taşma ve dokunma testi.
- Kapanış: gerçek çok nesneli sahne düzenleme ve kaydet/aç/dışa aktar/geri al işlemleri; dosyaların bağımsız uygulamada açılması, ekran görüntüleri ve işlevsel test.

### F09 — Canlı AI ve gerçek cihaz kabulü
- Güvenli canlı HTTPS AI bağlantısı, anahtar güvenliği, yükleme sınırı, hata/yoğunluk testleri, gerçek yeni kullanıcı görselinden model; kalıcı sunucu doğrulaması. Geçici CI/Colab testini üretim sunucusu diye gösterme.
- Realme C55 fiziksel Android testi: FPS, bellek, CPU/GPU, ısınma, dokunma, büyük GLB, animasyon, indirme. Emülasyon fiziksel test değildir.
- Kapanış: bütün zincir canlı ve gerçek kullanıcı görseliyle çalışır; güncel kaynak, HTML, tercihen 30 MB altı ZIP (gerekirse bölünmüş), statik/animasyonlu/parçalı GLB, görsel kanıt, validator ve performans raporu teslim edilir. Tüm kritik şartlar kanıtlanmadan üretime hazır etiketi yok.

## İlerleme kayıt biçimi (her oturum sonunda güncelle)

- Aktif aşama: F01.
- Son doğrulanmış önceki çalışma: R70.35 iki model IK testi (46084286474, cc087f9); bu F07'nin tamamlandığı anlamına gelmez.
- Önceki kapsam kaydı: verification/FORGE_GENEL_3D_KAPSAM.md.
- Her kayıt: tarih / aşama ID / yapılan kod değişikliği / test komutu ve sonucu / görsel kanıt bağlantısı / commit / kalan eksik / durum.
- Aşama kapanışı: tüm kabul ölçütleri için kanıt bağlantısı + regresyon sonucu + görsel inceleme; sonra ve sadece sonra sonraki aşamayı AKTİF yap.
- Yeni talep listeyle çelişmiyorsa ilgili aşamanın alt maddesine eklenir; sırayı değiştirme kullanıcı açıkça isterse yapılır.
- Başlangıç kaydı: 2026-11-28 — yalnız plan ve kabul ölçütleri kaydedildi; yeni motor kurulmadı, yeni kod testi yapılmadı. F01 açık.

- 2026-11-28 — F01: genel statik üretim yolu rig gerektirmiyor; önceki QA insansı ağırlıklı. Görsel ön plan kırpma, boş/çok küçük alfa alanı ve EXIF yönü düzeltildi ([a0a1954](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/a0a19542738ab9509390f730309234d05d8913fa)). Yerel izole Pillow kontrolü: 5/5 (kenar pikseli, düşük alfa gürültüsü, boş/düşük alfa ve tek piksel); gerçek model çıkarımı değildir. Farklı nesneler ve oturan insanlı özgün çizim sahnesi için gerçek TripoSR QA ve dört açılı görsel çıktılar eklendi ([83aab67](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/83aab67ff39207644cdc8524e7ba3125b52b96af), [c088f4b](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/c088f4b6776c11ae0a00e4538be61b8a65c21665)). [F01 gerçek üretim testi 46087227281](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46087227281) ve [eski regresyon 46087186543](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46087186543) başlatıldı; sonuçlar ve yeni görsel denetim henüz doğrulanmadı. API'deki 128 sabit çözünürlük, tarayıcı içe aktarım bütçesi, çok açılı ve yazıdan üretim açık. F01 AKTİF; F02 ve sonrası bekliyor.

- 2026-11-28 — F01: [genel gerçek üretim 46087227281](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46087227281) tamamlandı: 7/7 statik GLB ve bağımsız Khronos doğrulaması sıfır hata/uyarı; 27,9–35,2 sn. [Gerçek GLB ve dört açılı görüntü arşivi](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46087227281/artifacts/15240210747). Görsel denetim: sandalye/çaydanlık genel formu iyi; at ince gövde ve bacak, ev eğim/arka görünüm, oturan insanlı sahne bardak/yüz ve detay kusurları; sayısal başarı görsel kabul değildir. 128/192 sandalye 20.332/46.740 üçgen, ikisi de editör bütçesinde. Alanı <=1e-12 olan üçgenler sandalye 1, robot 2, yüksek detaylı sandalye 1; validator uyarısız olsa da ayrıca izlenmeli. [Eski regresyon 46087186543](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46087186543): üç çıkarım başarılı, VTK LOD adayları topoloji/kapalı yüzey kapısından geçmedi, orijinal korunmalı; regresyon bütünü başarısız, sınırlar gevşetilmedi. [9bfb005](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/9bfb005f9ed9e5d12bb5fb39d2fa202f744d130f): statik API'de 128 varsayılan, açıkça seçilen 192, geçersiz çözünürlük ve boş alfa reddi; rig ve editör limitleri korundu. [410be8f](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/410be8fac72268cf8f9b71a6147ef2ff741fd289): gerçek API iki çözünürlük testi ve validator eklendi; [yeni F01 CI 46088093473](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46088093473) ve [eski tarayıcı zinciri 46088075012](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46088075012) sürüyor, henüz sonuç yok. Kalite seçiminin arayüze bağlanması, görsel kalite, yeni bağımsız fotoğraf/mekanik nesne, çok açılı ve yazıdan üretim, toplu üretim açık. Önceki SF3D araştırması tam PBR motoru değil; TRELLIS.2 canlı çıkarımı önceki raporda başarısız; Hunyuan köprüsü çıkarım doğrulanmamış. F01 AKTİF; F02 ve sonraki aşamalar başlatılmadı.

- 2026-11-28 — F01: [standart API tarayıcı regresyonu 46088075012](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46088075012) BAŞARILI. Gerçek yükleme/çıkarım HTTP 200, 39.276 üçgen üretildi ve aynı sayıda çizildi, sıfır GLB hata/uyarı ve JS hatası, yön/normaller doğru. [Ön/arka/yan ekran görüntüleri ve GLB](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46088075012/artifacts/15240366102) indirildi ve görsel incelendi: arka yüzey dalgalı, eski karakter şablonu kontrolleri görünür; genel AI modeline zorunlu şablon uygulanmıyor. [d9c3fc1](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/d9c3fc1ffdf3fa28fa06dc62767059b096a5cc68): mevcut AI menüsüne standart 128/yüksek 192 detay seçimi ve statik API yönlendirmesi eklendi, rig yolu değişmedi. [5f06cc7](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/5f06cc7dbcab9e70072914c36f6ca89afada7660): gerçek yüksek detaylı sandalye çıkarımı, 800x360/740x360/667x375 menü sınırları ve 3 açılı ekran görüntüsü CI testi eklendi. [Yeni tarayıcı testi 46088261792](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46088261792) ve [API testi 46088093473](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46088093473) sürüyor; yeni detay seçimi henüz görsel/işlevsel kabul almadı. Yerel Chromium HTTP erişimi ERR_BLOCKED_BY_ADMINISTRATOR nedeniyle yerel görsel test tamamlanamadı. F01 AKTİF; toplu üretim, çok açılı/yazıdan üretim, görsel kusurlar, güvenli LOD ve yeni fotoğraf/mekanik nesne testleri açık; F02 başlatılmadı.
