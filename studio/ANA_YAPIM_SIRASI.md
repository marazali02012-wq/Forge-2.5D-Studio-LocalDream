# Forge Studio — Ana yapım sırası (R42)

Ana referans Tripo Studio. İşlevsel eşdeğerlik hedef; özgün kod ve tasarım. Genel amaçlı, çok dilli, oyunla sınırlı değil. Öncelik gerçek model, alternatif uygun motor, hafif açık kaynak motor, en son açıkça etiketli yerel yöntem. Ücretli kaynak kullanımı otomatik değil.

| No | Görev | Kabul şartı | Durum |
|---|---|---|---|
| 1 | Global AI komut | Çeşitli dillerde anlam, renk, malzeme, sayı ve olumsuz kısıtların korunması | 7B gerçek testinde 7/7 anlam korundu; daha geniş dil seti ve canlı uçtan uca doğrulama açık |
| 2 | Metinden 2D | Gerçek AI görüntü, konu uyumu, görsel inceleme | SDXS gerçek 2D 3/3 dosya üretildi; masa/sandalye kadraj kusurlu, küre uygun. Kadraj testi gerçek SDXS ile tamamlandı: masa ve sandalye hâlâ kusurlu; SD Turbo 4 adım ve iki seed gerçek testinde 5/5 dosya üretildi; masa/sandalye kadraj kusurlu, küre yüzeyi zayıf (run 45478151939). SD 1.5 16 adım gerçek testinde 3/3 üretim; küre uygun, sandalye ve masa kabul edilmedi; açık seçimle 1–3 aday, seed aralığı, aday kabul/ret ve hata/iptal tarayıcı testi geçti (kayıtlı farklı görüntüler, yeni çıkarım değil); gerçek aynı komutlu iki SD Turbo kaydı ile aday seçimi yeniden oynatıldı; canlı API açık |
| 3 | Metinden 3D | Metin→gerçek GLB, beş açı | Gerçek zincir teknik olarak çalıştı; 5 açı görsel denetiminde yan/üst deformasyon, kabul edilmedi |
| 4 | Tek resimden 3D | Farklı insan/hayvan/nesne örnekleri, silüet ve arka yüz kontrolü | Bir sandalye doğrulandı; kalite açık |
| 5 | Çok açılı 3D | Tutarlı geometri ve kaplama | Temel yerel yol |
| 6 | Oto arka plan silme | Kenar ve saydamlık testi | Gerçek U2NetP küre maskesi başarılı; diğer örnekler açık |
| 7 | Semantik parçalar | Doğru parçalar ve güvenli düzenleme | Kısmi |
| 8 | UV/retopoloji | Karmaşık ağ, dikiş, quad, dokular | Kısmi |
| 9 | AI kaplama/PBR | 360 derece doku, UV ve PBR | Kısmi |
| 10 | Rig | İnsan/hayvan/diğer anatomiler, gerçek mesh | Kısmi |
| 11 | Animasyon | Doğal hareket, klip aktarımı | Kısmi |
| 12 | GPU görüntüleme | WebGL2 gerçek çalışma ve görsel kalite | Doğrulanmadı |
| 13 | Tripo araç düzeni | Tüm ilgili işlevler, gerçek mobil kullanım | Kısmi |
| 14 | Dışa aktarma | GLB/OBJ/STL/FBX yeniden açma, uygun materyal/rig | Kısmi |
| 15 | Global arayüz | Dil seçimi, RTL, taşma ve çeviri | Bekliyor |
| 16 | Android/performans/offline | Fiziksel cihaz, ağ kapalı, FPS/bellek | Bekliyor |
| 17 | Nihai Tripo karşılaştırması | Aynı girdiler, gerçek çıktılar ve görsel farklar | Bekliyor |

Her madde: gerçek işlev testi, /GÖRSEL-DENETİM, önceki işlevlerin regresyonu. Simülasyon, altyapı ve gerçek üretim ayrı tutulur. Bir engel varsa kaynağı ve sonraki alternatif yazılır; ana madde açık kalır.

