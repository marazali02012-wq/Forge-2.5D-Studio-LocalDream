# R70.9 — Görsel ve teknik denetim

Önceki blob: 27fd480305b093814ad2a1226b9373cfd5cc8943. Yeni blob: c90eba9ed53a886128fa240f861a11a042c7ad88.

Gerçek mesh CPU rasterizasyonuyla R70.8/R70.9 ön ve yan yüz, ön ve yan silah kavrama yakın planları karşılaştırıldı (8 görüntü). Göz kapakları, dudaklar, burun delikleri ve parmaklar görünür; el kabzayı sarıyor. Bununla birlikte yüz hâlâ stilize, göz çevresi çizgili, parmaklar segmentli ve eldiven geometrisi profesyonel hedefin altında. Silah kavrama temasının tüm yüzeylerde çakışmasızlığı kanıtlanmadı. Parmaklar statik geometridir; ayrı parmak kemikleri yoktur.

| Model | Üçgen | GLB bayt | Sıfır alanlı üçgen | Birim normal hatası | GLB geri okuma |
|---|---:|---:|---:|---:|---|
| Şövalye | 20316 | 539912 | 0 | 0 | Konum/normal/renk birebir |
| İzci | 16564 | 440144 | 0 | 0 | Konum/normal/renk birebir |
| Muhafız | 18180 | 489080 | 0 | 0 | Konum/normal/renk birebir |

JS sözdizimi, parça doğrulaması, sonlu geometri, GLB indeks ve veri kontrolü geçti. Bu aşamada yalnızca yakın plan CPU görsel kontrolü yapıldı; tüm model açıları tekrar render edilmedi. Gerçek tarayıcı/Android FPS ve animasyon doğrulanmadı. Üçgen bütçesi yükseldi; mobil optimizasyon ve doğal anatomi açık. R70 görsel kabulü RED. R71'e geçilmedi. Önceki dosyalar korundu.
