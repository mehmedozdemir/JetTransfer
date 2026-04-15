# JetTransfer - Enterprise Data Migration Engine

JetTransfer, Python ve PyQt6 tabanlı, işletmelerin ihtiyaç duyduğu büyük hacimli veri transfer operasyonlarını şema farkındalıklı (schema-aware) yeteneklerle gerçekleştiren profesyonel bir masaüstü uygulamasıdır.

## Agent / AI Kurulum ve Dosyaları

Bu repo, proje için özel olarak optimize edilmiş AI/Agent kullanım belgelerini içerir. Geliştirme sürecinin daha tutarlı ve yüksek standartlı olması için lütfen bu belgeleri referans alın:

- [**project_context.md**](./project_context.md): Öncelikli olarak okunması gereken, mimari yapıyı ve proje durumunu (örn. Phase 4 Dinamik Şema) aktaran genel özet dosyası.
- [**agent_rules.md**](./agent_rules.md): Katı kodlama standartlarını (Python, async/QThread tabanlı UI, PyQt6) ve AES şifreleme/güvenlik prensiplerini içerir.
- [**agent_skills.md**](./agent_skills.md): Mevcut kod tabanındaki performans sorunlarını (Batch/Bulk Insert) çözmek ve UI kilitlenmelerini aşmak adına aracıya yönlendirme sağlayan skill seti listesidir.

## Özellikler

1. **Çoklu Veritabanı (Multi-Database) Desteği**: PostgreSQL, Oracle ve MS SQL Server gibi sistemler arasında verileri sorunsuz taşıyabilir.
2. **Dinamik Şema Eşleştirme (Phase 4)**: Tablolar sadece birebir aynı olmak zorunda değildir. Kesişen (intersecting) sütunları zekice bularak veri çöküşünü önler.
3. **Senkron Olmayan Non-Blocking UI**: Uzun süren milyonlarca satır veri indirme işlemi ve hedef sisteme insert işlemi sırasında UI kesinlikle kitlenmez (QThread tabanlı mimari).
4. **Yerel Korumalı Depolama**: Veritabanı erişim şifrelerini metin bloklarında (`plain-text`) saklamaz; aes tabanlı encryption ile sqlite backendine kaydeder (`jettransfer_state.db`).

---
> *Bu proje "JetTransfer Enterprise" standartlarında, performansı önceleyen, estetik olarak Catppuccin paletleri kullanılan bir platformdur.*
