# Forge R70.34 bulut seçenekleri

| Altyapı | Kapasite ve durum |
| --- | --- |
| Render Free | 0,1 CPU ve 512 MB RAM. Forge editörü statik olarak yayında. Ölçülen TripoSR işlemi yaklaşık 3,8 GiB tepe belleğe ulaştı. |
| Hugging Face Docker Space | CPU Basic 2 CPU, 16 GB RAM, kalıcı olmayan 50 GB disk. Güncel belgelerde yeni Docker veya Gradio Space oluşturmak için ücretli plan gerekiyor. ZeroGPU ayrı Gradio çalışma ortamı ve kotaya bağlı. |
| Oracle Cloud Ampere A1 | Güncel Always Free kotası 2 OCPU ve 12 GB eşdeğeri. ARM işlemci. Uygun hesap, bölgesel kapasite ve ARM bağımlılık testi gerekiyor. |
| Google Colab | Etkileşimli notebook testi. Ücretsiz kaynaklar ve çalışma süreleri değişken. Web hizmeti için kalıcı sunucu olarak seçilmedi. |
| Kaggle Notebooks | CPU/GPU notebook testleri için kullanılabilir. Oturum süresi ve GPU kotası var. |
| Ayrı kullanıcı makinesi | Kullanıcının yönettiği bir makinede Docker CPU paketini çalıştırmak mümkün. Canlı erişim için HTTPS uç noktası ve erişim anahtarı gerekir. |

Hugging Face giriş isteği CloudFront tarafından 403 ile karşılandı. Ekranda yanlış parola, e-posta doğrulama veya hesap yetkisi hatası görünmedi. AWS belgelerine göre aynı 403 kodu dağıtımın arkasındaki uygulamadan veya WAF'tan gelebilir. Kesin neden için sağlayıcı günlükleri gerekir. Yeni Docker Space plan şartı bağımsız bir uygunluk koşuludur.

Kaynaklar

- [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-overview)
- [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/en/spaces-zerogpu)
- [Render Compute Plans](https://render.com/docs/compute-plans)
- [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Colab SSS](https://research.google.com/colaboratory/faq.html)
- [Kaggle notebook çalışma süreleri](https://www.kaggle.com/product-feedback/302908)
- [CloudFront 403](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/http-403-permission-denied.html)

## Karşılaştırılan motorlar

TripoSR bu sürümün CPU üretim yoludur. MIT lisanslı tek görsel motoru kullanılır. Stable Fast 3D doğrudan UV açma ve aydınlatma ayrıştırma sunuyor. Depodaki R58 denemesinde CPU ONNX yüklemesi çalışmış, gerçek çıktı alınamamıştır. Hunyuan3D-2 belgeleri şekil ve doku hattı için 16 GB GPU belleği belirtir. TRELLIS.2 belgeleri en az 24 GB NVIDIA GPU belleği belirtir. Bu altyapılarla bu sürümde eş girdili görsel kıyas yapılmadı.

- [TripoSR](https://github.com/VAST-AI-Research/TripoSR)
- [Stable Fast 3D](https://github.com/Stability-AI/stable-fast-3d)
- [Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
