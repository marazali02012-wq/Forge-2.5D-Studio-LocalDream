FORGE STUDIO R7 — Birleşik genel amaçlı 3D stüdyo
Arena Forge oyun kodu veya hazır karakter yok. TripoSR gerçek CPU üretimi. R6 model yönü onarımı korunur.

ÇALIŞTIRMA (telefon değil, Linux sunucu)
Docker: docker build -t forge-studio .
En az 16 karakter FORGE_PASSWORD ortam değişkeni tanımlayın (gizli tutun).
docker run --rm -p 127.0.0.1:7860:7860 -e FORGE_PASSWORD forge-studio
Tarayıcı: http://127.0.0.1:7860, kullanıcı forge.
Ubuntu 24.04 + Python 3.11 için setup.sh; sanal ortamda uvicorn server:app --host 127.0.0.1 --port 8000.
Uzak erişim: HTTPS reverse proxy; FORGE_PUBLIC_ORIGIN tam HTTPS adresi. Ücretli hizmet otomatik oluşturulmaz. Tek kullanıcıya yönelik altyapıdır.
Önceki R5 2 CPU gerçek uçtan uca testinde tepe RAM 4.1 GiB. R7 128/160 çözünürlük ve Blender için daha fazla kaynak gerekebilir. 8–16 GB RAM önerisi ölçülmüş minimum değil. İlk model indirmesi internet gerektirir.

İŞLEVLER
- Kaynak görsel, güvenli/AI fon önizleme, saydam piksel sınırından kırpma, geri alma.
- TripoSR CPU: 96/128/160 geometri; 512/1024 doku. SF3D ve TRELLIS.2 harici seçenekler; kota/API engeli olabilir.
- GLB inceleme, kalıcı dönüş, ölçek, PBR metalik ve pürüzlülük, 3 adımlı model geri alma. Mevcut GLB bin/doku korunur. Temel önizleme tam PBR değildir.
- Statik OBJ+MTL+doku ZIP. Rigli/animasyonlu modeller OBJ'ye dönüştürülmez.
- Blender kuruluysa gerçek üçgen azaltma ve FBX dışa aktarma. Üçgen hedefi yaklaşık, otomatik quad retopoloji değildir. Rig/animasyon/morph içeren modellerin azaltılması engellenir.
- Gelişmiş PBR/var olan rig animasyonu: çevrimiçi model-viewer bağımlılığı; henüz gerçek oynatma doğrulanmadı. Yerel temel görünüm korunur.
- Mobil üretim/model sekmeleri ve yakınlaştırma.

DOĞRULAMA
R5 gerçek CPU tarayıcı -> GLB indirme başarılı (2 örnek). R7 yerel testleri: kırpma/geri alma, gerçek UV GLB dönüş/ölçek/PBR kayıt, BIN koruma, 3 geri alma, OBJ/MTL/UV/doku, zoom, hata koşulları. Gerçek Android test edilmedi. R7 geniş üretim ve Docker/Blender/rig oynatma GitHub testleri başlatıldı; sonucu henüz kesin değil. Canlı kamu sunucusu yok. Otomatik anatomik rig, yeni doğal animasyon üretimi, metinden 3D, semantik parçalama ve quad retopoloji tamamlanmadı. Tripo ile kalite eşitliği iddia edilmez.

Kalite kontrolü: ön silüet IoU ve eksik ayrı alfa adaları sezgisel ölçümlerdir; düşük skorda en fazla 3 gerçek geometri çıkarımı yapılır. Doku rengi düğmesi sadece önizlemeyi değiştirir. Tek görüntüden 3D arka yüz doğrulanamaz.


Kalite güncellemesi: Ön silüet uyarısı oluşursa aynı sahne kodunu tekrar çıkarmak yerine %85, %94 ve %72 nesne kadrajıyla en fazla üç gerçek TripoSR çıkarımı denenir. Seçilen geometri kendi sahne kodundan kaplanır. Görsel kalite garantisi yoktur; beş açı ve manuel kontrol gereklidir. Yeni çıkarım testi: https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/45440466196

Düzeltme: TripoSR doku motoruna 5B toplu tensör yerine tek 4B sahne veriliyor. Yerel boyut kontrolü başarılı; canlı AI yeniden testi ve görsel onay henüz tamamlanmadı.


Kalite denemesi: kaynak siluet uyumlu ise gorunen on yuz UV renklerine dayanarak sinirli parlaklik kalibrasyonu denenir. Egitim disi piksel bloklarinda fayda ve parlaklik kirpilmasi kontrol edilir. Yuz ve arka yuz kalitesi garantisi degildir. Diger modellerde orijinal doku korunur. Canli entegre test henuz sonuclanmadi.

