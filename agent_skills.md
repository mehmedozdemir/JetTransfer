# Agent Yetenekleri (Agent Skills)

Bu dosya, projenin özgün altyapısı temel alınarak ajanın problemleri analiz ederken veya yeni geliştirmeler eklerken kullanması gereken yetenekler setini (skills) listeler.

## Yetenek 1: Bağlantı Hatalarını Giderme
**Bağlam**: Kullanıcı bir veritabanı bağlantısı eklediğinde (ODBC, Oracle Client, psycopg2 vs.) eksik driver kaynaklı sorunlar olabilir.
- **Kullanımı**: Hata fırlatıldığı noktada (`core/mssql.py` veya diğerleri), driver'ın yüklü olup olmadığı log'a veya `QMessageBox`'a gönderilerek kullanıcı bilgilendirilir.
- **Güvenlik Çözümü**: Eğer `crypto.py` üzerinden geçersiz bir aes-key çözme (decryption error) uyarısıyla karşılaşılırsa, mevcut key ile `jettransfer_state.db` arasında uyumsuzluk olduğu teşhisini koyarak kullanıcıya 'şifreleme anahtarının geçersiz olduğunu' bildir.

## Yetenek 2: UI Kilitlenmelerini Giderme Konsültasyonu (QThread Adaptasyonu)
**Bağlam**: Bir Query çok uzun sürdüğünde masaüstü kilitleniyorsa veya tepki vermiyorsa.
- **Kullanımı**: İlgili uzun süren döngüyü veya metodu bulup `QRunnable` veya `QThread` içine taşı. `progress = pyqtSignal(int)` oluşturup döngüdeki ilerlemeyi(`.emit(değer)`) ana sayfadaki QProgressBar'a (`self.progress_bar.setValue`) ata.

## Yetenek 3: Şema Farklılıkları Karşılaştırması ve Aktarım Modeli
**Bağlam**: Veritabanları arası tablo transferinde (Postgres -> MSSQL vs.), hedef tabloda farklı sütunlar var ise.
- **Kullanımı**: Phase 4 kapsamında, `schema_mapper.py` içindeki algoritmaları incele. Eğer iki tablo eşit değilse (sütun eksiği vb.), **sadece eşleşen/kesişen sütunlar** üzerinden (intersect) SQL `INSERT` dizgisi oluştur. Eksik sütunları pas geç ve hata üretme. Bu veri uyuşmazlığına karşı esneklik sağlar.

## Yetenek 4: Toplu Veri (Bulk Insert) İşlemi Geliştirme
**Bağlam**: Satır satır (row-by-row) `INSERT` yapmak çok yavaştır. Performansı arttırmak gerekir.
- **Kullanımı**: `transfer_engine.py` içinde `cursor.executemany()` veya DBMS'e özgü bulk tool'ları kullanılarak verilerin, ayarlanmış bir `BATCH_SIZE` (örn: 10.000 satır) limitine kadar RAM'de biriktirilip sonrasında yığıt şeklinde (batch insert) yazılmasını sağla. Milyonlarca satır başka türlü verimli taşınamaz.

## Yetenek 5: Arayüz Stilleme ve Theme Check (CSS)
**Bağlam**: Yeni bir buton, liste veya input alanı eklenince uygulamanın temel koyu (Catppuccin vari) renk temasından sırıtabilir.
- **Kullanımı**: `main.py` içerisindeki `.setStyleSheet()` deklarasyonuna git ve kurallara uygun (`background-color: #313244; color: #cdd6f4;` vb.) şekilde genel stil bileşenini yeni Qt Widget'ına uygula. Gerekirse Widget için özelleştirilmiş yeni bir `ObjectName` tanımla.
