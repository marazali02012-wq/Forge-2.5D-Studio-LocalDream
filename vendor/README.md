# Forge Studio R70 — Harici açık kaynak desteği

Kullanıcının talebiyle TinyFish üzerinden upstream kaynaklar incelendi, GitHub üzerinden gerçek dosyalar alındı. Ücretli paket satın alınmadı.

## MakeHuman
- Kaynak: https://github.com/makehumancommunity/makehuman/blob/master/makehuman/data/3dobjs/base.obj
- Upstream blob d26635e9326e3cca30778fd7b9c00062b03cce09, 1.749.303 bayt, 19.158 vertex (yardımcı gruplar dahil). Orijinal OBJ, LICENSE.md ve LICENSE.ASSETS.md saklandı. CC0 1.0 varlıklar; AGPL uygulama kodu alınmadı.
- R70.10/R70.11 HTML içinde gerçek baş, iki göz ve iki el geometrisi, body/eye gruplarından seçilerek ölçeklendi, üçgenleştirildi, normaller hesaplandı. Baş+göz 8428 üçgen, her el 2846. Eklenebilir/düzenlenebilir parçalar; proje JSON geri okuması ve GLB üretimi geçti. CPU rasterizasyonunda 6 görünüş (baş/el ön-yan-arka) kontrol edildi. Yüz önceki prosedürel taslaktan daha anatomik, gözler renksiz, boyun/bilek kesitleri açık ve tırtıklı. Tam vücut, UV, rig, gerçek Android testi ve otomatik karakter birleşimi yok. Orijinal tam vücut OBJ saklı.

## meshoptimizer
- Kaynak: https://github.com/zeux/meshoptimizer/tree/v1.0, MIT; upstream js/meshopt_simplifier.js blob d5d7264b9ae3ef0ed118c4edd89191b41838bc2b, 55.064 bayt. Orijinal .mjs ve MIT lisansı saklandı.
- R70.11 HTML içine MIT bildirimiyle gömüldü, çevrimdışı deneysel Hafif GLB butonu eklendi. Parça bazında normal/renk ağırlıklı simplifyWithAttributes, LockBorder ve .008 göreli hata hedefi. Normal GLB kaydı korunuyor. JS sözdizimi, sarmalayıcı kimlik, geçersiz indeks reddi ve hata durumunda kaynak geometriye dönüş sahte API ile test edildi. Kullanılan JS test ortamında WebAssembly yok, gerçek sadeleştirme, görsel karşılaştırma ve Android performansı doğrulanmadı. Deneysel, kabul edilmiş sayılmaz.

SculptGL, Manifold, Three.js, Watlas, Quaternius ve KayKit henüz aktarılmadı/entegre edilmedi. R70 açık; R71 başlatılmadı. Önceki HTML'ler korundu.
