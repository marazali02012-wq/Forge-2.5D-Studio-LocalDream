# Forge 2.5D Studio — V14 WebGL2 geliştirme

Bu dal **gelistirme/webgl2-v14** dalıdır; ana dalı değiştirmeden 3D GPU çizimi, UV kaplama, animasyon ve dışa aktarma geliştirilmektedir.

## Dosyalar

- `Forge_25D_V14_WebGL2.html`: Çevrimdışı çalışan tek dosyalık uygulama.
- `test/check_webgl.py`: CPU/WebGL2 piksel karşılaştırması, 40 sprite + GLB testi, bağlam kaybında CPU'ya dönüş ve mobil ekran/sekme testleri.
- `test-sonuclari/olcumler.json`: Otomatik test sonuçları.
- `test-sonuclari/mobil-ekranlar.json`: Yeni mobil test başarılı olduğunda üretilecek.
- `.github/workflows/webgl2-test.yml`: Testleri GitHub Actions üzerinden çalıştırır.

## Doğrulama sınırı

GitHub Actions testleri **SwiftShader (yazılım WebGL2)** kullanır. Bunlar Mali-G52 üzerinde donanımsal GPU hızlandırmasının doğrulandığı anlamına gelmez. Gerçek Realme C55 testi ayrıca gereklidir.

## Telefon testi

1. `Forge_25D_V14_WebGL2.html` dosyasını telefona indir ve tarayıcıda aç.
2. **Ayarlar → 3D çizim motoru** bölümünde önce `Otomatik`, ardından `GPU` ve `CPU` seçeneklerini ayrı ayrı dene.
3. PNG karakteri yükle, **3D Model → Resimden 3D oluştur**. Modelin yüz/kıyafet dokusunun görünüp görünmediğini incele.
4. Modeli döndür, yürüme/saldırı animasyonlarını çalıştır, **40 sprite + GLB ZIP** çıkar.
5. Ölçüm ekranından çizim yolu, CPU/GPU kare süreleri ve sürücü bilgisini kontrol et. Çıktıların içindeki GLB ve PNG'leri yeniden aç.

**Kabul koşulu:** GLB kaplaması kaybolmayacak, 40 sprite sayfası bozuk olmayacak, GPU başarısız olduğunda CPU yolu çalışacak. Gerçek telefon testi yapılana kadar performans artışı iddiası kesin değildir.

## Kapsam dışı

Local Dream'in gerçek yapay zekâ görsel üretimi ayrı model dosyaları gerektirir; WebGL2 3D çizimi bunun yerine geçmez.
