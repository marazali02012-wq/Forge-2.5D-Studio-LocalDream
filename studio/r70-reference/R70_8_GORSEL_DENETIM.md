# R70.7–R70.8 gerçek geometri denetimi

R70.6 baz: 731c816d8fccbf87d07eb6b514de832bb0e47a9c. R70.7: ef463d1619bca50df44884654bdc02647251dc34. R70.8: 27fd480305b093814ad2a1226b9373cfd5cc8943.

R70.7: tek sürekli kafa yüzeyinde burun, çene, yanak, göz çukuru, kaş ve dudak kabartmaları; pelerin gerçek kıvrımları ve türev tabanlı normalleri; göğüs mücevheri zırha yaklaştırıldı. Gerçek CPU mesh rasterizasyonu ile 9 tam model görünüşü ve eski/yeni 6 detay görünüşü incelendi. Saç kesişimi fark edildi ve R70.8'de kafa yüzeyini takip eden saç kabuğuyla değiştirildi. R70.7 ve R70.8 için ön/yan/arka 6 yakın plan tekrar incelendi. Önceki arka saç lekeleri ve kesik saç çizgisi belirgin biçimde giderildi. Şövalye ve muhafız R70.8'de saç değişikliğinden etkilenmez; yeni tam model görüntüsü alınmadı.

| Model | Üçgen | GLB bayt | Sıfır alanlı üçgen | Birim normal hatası | GLB geri okuma |
|---|---:|---:|---:|---:|---|
| Şövalye | 15832 | 417316 | 0 | 0 | konum/normal/renk birebir |
| İzci | 12080 | 317548 | 0 | 0 | konum/normal/renk birebir |
| Muhafız | 13696 | 366480 | 0 | 0 | konum/normal/renk birebir |

JavaScript sözdizimi ve parça doğrulama geçti. Yüz hâlâ stilize ve hedef kalite altında; burun profili, göz kapakları, ağız, kulak ve eller daha ayrıntılı olmalı. Saç kabuğunun tüm yüzeylerinde çakışmasızlık matematiksel olarak kanıtlanmadı. Pelerin görsel kıvrımları fizik simülasyonu değildir. Bu test WebGL tarayıcı ekran görüntüsü veya fiziksel Android FPS testi değildir. Yeni topoloji ile animasyon/UV entegrasyonu yapılmadı. Geometri bütçesi arttı; mobil performans ölçülmeden kabul edilemez. R70 kabulü RED; R71 başlatılmadı. Önceki HTML'ler ve kaynak dallar korundu.
