# Agent Kuralları (Agent Rules)

Bu proje üzerinde çalışırken yapay zeka aracısının uyması gereken kesin kurallar şunlardır:

## 1. Kod Standartları, Stili ve SOLID Prensipleri
- **Single Responsibility Principle (SRP)**: Her sınıfın veya modülün tek bir sorumluluğu olmalıdır. UI (`ui/`) bileşenleri yalnızca gösterimden sorumlu olmalı; veritabanı bağlantısı veya veri aktarımı iş mantıkları kesinlikle UI içine (örneğin buton tıklama fonksiyonuna) gömülmemelidir. Bu işler `core/` modülleri tarafından yönetilmelidir.
- **Open/Closed Principle (OCP)**: Sınıflar, genişlemeye açık ancak değişime kapalı olmalıdır. Yeni bir veritabanı sürücüsü ekleneceğinde (`mysql.py` gibi), var olan `base.py` interfaceleri değiştirilmemeli; `BaseDatabase` sınıfından miras alınarak yeni sınıflar yaratılmalıdır.
- **Liskov Substitution Principle (LSP)**: `BaseDatabase` (veya ilgili core soyutlamalarından) türeyen tüm alt sınıflar (`mssql.py`, `oracle.py` vs.), ana sınıfın yerine kullanılsalar bile sistem patlamamalıdır. Dönüş tipleri (return types) ve bağımsız değişkenler istikrarlı olmalıdır. 
- **Interface Segregation Principle (ISP)**: Arayüzler (interfaceler) özelleşmiş olmalı, kullanılmayan metodlar implement edilmeye zorlanmamalıdır. Aktarım veya doğrulama araçları, yalnızca ihtiyaç duyulan temel metodları barındırmak üzere ayrıştırılmalıdır.
- **Dependency Inversion Principle (DIP)**: Üst seviye modüller, alt seviye modüllere (örneğin UI'ın psycopg2'ye doğrudan bağlanması) bağımlı olmamalıdır. İkisi de soyutlamalara (abstraction) bağımlı olmalıdır (Örn: Veritabanı arayüzlerini ve modellerini kullanan Dependency Injection yapıları).
- **Dil ve Framework**: Projede **Python 3** ve **PyQt6** kullanılmaktadır. Tüm arayüz kodlarında güncel PyQt6 yapıları (QThread, QStackedWidget gibi) temel alınmalıdır.
- **Tip İpuçları (Type Hinting)**: Mümkün olduğunca Python 'typing' modülü ile imzalar belirginleştirilmeli, hata payı düşürülmelidir.
- **Modülerlik**: Her şey `main.py` içerisine yığılmamalıdır. Yeni arayüz bileşenleri `ui/`, veritabanı sürücüleri veya motor güncellemeleri `core/` altında yapılmalıdır.

## 2. Arayüz (UI) ve Performans Kuralları
- **Thread Yönetimi (Asenkron)**: Milyonlarca satır taşıyabilen uzun süren veritabanı sorguları ve aktarım işlemleri KESİNLİKLE ana iş parçacığını (Main Thread) kilitlememelidir. Bunun yerine **QThread** veya **QRunnable** kullanılarak arka planda (worker thread) çalıştırılmalıdır.
- **Erişilebilirlik ve İletişim**: Thread'lerden (Worker'dan) gelen mesaj ve güncellemeler, bir **Signal (pyqtSignal)** mekanizmasıyla UI'a gönderilmelidir. 
- **Veri Gösterimi**: Ekran kitlenmelerinin önüne geçmek için tableview gibi bileşenlere binlerce satır aynı anda yüklenmemelidir (Pagination veya lazy loading).
- **Tasarım:** Arayüz değişikliklerinde proje için temel alınan Catppuccin, Dark Mode modern tasarım stillerine sadık kalınmalıdır. Modern yazı tipleri, rounded-corner (yuvarlak kenarlar) elementleri CSS içinden (`QMainWindow { background-color: #11111b; ...}`) ayarlanmalıdır.

## 3. Güvenlik ve Veri Kuralları
- Veritabanı şifreleri, AES anahtarları veya herhangi bir hassas veri `*.py` dosyaları içine sabit metin (hardcoded) olarak KESİNLİKLE gömülmemelidir. İşlemler `core/crypto.py` üzerinden yapılmalı ve bağlantı metinleri `jettransfer_state.db` üstünden çekilmelidir.
- Yanlış veritabanı bağlantı hataları (örneğin ODBC bulunamadı, şifre yanlış) durumunda, trace-back direkt kullanıcıya gösterilmektense, anlaşılabilir `QMessageBox` uyarılarına çevrilmelidir.
- Veri silme veya değiştirme (DML) durumlarında (ör. tablonun içini boşaltma vs.) KESİNLİKLE transaction (commit/rollback) yapıları kurulmalı ve bozuk veriler geri döndürülebilmelidir.

## 4. Geliştirme Süreci
- Eklenen yeni bir özelliğin performansı etkileyip etkilemediği gözlenmelidir.
- Yalnızca ilgili .md dosyalarındaki talimatlara değil; aynı zamanda `/core/` altındaki base abstraction sınıflarına (ö. `base.py`) bakılarak implementasyonlar geliştirilmelidir.
- Her yeni özellik için branch açılmalı ve bu branch üzerinden geliştirme yapılmalıdır. Sonra code review yapılmalı ve onaylandıktan sonra main branch'e merge edilmelidir.
