R7 — CPU normal haritası önizlemesi
- GLB normalTexture, scale ve seçili UV kanalı okunur. Üçgen UV türevinden kamera uzayında yaklaşık tangent/bitangent tabanı hesaplanır. Dejenere UV üçgeninde temel aydınlatmaya dönülür.
- Doku rengi modu etkilenmez. Orijinal GLB verisi korunur.
- test_normal_r7.py: 4 sentetik yüzey, normal ölçeği 1/0.5/0 ve haritasız kontrol; GLB dışa aktarma, materyal düzenleme, geri alma, 5 viewport boyutu.
- R6 PBR regresyon testi başarılı. GPU, HDRI, gerçek Android, gerçek model performansı, MikkTSpace/özel TANGENT verisi ve aynalı UV özel durumları doğrulanmadı. Normal haritası fiziksel geometriyi değiştirmez.
