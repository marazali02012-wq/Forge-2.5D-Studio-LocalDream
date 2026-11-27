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
