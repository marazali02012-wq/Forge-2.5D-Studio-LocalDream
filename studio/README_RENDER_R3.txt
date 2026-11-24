Forge Studio R3 — renk ve önizleme onarımı

R2 üzerinden değişiklikler: GLB COLOR_0 (VEC3/VEC4, float veya normalized unsigned byte/short), doğrusal renk/ekran sRGB dönüşümü, iki yönlü temel aydınlatma, non-uniform ölçek için normal dönüşümü, CPU piksel bütçesi (yaklaşık 480 bin piksel, 1024 kenar, 1.5 DPR), CPU UV wrap seçenekleri, dar kamera paneli satır kaydırma.

Test: test_render_r3.py, test_visual_r2.py. CPU: renk/doku örnekleri, görünüm geçişi, GLB byte-identical dışa aktarma, 5 ekran boyutu geçti. WebGL2 ortamda açılamadı; GPU testi atlandı. Android performansı ölçülmedi. Metal/roughness, normal map, HDR ve alpha BLEND tam PBR önizleme kapsamında değildir. CPU doku örnekleme en yakın piksel yöntemidir. Üretim/AI sunucu motorlarına bu sürümde değişiklik yapılmadı.
