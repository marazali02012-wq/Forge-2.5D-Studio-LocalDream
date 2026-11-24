# V36 — Şeffaf materyal

Yerel HTML SHA256: 99fc313651e20f2a7fbc950e1e3486fd9179530ad2e25d4a0b55537986779a62. Bu kayıt HTML kaynak kodu değildir.

CPU raster: opak ve MASK önce, BLEND üçgenleri merkez derinliğine göre arkadan öne; opak derinlik testi, saydam yüzeyler derinliğe yazmaz, lineer RGB source-over, ortak kenar yarı açık kuralı. Dokusuz alphaFactor da işleniyor.

Chromium: tek 0.5 alpha=128; iki katman=192; ters giriş sırası aynı RGBA [137,12,186,192]; MASK 0.2=0; OPAQUE 0.2=255; arkadaki BLEND opak yüzeyi değiştirmedi. 5 animasyonun 5 örnek karesi ve 24 PBR haritası regresyonu geçti (MR 11034, normal 10472, AO 11417, emissive 19282 farklı kanal). Sentetik test, gerçek Android değil. Kesişen üçgen sıralaması yaklaşık, tam PBR/IBL yok. Creations3D model hazır fakat yerel DNS nedeniyle indirilemedi. Render çalışma alanı onayı gerekli. Main değişmedi.
