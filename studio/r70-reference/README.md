# R70 — Kırık Mühür kaynak desteği

Kaynak: marazali02012-wq/Kirik-Muhur, dal ccr-8065385b-gkmyx1, commit 44decbb3d7761bfc812eecff87e907bcabff68f9, forge/src/. Kullanıcı isteğiyle aynı sahibin Forge Studio projesine referans kopyaları aktarıldı. Kırık Mühür değiştirilmedi.

- f3d_math.js: e438660aaee6bf7a8def80e8fe4231e151f74a9b
- f3d_rig.js: 28f9e685776aff64b2eba58e7300b8e1019b1f34
- f3d_mesh.js: 6a48d423eb64de7d34c02cfbf159a97870f2447f

JavaScript kaynakları bağımsız olarak yüklenip gerçek mesh üretimi denendi. İndeksler ve eklem indisleri sınır içinde, konumlar sonlu, ağırlık toplamları 1 toleransında.

```json
[
  {
    "style": {},
    "vertices": 5459,
    "triangles": 8102,
    "parts": 34,
    "weightError": 2.9802322387695312e-8,
    "valid": true
  },
  {
    "style": {
      "helmet": "full",
      "weapon": "axe",
      "cape": false,
      "shield": true
    },
    "vertices": 5468,
    "triangles": 7942,
    "parts": 34,
    "weightError": 2.9802322387695312e-8,
    "valid": true
  },
  {
    "style": {
      "armor": "light",
      "weapon": "staff",
      "cape": true
    },
    "vertices": 4972,
    "triangles": 7330,
    "parts": 30,
    "weightError": 2.9802322387695312e-8,
    "valid": true
  }
]
```

R70.2'nin 34.120 üçgenli anatomik taslağına göre varsayılan eski Forge modeli 8.102 indeksli üçgen ve 5.459 vertex ile daha hafiftir; farklı tasarımlar olduklarından bu kalite veya hız karşılaştırması değildir. UV ve iskelet verisi referans olarak korundu, R71/R72 entegrasyonuna geçilmedi. HTML düzenleyiciye henüz bağlanmadı. Görsel kalite, gerçek Android FPS, tüm yüzeylerin topolojik uygunluğu ve stil seçeneklerinin gerçek görünümü doğrulanmadı. KayKit arşiv dalı yalnızca envanter içerir; üçüncü taraf paketler kopyalanmadı.

R70 kabulü AÇIK: detay geometrisi, düzenlenebilir parça kimlikleri, birden fazla karakter tipi, üç açı görsel denetimi ve mobil tarayıcı testi tamamlanmadan sonraki aşamaya geçilmez.
