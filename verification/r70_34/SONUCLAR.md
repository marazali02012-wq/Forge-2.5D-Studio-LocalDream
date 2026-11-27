# Forge R70.34 test raporu

R70.33 tabanı 17213ff. R70.34 geliştirme kaydı dc9730c. Ayrı Render önizlemesindeki HTML, derlenen dosyayla SHA-256 düzeyinde aynı.

| Girdi | Yerel API süresi (sn) | Saldırıda p99 kenar oranı | Beş klip ve tarayıcı zinciri |
| --- | ---: | ---: | --- |
| archer | 37.83 | 1.357 | Geçti |
| astronaut | 31.92 | 1.467 | Geçti |
| guard | 29.96 | 1.420 | Geçti |
| healer | 32.27 | 1.474 | Geçti |
| knight | 30.76 | 1.354 | Geçti |
| mage | 35.46 | 1.417 | Geçti |
| miner | 35.07 | 1.411 | Geçti |
| pilot | 31.69 | 1.354 | Geçti |
| robot | 33.13 | 1.338 | Geçti |
| scout | 33.65 | 1.492 | Geçti |

On özgün PNG tarayıcıdan tekrar yüklendi. Her istek CPU üzerinde gerçek TripoSR çıkarımı çalıştırdı. Yüzey yumuşatma koruması önceden belirlenmiş ölçütler sağlanınca adayı kullanır. Sonrasında UV atlası, gömülü PNG doku, 26 kemik ve beş animasyon yazıldı. Beş kamera açısı açıldı ve GLB tarayıcıdan indirildi. On animasyonlu ve bir statik GLB bağımsız Khronos doğrulamasında sıfır hata ve uyarı verdi. API eşzamanlı isteği 429, hatalı anahtarı 401, yabancı origin'i 403, büyük yüklemeyi 413 ile döndürdü. TLS üzerinden canlı üretim ve uzun süreli yük testi açık.

Okçu için gövde kesitleri anatomik ekseni hesaplıyor. Büyücü ve şifacı saldırısında bilek, dirsek, üst kol ve gövde hareketi yeniden dağıtıldı. Yürüyüşte duruş ayağının taban merkezine kök düzeltmesi uygulandı. Tam sabitleme bölgelerindeki ortalama taban merkezi sayısal olarak yerinde kaldı. Ayak değişimi sırasında harmanlama var. Bağımsız GLB örneklemesi her animasyonda 121 zaman örneğinde en alt noktanın boyla oranını %-0.038 ile %0.460 arasında ölçtü. Ters kinematik ve ayrı parmak kemikleri açık. Tabanın çapraz hareketi ile bütün ayak geometrisinin doğal şekli ayrıca ele alınmalı.

Görsel denetimde şifacının arka dokusundaki leke ve bazı ince yan profiller sürüyor. Yerel renk yumuşatma lekeyi hafifletti ancak ayrıntıyı da yumuşattı. %15 derinlik düzeltmesi ölçülmüş bir yan görünüşe dayanmadığı ve asayı da kalınlaştırdığı için genel akışa alınmadı. Tek fotoğraftan arka dokunun ve hacmin doğruluğu onaylanamaz. Önceki statik 128/192 üretim ve editördeki hafif dışa aktarma korundu.

800×360, 740×360 ve 667×375 Chromium testlerinde kaydırarak döndürme, iki parmak yakınlaştırma, beş klip ve bayt düzeyinde eşleşen indirme kontrol edildi. Tarayıcı yazılım işleyicisi kullanıldı. Fiziksel Realme C55, Android FPS, GPU ve bellek ölçümü için cihaz bağlantısı gerekli. Test girdileri özgün proje çizimleri. Kullanıcı tarafından yüklenen yeni görselle canlı test bekliyor.

Çalışan statik editör https://forge-r70-editor-preview.onrender.com/?r=7034

Üretim onayı verilmedi. Canlı AI sunucusu, fiziksel telefon testi ve görsel kalite onayı bekliyor. Bulut karşılaştırması hosting.md dosyasındadır.

Oracle konsolu ve ücretsiz katman sayfası bu tarayıcıda “Site Unavailable” döndürdü. Hesap, bölgesel Ampere kapasitesi ve VM dağıtımı doğrulanamadı. Yeni ARM64 Docker yolu için temel Python paketlerinin aarch64 dağıtımları kontrol edildi. OCI üzerinde imaj derlemesi bekliyor.
