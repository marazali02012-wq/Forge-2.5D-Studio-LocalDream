# V35 — Yerel materyal doğrulaması

24 Kasım 2026. Yerel V34 HTML üzerinden türetildi; bu dosya yalnızca doğrulama raporudur, V35 uygulama kaynak kodu değildir.

Chromium çevrimdışı, sentetik altı mesh parçası/48 vertex, 24 ek doku haritası. Haritalar ayrı ayrı kapatıldığında yürüyüş karesinde farklı RGBA kanal değerleri: metallic-roughness 11034; normal 10472; occlusion 11417; emissive 19282. Beş animasyonun farklı kare ürettiği ayrı temel doku testinde doğrulandı. İlk denemede sabit değişken atama hatası bulundu ve giderildi. Gerçek Android, tam PBR (IBL/BLEND), gerçek karakter ve TRELLIS.2 uçtan uca doğrulanmadı. Creations3D modeli hazır, yerel indirme DNS engeline; TinyFish incelemesi oturum açma engeline takıldı. Yeni Creations3D kredisi harcanmadı. Ana dal değişmedi.