Atlas kalite onarımı: yalnızca yapay zekâ tarafından üretilen opak dokularda UV dışı boş renk pikselleri doldurulur. Mevcut geçerli texeller korunur. Geometri raporu bileşenleri işaretler, silmez. 9 gerçek GLB üzerinde ve 90 açı görüntüsüyle önce/sonra kontrol edildi. SS kalite onayı yok; birleşik canlı test bekleniyor.

256 geometri / 2048 doku deneysel seçenekleri: daha yüksek RAM ve süre gerektirebilir. SS kalite garantisi yoktur. Canlı performans ve görsel karşılaştırma henüz doğrulanmadı.

Geometri adaları: tek statik GLB için geometrik bağlantıya göre listeleme ve ayrı GLB olarak seçili parçayı indirme. Kaynak dosya değiştirilmez. Semantik/anatomik bölme, rig üretme veya otomatik parça silme değildir.

2K önizleme: WebGL2 üzerinde seçilebilir 1024/2048 piksel üst sınırı. CPU önizleme 1024 ile sınırlıdır. Doku boyutları kaynak ve önizleme olarak gösterilir; dışa aktarılan GLB değiştirilmez.

Hassas dönüş: -180 ile 180 derece arasında 0,1° adımlı manuel GLB dönüşü. Geometrik ada temizliği: yalnızca ana gövde dışı, en fazla 64 üçgen ve %0,05 alanlı adalar, açık kullanıcı onayı ile. Otomatik silme yok. Geri alma mevcut. Bu yöntem gerçek anatomi veya hatalı taban geometrisini yeniden üretmez.

Deneysel kılavuzlu rig: 2–64 açık eklem, statik tek mesh ve dönüşümsüz GLB. Mesafe tabanlı skin ağırlıkları ve tek eklem test klibi; otomatik anatomi veya doğal yürüyüş değildir.

Yerel Forge rig oynatma: tek mesh, Forge landmark rig, normal verisi ve en fazla 200.000 vertex; yalnız lineer eklem rotasyon klibi. CPU skin hesaplaması, WebGL2 veya CPU görüntüleme. 78.019 vertex gerçek rig ile yerel Chromium CPU oynat/duraklat/başlangıç ve 9 poz/açı kontrolü başarılı. GLB birebir korundu. Gerçek WebGL2 ve Android animasyon performansı henüz doğrulanmadı. Otomatik anatomi ve yürüyüş üretimi değildir.

Çoklu hareket: guide.clips, name/duration/tracks; joint ve keys=[saniye,X,Y,Z] yerel intrinsic XYZ. Önce klipleri hazırla, sonra seç. Otomatik anatomi değildir.

Eklem yardımı: statik, kapalı tek GLB ve mevcut kılavuz gerektirir. Geometrik orta hat yalnız öneri üretir; uzuv tanımaz. Kullanıcı inceleyip onaylamadan kılavuz veya model değişmez. En fazla model köşegeninin %3,5 kadar öneri yapılır.

Kılavuzlu yürüyüş: 10 elle eşlenen eklem, karşı fazlı kol ve bacak rotasyonları, yön seçimi ve 0,9/1,2/1,6 saniye seçenekleri. Klip standart GLB quaternion animasyon kanallarına yazılır. Baş ve gövde için ayrı sabit eklemler gereklidir. Mevcut rig testi ve diğer klipler korunur. Bu bir yerinde döngüdür; ayak IK, zemin teması, otomatik anatomi veya doğal insan hareketi garantisi yoktur. Ayrık geometri adalarında eklem önerisi engeli son GitHub değişikliğinden alındı.
Test: Chromium CPU önizleme, sentetik 13 eklemli model, hatalı boş eşleme reddi, 10 kanal, FastAPI TestClient gerçek rig yanıtı, GLB yeniden yükleme, vertex değişimi, döngü uç eşitliği, oynatma/duraklatma, 5 poz görsel kontrolü. Tarayıcı ağ politikası nedeniyle HTTP üzerinden birleşik uçtan uca düğme akışı doğrulanamadı; API ve arayüz ayrı ayrı test edildi. Gerçek zırhlı karakter, ayak kayması, GPU ve gerçek Android testleri açık. GitHub'a bu sürüm gönderilmedi.

T-poz otomatik eklem önerisi (deneysel): Y-yukarı, tek kapalı ve birleşik gövde, iki yana açık kollar, ayrı bacaklar. 21 eklemli geometrik kılavuz oluşturur, kullanıcı onayı olmadan modele dokunmaz. Öğrenilmiş anatomi tanıma değildir. Yürüyüşte standart eklem adları otomatik eşlenir, T-poz omuzları aşağı indirilir. Başka pozlar, çoklu parçalı zırh, parmaklar, gerçekçi zemin teması ve IK desteklenmez. Sunucu gereklidir. Test: iki prosedürel insansı mesh, kutu ve ayrık mesh reddi, gerçek FastAPI çağrıları, Chromium test köprüsü üzerinden öneri/onay/rig/oynatma. Test ortamında HTTP ağ erişimi engellendiğinden yalnız test sayfasında protokol kontrolü devre dışı ve fetch köprülendi; teslim edilen HTML'de koruma yerinde. Gerçek Android ve canlı sunucu testi yok. test_auto_rig.py tekrar üretilebilir yerel testtir (Playwright/Chromium gerekir).

