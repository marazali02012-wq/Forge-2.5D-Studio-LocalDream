# V37 — Stüdyo ışığı

Yerel HTML SHA256: 23926a0763115cc6a473a5e34e9a67dbe877a9706a35305c43cdd16a0293070b. Bu dosya test raporudur, HTML kaynak kodu değildir.

Dünya koordinatlarında iki analitik çevre ışığı lobu, pürüzlülüğe göre yayılım, Fresnel, hemisfer dolgu, parlaklık sıkıştırması; glTF doğrusal vertex renk interpolasyonu. Eski ışık seçeneği korundu. Gerçek HDRI değil.

Chromium çevrimdışı: beş klip x beş örnek kare; 24 harita regresyonu (MR 28689, normal 21947, AO 28923, emissive 19282 farklı kanal). Saydamlık 128/192 alfa, ters sıra eşit, MASK ve opak derinlik testi geçti. 31372 piksel küre testinde eski parlak metal ortalama 69.14, yeni parlak 95.78, yeni mat 90.81; parlaklık standart sapması 29.04/19.81 (parlak/mat). En az bir kanalı 255 olan piksel 117/86/0. Sentetik test; gerçek savaşçı ve Android doğrulanmadı. Main, Render ve Supabase değiştirilmedi.