R35: SD 1.5 gerçek çizim işi 45479317768 henüz sonuçlanmadı. Şeffaf kaynakta kenar teması, boşluk, küçük nesne ve boş maske kontrolü eklendi; opak kaynağın kadrajı doğrulanmış sayılmaz. 5 sentetik maske durumu, gerçek SD Turbo PNG ve gerçek sandalye referansı (42 px kenar boşluğu), 5 Chromium ekran boyutu ve GLB/OBJ/STL regresyonu başarılı. Kırpılmış nesne onarımı yapılmaz. Test kanıtları uygulama ZIP dışında.

R36: 02/17 açık. 03/17 hazırlığı: yerel sunucuda U²-NetP ONNX fon ayırma seçeneği, mevcut tarayıcı maskeleri korunarak eklendi. Ağırlık açıkça kurulmalı: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx → models/u2netp.onnx (veya FORGE_MASK_MODEL). Çıkarım sırasında indirme yok. Maske onaylanmadan kaynak değişmez. Gerçek çıkarım ve görsel kalite ayrıca doğrulanmalı.

R36 doğrulama: SD 1.5 gerçek 3/3 PNG üretimi tamamlandı (run 45479317768): küre uygun, sandalye kırpılmış, masa yerine çekmeceli nesne. 203.41–204.94 sn/PNG (GitHub CPU); kalite kabul edilmedi. Yerel U2NetP API eksik ağırlık, yanlış PNG, başka origin, onay/ret ve geri alma testleri kontrollü yanıtla geçti. 5 Chromium ekran boyutu test edildi. Gerçek U2NetP ve kayıtlı AI çiziminden dokulu GLB üretim testi ayrı dalda başlatılmak üzere gönderildi (commit bae4599d69bd5757574e5fe930494c8e16329c3c); sonucu ve görsel kalitesi açık. 02/17 açık, 03/17 ön hazırlık.

R37: 02/17 açık; 03/17 hazırlığı. CPU TripoSR hazır ve onaylanmamış maskede yeterli kenar boşluğu varsa kullanıcı seçimiyle maske onayı ve 3D üretim tek adımda başlatılır. Küçük maske önizlemesi onay düğmesinin yanında. Kenar teması/boşluk sorunu otomatik kısayolu devre dışı bırakır; elle onay ve üretim korunur. Yeni üretim başarısız olursa önceki model korunur ve kaynak revizyonu farklı gösterilir. Yerel Chromium testi: HTTP sayfa navigasyonu ortam tarafından engellendi; yalnızca test kopyasında HTTP protokol kontrolü devre dışı bırakıldı, API yanıtları kontrollü olarak yeniden oynatıldı (sentetik maske ve önceki gerçek AI GLB). Yüklenen alfa doğrulandı; yeni AI çıkarımı yapılmadı. 5 ekran boyutu, GLB/OBJ/STL regresyonu başarılı. GitHub gerçek zincir run 45483081285 ağırlık kurulumu başarılı, çıkarım devam ediyor; gerçek çıktı doğrulanmadı. Test görselleri ZIP dışındadır.

R38: GitHub run 45483081285 gerçek kayıtlı SD 1.5 küre görseli → U2NetP (0.46 s) → TripoSR GLB (73.57 s). 39.996 üçgen, ön IoU .9832, 15 bağlı parça (14 küçük). Ön görüntü uygun; yan/üst/arka kusurlu, genel kalite reddedildi. Bu kayıtlı görsel üzerinden ayrı adımlardır, birleşik canlı API değil. Motor aday seçiminde ön silüet yakın sonuçları için topoloji ölçümü; topoloji uyarısında erken kabul yok, en çok üç deneme. Gerçek eski GLB ile ölçüm ve sentetik karşılaştırma testleri başarılı; yeni AI çıkarımı yapılmadı. Gerçek GLB çevrimdışı açma/bit özdeş dışa aktarma, OBJ/STL açma, 5 ekran genişliği başarılı. Test kanıtı uygulama ZIP dışında. 02/17 ve 03/17 açık.

