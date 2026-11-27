# R70.6 — Görsel denetim ve kabul durumu

Her değişiklikten sonra gerçek mesh üzerinden görsel denetim, önceki işlevlerin regresyonu ve ölçüm yapılır. R70 kabul edilmeden R71'e geçilmez.

R70.5 blob 9942cde99abb46fbe678fe91a9436b7e3cd98573; R70.6 blob 731c816d8fccbf87d07eb6b514de832bb0e47a9c. Üç karakterin her biri ön, yan ve arka ortografik CPU rasterizasyonu ile karşılaştırıldı (her sürüm 9 görünüş, aynı ölçek). Bu gerçek geometri görüntülemesidir, WebGL tarayıcı ekran görüntüsü değildir.

Gözlem: düz ve gövdeden uzak görünen zırh plakalarının yerine kalınlıklı eğri kabuklar, miğferin yan bağlantıları ve çizme manşeti iyileştirildi. İzci yeşil giysiye kavuştu. Miğfer hâlâ basit; baş/yüz, pelerin kıvrımları, omuz detayları, malzeme gerçekçiliği ve doğal oranlar hedef altında. Göğüs mücevherinin yan görünüşte ayrık durması da açık. R70 görsel kabulü RED.

| Model | Üçgen | GLB bayt | Sıfır alanlı üçgen | İndeksli GLB okuma |
|---|---:|---:|---:|---|
| Şövalye | 10168 | 277636 | 0 | Konum/normal/renk birebir |
| İzci | 6360 | 178140 | 0 | Konum/normal/renk birebir |
| Muhafız | 9616 | 266184 | 0 | Konum/normal/renk birebir |

JavaScript sözdizimi, sonlu geometri ve parça doğrulaması geçti. Kapalı/manifold model, tüm kabuk normalleri ve kesişimlerin yokluğu bu testle kanıtlanmaz. Android, gerçek tarayıcı arayüzü, GPU ve FPS doğrulanmadı. Önceki kaynak-parça projeleri aynı parça adlarıyla yeniden üretildiğinde geometri revizyonu değişebilir; tam sürüm uyumluluğu test edilmedi. Önceki HTML korunmuştur. R71/R72 başlatılmadı.
