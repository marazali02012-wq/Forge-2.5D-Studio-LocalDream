# F02 — İzole paralel laboratuvar

Kullanıcının 28.11.2026 açık onayı: Claude F01 üzerinde ayrı ZIP ile çalışırken F02 ayrı dalda geliştirilecek. F01 kapanmış değildir. F02 kodu ana dal veya forge-r70-surface-lab'a birleştirilmeyecek; F03 başlamayacak. F01 ZIP geldikten sonra kaynak karşılaştırması ve regresyon yapılacak.

## Sıra
1. Gerçek GLB yüzey seçimi, model kimliğine bağlı etiket dosyası, görünür piksel -> üçgen eşlemesi, komşuluk fırçası ve undo. Yerel deney geçti.
2. SAM2 gerçek nokta maskesi -> görünür üçgen etiketleri; üç farklı gerçek F01 modeli. CI [46096885437](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/actions/runs/46096885437) in_progress. Otomatik semantik etiket değildir.
3. GeoSAM2 çok açılı aktarım ve/veya diğer gerçek açık kaynak parça segmentasyonu. Resmi README https://github.com/VAST-AI-Research/GeoSAM2 : Apache-2.0, CPU mümkün ancak yavaş, 12 render (RGB/depth/normal/camera), gerçek per-face labels. Henüz bağlanmadı. Kullanıcı tıklaması ile görülmeyen yüzeylere aktarım test edilecek.
4. Nesne/parça semantik tanıma, otomatik etiketler, ayrıntı seviyesi ve hata/örtüşme ölçümleri; çok nesneli sahne ve tek nesne kabulü.
5. Bağımsız editör paneli, fırça/maske düzeltme, yeniden açma, üç mobil ekran ve gerçek GLB regresyonu. Claude F01 ZIP gelmeden birleşim yok.

## Modül sözleşmesi
- Girdi: gerçek üçgenli statik mesh, aynı vertex/face sırası, Y-up. Yüzey etiketi JSON'u yalnız SHA256 mesh kimliği ile birebir eşleştiğinde açılır. 0=bilinmeyen. Yeni mesh/geometri sırası değişirse eski etiket dosyası reddedilir; yeniden segmentasyon veya doğrulanmış eşleme gerekir. Kaynak GLB ve üretim kodları değişmez.
- F02 yüzey bölge seçimi; yeni kapalı hacim yaratma veya ayrı GLB üretme F03'tür.

## Kanıt (2026-11-28)
- [9a8af8d](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/9a8af8d295a79ffdad7a4adf59cece9d2f35bf55) studio/f02/surface_selection.py: z-buffer, maske piksel oylaması, üçgen merkez komşuluk yaklaşık geodezik fırça, undo, JSON sidecar ve yanlış model reddi.
- Yerel aynı algoritma testinde gerçek F01 artefakt 15240210747 (chair 20.332, robot 39.276, seated_scene 26.108 üçgen); fırça sırasıyla 567/889/1017 yüz; görünür maske 1309/757/1163 yüz. 3/3 undo, sidecar kaydet/yükle, yanlış geometri reddi, mesh kimliği değişmez; öndeki/arkadaki üst üste iki üçgen testi geçti. Dört açılı gerçek görsel açılıp incelendi: manuel bölgeler yüzeye bağlı; sandalye fırçası sırt ve oturma sınırını aşabiliyor; bu semantik ayrıştırma kabulü değildir.
- [65e678b](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/65e678b513944041e48cdde51d193a75f287023a), [b55ef2b](https://github.com/marazali02012-wq/Forge-2.5D-Studio-LocalDream/commit/b55ef2b55f8cbdf2d8b3d1fcd86fd5c564728d43): gerçek SAM2.1 tiny CPU resmi ağırlıkları ile nokta maskesi, 3 farklı GLB ve altı panelli görsel, orijinal dosya hash, geri alma ve hatalı sidecar testi. CI sonucu henüz yok. Otomatik semantik, tüm açılarda tam kapsama, ayrıntı kontrolü, UI ve fiziksel cihaz kabulü yok.

Durum: F02 PARALEL DENEYSEL AKTİF; F01 açık; F03–F09 bekliyor. Ücretli servis yok.
