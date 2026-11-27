# R70.12 — Dış destek ve görsel denetim
Kaynak dosyaları yerel depoya alındı; mevcut R70.11 ve önceki HTML'ler korunur.

| Kaynak | Durum | Pin / lisans |
|---|---|---|
| Meshoptimizer | R70.11'deki deneysel düğme korunur; gerçek WASM yürütme doğrulanmadı | v1.0 MIT |
| SculptGL | Brush.js, Smooth.js, Inflate.js ve lisans arşivde; Inflate algoritmasının sınırlı uyarlaması R70.12'de bağlı | stephomi/sculptgl master, MIT |
| Three.js | core ve module min.js dosyaları yerel arşivde; mevcut görüntüleyiciye bağlanmadı | r180 MIT |
| Manifold | lisans, WASM README ve API tipleri arşivde; JS/WASM çalışma motoru eksik | elalish/manifold master, Apache-2.0 |
| Watlas | JS dağıtımı, tipler, README ve lisans arşivde; WASM eksik | toji/watlas main, MIT; dağıtımın bağımlılık lisansları ayrıca kontrol edilmeli |
| Quaternius | UAL Standard lisans metni alındı, GLB alınmadı | CC0 |
| KayKit | Adventurers lisans metni alındı, karakter/animasyon GLB alınmadı | CC0 |

İkili transfer engeli: GitHub fetch UTF-8 metin kabul eder. Watlas WASM içerik isteği hata verdi. Yerel çalışma ortamının ağ erişimi de başarısız oldu. Paketler indirilmiş gibi gösterilmez.

## Eksik dosyaların kaynakları
- Watlas WASM: https://github.com/toji/watlas/blob/main/dist/watlas.wasm (blob 0a8a80a272d41bac2374073a35aacde884b4501e)
- Manifold npm: https://www.npmjs.com/package/manifold-3d (JS/WASM, sürüm doğrulanarak alınacak)
- Quaternius resmi ücretsiz paket: https://quaternius.itch.io/universal-animation-library
- Quaternius UAL1 Standard CC0 yeniden dağıtımı: https://github.com/NafisRayan/Animate-Rigged-Humanoid-No-Blender (commit 5821923af517ac5fdc82505faa92a0d575fc1b1a; UAL1_Standard.glb, 7618436 bayt)
- KayKit resmi ücretsiz animasyon: https://kaylousberg.itch.io/kaykit-character-animations
- KayKit resmi Adventurers: https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0 (commit 672074b73ba276876a19e8816ecdc5241817ab47; Characters/gltf/Knight.glb, 3659532 bayt)

## R70.12 fırça testi
MakeHuman başında 8148 üçgen korunarak 11170 köşe oluşumu değiştirildi (benzersiz köşe sayısı değil). Maksimum hareket 0.008739 model birimi. Sıfır alanlı üçgen 0. JSON geri okuma ve kaynak geometriye geri dönüş başarılı. JS sözdizimi geçti. Seçili kaynak parçasına koordinat/radyus/güç temelli şişirme ve içe çökertme, 32 işlem sınırı ve son işlemi geri alma eklendi. Tam SculptGL, parmakla yüzey seçimi ve Smooth henüz bağlı değil. Altı CPU raster görünüşü (ön/yan/arka, önce/sonra) incelendi: burun/yüz şekli değişiyor, yüksek güçte göz küresi kısmen örtülebiliyor; boyun kesiti açık. Normaller yeniden hesaplanıyor fakat tüm dikiş ve kesişimler doğrulanmadı. Fırça görsel kabulü açık. Three.js çekirdek denemesi test ortamında AbortController bulunmaması nedeniyle çalışmadı. Tarayıcı, fiziksel Android ve WebAssembly testi geçilmedi. R70 açık; R71'e geçilmedi.