R39: R38 gerçek GLB üzerinde bağımsız ölçüm: hull_fill=.82659; radyal p05/p95=.62298. Kapalı olmasına rağmen biçim kusuru var. Üretim motorunda yalnız kalite uyarısı bulunan adayda aynı neural sahneden iki sınırlı yoğunluk eşiği (18/32, başlangıç 25) denenir; önceki kazananın silüet ve topoloji koşulları korunur. Tanısal hacim ve radyal ölçüler genel nesne kalite kabulü değildir. Gerçek yeni çıkarım ayrı test dalında doğrulanmalı; 02/17 ve 03/17 açık. Tahmini teknik ilerleme: 5 gerçek kısmi görev x .60 + 8 kısmi x .30 + GPU altyapısı x .15 = 5.55/17 ≈ %33; tüm kabul koşulları tamamlanan 0/17. Bu eşit görev ağırlıklı öznel tahmindir, zaman/Tripo kalite oranı değildir.

R39 doğrulama: kayıtlı gerçek GLB ile ölçüm; kontrollü çıkarım alternatiflerinde seçim, yetersiz aday reddi, erken çıkış başarılı. Gerçek yeni AI test dalı commit ac4cb2f2e7efac8655120cb17c17803ad8e017ac; sonuç açık. Chromium 5 ekran boyutu, GLB byte özdeş dışa aktarma, OBJ/STL içe aktarma başarılı. UI değiştirilmedi; eski kusurlu GLB ile görsel regresyon, yeni kalite kanıtı değil.

R40/R41: run 45485344868 gerçek yoğunluk testi; 15→6 parça, ön IoU .9873, hull_fill .84369; beş açı kalite reddi. Shap-E run 45486474745 gerçek vertex renkli 302108 üçgen üretti, hull_fill .27697, CPU görüntüleme 150000 üçgen sınırı; kalite reddi. R41 regresyonları: kontrollü T-pose 21 eklem, yürüyüş/saldırı/hasar/ölüm, UV, materyal, dışa aktarma; WebGL2 ortamda doğrulanmadı.
R42: Öncelik yüklenen özgün resimden 3D; SF3D/SPAR3D resmî ağırlıklar lisans/onay gerektiriyor, token yok; bu yollar henüz çalıştırılmadı. İsteğe bağlı kaynak ön yüz projeksiyonu: ön silüet IoU >= .90 ve mevcut görünür atlas texelleri, z tamponu, yüz normali, alfa kenar koruması; geometri değişmez. Gerçek R39 küresinde ön renk MAE 18.859 → 9.161; atlasın %9.588'i hedeflendi; 9.57 sn, görünmeyen alan doğrulanmadı. Gerçek R24 sandalye (.8014 IoU) reddedildi ve eski doku korundu. Bu eski gerçek GLB üzerindeki işlem, yeni AI çıkarımı değil. Kaynak ışığı dokuya geçebilir; seçenek varsayılan kapalı. Docker COPY listesinde eksik density_qa.py düzeltildi; Docker image çalıştırılmadı. Test ve görsel kanıtlar ZIP dışında; 02/17 ve 03/17 açık. İlerleme tahmini %33.

R42 devam noktası: source_projection.py, engine.py, server.py, index.html, Dockerfile. Gerçek kayıtlı küre/sandalye kaplama testi ve kontrollü API aktarımı, Chromium 5 ekran boyutu, dört açı, byte özdeş GLB dışa aktarma başarılı. Arka ve yan geometri kusurlu. Yeni neural çıkarım, Android ve Docker çalıştırma açık. Sonraki: resimden 3D alternatif motor erişim denetimi; çok açılı referansla geometri doğrulaması. Shap-E seçilmedi. Geliştirme dalı forge-r42-source-fidelity; ana dal korunur.
