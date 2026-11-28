# Forge Studio — Genel amaçlı 3D üretim kapsamı

Kullanıcı düzeltmesi: Forge, şövalye/robot/ayakta duran insan gibi şablonlara bağlı bir karakter üreticisi değildir. Kullanıcı herhangi bir görsel yükleyebilmeli; model görsele uyarlanmalıdır. Örnek: masada çay içen insan; insan, masa, sandalye, bardak ayrı gerçek 3D nesneler olarak düzenlenebilmeli. Örnek sınıflar zorunlu katalog değildir.

## Kabul koşulları
- Genel nesne ve sahne üretimi, semantik parça ayrıştırma; her ayrılmış parça kendi gerçek üç boyutlu geometrisine sahip olmalı. Sadece 2D maske, kopuk üçgen grubu, isimlendirme veya düz kart yeterli değildir.
- Parça geometrisi görünmeyen bölgelerde mümkün olduğunca tamamlanmalı; tek görüntüden görünmeyen yüzeylerin doğruluğu garanti edilemez.
- Her parça ayrı seçilebilmeli, taşınabilmeli, döndürülebilmeli, düzenlenebilmeli; bütün sahne ve ayrı parçalar GLB olarak dışa aktarılabilmeli. Sahne ilişkileri ve dokular korunmalı.
- Statik nesne üretimi iskelet şartına bağlı olmamalı. Rig ve animasyon isteğe bağlı, nesneye/anatomiye ve poza uygun olmalı. Mevcut 26 kemik sistemi yalnız uygun insansı modeller için korunur; genel üretim yolu değildir.
- Yeni ve daha önce görülmemiş görsellerle test: çok nesneli sahne, tek nesne ve alt parçaları, oturan insan, hayvan ve mekanik nesne. Bunlar test örnekleri, şablon değil. Gerçek GLB, geometri, materyal, parça seçimi ve görsel 360 derece denetim gerekir.
- Çalışan TripoSR CPU üretimi ve mevcut editör korunur. Ayrı deneysel yol, kanıtlanmadan varsayılan olmaz. Ücretli altyapı kullanıcı onayı olmadan açılmaz.

## Aday teknolojiler (entegrasyon doğrulanmadı)
- https://github.com/wgsxm/PartCrafter — tek görüntüden çok parçalı nesne ve sahne, resmi kurulum en az 8 GB CUDA VRAM ister; otomatik parça sayısı seçimi ayrıca model gerektirebilir.
- https://github.com/VAST-AI-Research/HoloPart — gerçek 3D modelden semantik parçaları ve kapalı/gizli geometrileri tamamlama.
- https://github.com/facebookresearch/sam-3d-objects — tek fotoğraftan nesne geometrisi, doku ve sahne yerleşimi.
- CPU alternatifi: genel görüntü segmentasyonu + her maske için bağımsız TripoSR çıkarımı. Ölçek/konum ve örtüşen parçaların tamamlanması ayrıca doğrulanmalıdır; Tripo eşdeğeri olduğu varsayılmaz.

Bu dosya kapsam kaydıdır; özelliklerin uygulanmış veya test edilmiş olduğunu göstermez.
