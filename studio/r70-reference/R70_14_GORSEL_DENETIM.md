# R70.14 — Three.js gerçek tarayıcı denetimi

R70.13 Manifold kapalı katı işlemleri: GitHub Actions 46046174786 başarılı.
R70.14 Three.js r180: GitHub Actions 46047880676. 800x360, çevrimdışı Chromium, yazılımsal GPU; fiziksel Android değil.
İlk deneme 46047799666, Ubuntu 26.04 üzerinde Playwright Chromium kurulumu desteklenmediği için başarısız oldu. Ubuntu 24.04 sabitlendi.
Son test: 20.316 üçgen birebir görüntülendi, tek draw call; 530x280 canvas. Manifold union hacmi 1.5, 28 üçgen, GLB 2456 bayt. Eski motor dönüşü başarılı. Sıfır JavaScript hatası, diyalog ve HTTP isteği.
Gerçek PNG ekran görüntüleri incelendi: R70_14_old.png, R70_14_three.png, R70_14_side.png, R70_14_back.png. Three.js aydınlatması göğüs plakası ve miğfer hacmini daha görünür yapıyor. Model üç açıda görünür, ancak anatomik kalite hâlâ stilize; zırh ve el detayları hedefin altında. Üst menü iki satır; yan panellerde kaydırma gerekiyor, 800x360 ekranda model görece küçük. Görsel kalite kabulü RED. Three.js opsiyonel, eski WebGL2 korundu; iki GPU context maliyeti fiziksel Android'de ölçülmedi. Watlas, Quaternius ve KayKit paketleri depoda, işlevsel entegrasyon henüz yok. R71 başlatılmadı.