IK YÜRÜYÜŞ: 61 örnekli iki kemikli ters kinematik, sabit destek ayak bileği hedefi, ileri kök hareketi. Forge sunucusu gereklidir. Mevcut rotasyon klipleri desteklenir; GLB çeviri kanalı da oynatılır. Döngü önizlemesi başlangıca sıçrar; oyun motorunda root-motion biriktirme gerekir. Y-yukarı, +/-Z ileri ve aşağı yönlü bacaklar gerekir. Ayak bileği hedefi sabit olsa da gerçek mesh tabanı, kıyafet ve ağırlıklar ayrıca kontrol edilmelidir. Sentetik modeller dışında doğrulanmadı. test_gait.py ve test_auto_rig.py yerel testleri içerir; sonuncusu Chromium ve Playwright gerektirir.

SALDIRI KLİBİ: Omuz-dirsek-bilek rollerini elle veya standart isimlerle eşleyin. Sağ/sol kol ve +/-Z yönü seçilebilir. 0,9 saniye, 61 örnek, dört rotasyon kanalı. Hazırlık, geri çekilme, vuruş, toparlanma ve başlangıca dönüş. Mevcut IK yürüyüşü ve diğer klipler korunur. Yeni combat.py sunucuda gereklidir. Silahsız yumruk; gövde, bacaklar, parmaklar, silah ve çarpışma animasyonu henüz yok. Gerçek karakterlerde skin kalitesi garanti edilmez.
Test: test_combat.py ile iki yön x iki kol, geçersiz roller, tekrarlı ekleme, gerçek FastAPI rig üretimi ve Chromium CPU önizlemesi, GLB yeniden yükleme, IK oynatma ve 5 poz ekran görüntüsü. Sentetik omuz zırhlı manken. Chromium ağ kısıtı nedeniyle testte gerçek API'ye TestClient köprüsü kullanıldı; canlı sunucu ve gerçek Android cihazı test edilmedi. Görsel kontrolde hareket okunabilir, gövde ve ayaklar sabit; doğal profesyonel dövüş kalitesi değil. GitHub güncellenmedi.

HASAR / ÖLÜM: 15 eşlenmiş insansı eklem, Y-yukarı, +/-Z ileri. Hasar 0,65 sn, geriye sarsılma ve gard pozuna dönüş. Ölüm 1,5 sn, geriye düşüş ve gevşeyen kollar. 61 örnek, 12 rotasyon ve 1 kök çeviri kanalı. Skin ağırlıkları üzerinden her örnekte ağın en alt noktası başlangıç zeminine hizalanır; fizik tabanlı ragdoll veya örnekler arası kesin çarpışma garantisi değildir. Forge yerel oynatıcı hasar/ölüm kliplerini bir kez oynatır, son pozda durur. Harici oyun motorunda döngü kapatılmalıdır. En fazla 200.000 vertex. Sunucu reaction.py gerektirir.
Test: test_reaction.py ile sentetik manken, gerçek FastAPI TestClient köprüsü ve Chromium CPU önizleme, beş örnekte iki klip zemin kontrolü, GLB yeniden yükleme, son pozda durma, önceki yürüyüş/saldırı koruma, -Z yönünde ölüm oluşturma ve geçersiz rol reddi. test_gait.py iki yön başarılı. Gerçek karakter, Android, WebGL2 ve canlı sunucu doğrulanmadı. GitHub güncellenmedi.

CALISMA ALANI (Tripo referansli, ozgun Forge): Yedi ayri sekme: Uretim, Model, Parcalar, Topoloji, Materyal, Iskelet, Animasyon. Tek kalici 3D onizleme ve sekmeye gore degisen arac paneli. Mevcut 122 ID korunur. Animasyon klibi ekledikten sonra Iskelet sekmesinde rig olusturun ve Animasyon sekmesinde oynatin. test_workspace.py: Chromium CPU, 5 ekran boyutu, sandalye GLB iceri aktar/dondur/PBR kaydet/geri al/birebir disari aktar, gorsel yukle, 7 sekme, kamera araclarinin yatay ekranda gorunurlugu. test_reaction.py ve test_gait.py tekrar basarili. Tarayici agi nedeniyle gercek FastAPI TestClient koprusu kullanildi; canli sunucu ve Android GPU dogrulanmadi. Vertex renkleri temel onizlemede gosterilmiyor. AI uretim motoru degistirilmedi; Tripo uretim kalitesi, metinden 3D, semantik parcalama ve quad retopoloji acik.
