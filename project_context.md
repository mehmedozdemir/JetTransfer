# Mimarisi ve Proje Bağlamı (Project Context)

**JetTransfer**, işletmelerin farklı veritabanı sistemleri arasında yüksek hacimli (milyonlarca satır) veri transferini hızla ve güvenle gerçekleştirebilmesi için geliştirilmiştir. Python ve PyQt6 tabanlı masaüstü (desktop) uygulayışına sahiptir.

## 📁 Dizin Yapısı ve Görevleri

- **`main.py`**: Uygulamanın giriş noktası. Ana QMainWindow ve menü tanımlarını barındırır.
- **`ui/` (Kullanıcı Arayüzü)**: PyQt6 tabanlı görsel katman kodları burada yer alır. Örn: `connections_tab.py`, `transfers_tab.py`, `add_connection_dialog.py`, `wizard_dialog.py`.
- **`core/` (Çekirdek İş Mantığı)**: 
  - Veritabanı İletişimi: `mssql.py`, `oracle.py`, `postgres.py`, ve bunları soyutlayan `base.py`.
  - Aktarım Mantığı: `transfer_engine.py` (verileri kopyalama), `schema_mapper.py` (tablo ve sütun eşleme), `schema_validator.py` (tip doğrulama).
  - Güvenlik & Saklama: `local_db.py` (yerel SQLite entegrasyonu), `crypto.py` (şifrelerin ve bağlantı metinlerinin güvenli şifrelenmesi).

## 🚀 Proje Durumu / İş Mantığı
- **Phase 4 - Dinamik Şema Eşleme**: Kaynak ve hedef tabloların sütunlarının (isim, tip vb.) kesişimini alıp dinamik olarak eksik sütunları tolere eden bir veri aktarım mekanizması.
- Uygulama çalışırken veritabanı bağlantı detayları AES şifrelemesiyle `jettransfer_state.db` SQLite veritabanı üzerinde saklanır.
- UI engellenmelerini önlemek (Non-blocking UI), profesyonel ve modern (Catppuccin veya benzeri koyu odaklı) arayüz sunmak temel ilkelerdendir.
