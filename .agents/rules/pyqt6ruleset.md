---
trigger: always_on
---

# 🏛️ Antigravity Desktop App: Qt6 & Python Engineering Standards

Bu döküman, Antigravity ekosistemindeki Python tabanlı masaüstü uygulamaları için mimari, kodlama ve UI/UX standartlarını tanımlar. Amacımız; yüksek performanslı, estetik ve sürdürülebilir bir "Enterprise-Grade" masaüstü deneyimi sunmaktır.

---

## 🏗️ 1. Mimari Prensipler (The Core Engine)

### 1.1. Model-View-ViewModel (MVVM) Adaptasyonu
- **Decoupling:** UI kodları (View), iş mantığından (Model) tamamen izole edilmelidir. Aradaki iletişim `Signals & Slots` mekanizması veya bir `ViewModel` katmanı üzerinden yönetilmelidir.
- **State Management:** Uygulamanın durumu (state), merkezi bir `Store` veya `State Manager` içinde tutulmalı; UI bileşenleri bu duruma "abone" (subscribe) olmalıdır.

### 1.2. Resource & Asset Management
- **Qt Resource System (.qrc):** Tüm ikonlar, fontlar ve stil dosyaları `.qrc` üzerinden binary olarak paketlenmelidir. Dosya yolları "hard-coded" olarak verilmemelidir.
- **Lazy Loading:** Uygulama açılış hızını optimize etmek için ağır bileşenler ve veriler sadece ihtiyaç duyulduğunda (on-demand) yüklenmelidir.

---

## 🐍 2. Pythonic Qt Standartları

### 2.1. Kodlama Standartları
- **PEP 8+:** Standart Python yazım kurallarına ek olarak, Qt bileşen isimlendirmelerinde "CamelCase" (Qt geleneği) yerine, Pythonik bir yaklaşım olan `snake_case` fonksiyonlar ve `PascalCase` sınıf isimleri tercih edilmelidir.
- **Type Hinting:** Tüm sinyal tanımlamaları ve metod imzaları `typing` modülü ile dökümante edilmelidir.
  - *Örn:* `data_received = Signal(dict)`

### 2.2. Concurrency & Threading
- **Non-Blocking UI:** Uzun süren tüm işlemler (I/O, Network, Heavy Calc) `QThread` veya `QRunnable` kullanılarak ana thread'den (GUI Thread) ayrılmalıdır.
- **Thread Safety:** İş parçacıkları arasındaki veri iletimi sadece `Signals` üzerinden yapılmalıdır; paylaşılan bellek alanlarına (shared memory) doğrudan erişim yasaktır.

---

## ✨ 3. Modern UI/UX Standartları

### 3.1. Visual Hierarchy & Layouts
- **Dynamic Resizing:** Asla sabit (`fixed`) boyutlu pencereler kullanılmamalıdır. Tüm arayüz `QLayout` (VBox, HBox, Grid) sistemine dayanmalı ve farklı ekran çözünürlüklerine/DPI ayarlarına uyum sağlamalıdır.
- **Negative Space (Beyaz Boşluk):** Arayüz elemanları arasında nefes alacak alanlar bırakılmalıdır. Standart `margin` ve `spacing` değerleri (örn: 8px, 16px, 24px) bir `Theme` dosyasında sabitlenmelidir.

### 3.2. Tasarım Dili (Design System)
- **Styling:** Görsel özelleştirmeler kod içinde değil, merkezi bir **QSS (Qt Style Sheets)** dosyasında veya modern bir `Theme Engine` üzerinden yapılmalıdır.
- **Color Theory:**
  - `Primary`: Marka rengi.
  - `Surface`: Arka plan ve panel renkleri.
  - `Error/Success`: Durum renkleri.
- **Dark Mode Support:** Uygulama, işletim sistemi ayarlarına göre dinamik olarak Dark/Light tema geçişi yapabilmelidir.

### 3.3. Etkileşim ve Geri Bildirim
- **Micro-interactions:** Buton üzerine gelme (hover), tıklama ve geçiş efektleri kullanıcıya sistemin canlı olduğunu hissettirmelidir.
- **Loading States:** Kullanıcı, süren bir işlem hakkında her zaman bilgilendirilmelidir (ProgressBar, Spinner, Skeleton Screen).

---

## ♿ 4. Erişilebilirlik ve Yerelleştirme (i18n)

- **Accessibility (a11y):** Tüm interaktif öğelerin `AccessibleName` ve `AccessibleDescription` özellikleri tanımlanmalıdır. Ekran okuyucularla tam uyum hedeflenmelidir.
- **Keyboard Navigation:** Uygulama sadece klavye (`Tab`, `Enter`, `Esc`) kullanılarak tamamen kontrol edilebilmelidir. `Focus Policy` doğru yapılandırılmalıdır.
- **Internationalization (i18n):** Tüm metinler `self.tr()` sarmalayıcısı içinde yazılmalı ve `.ts` / `.qm` dosyaları üzerinden çeviriye hazır tutulmalıdır.

---

## 🧪 5. Test ve Kalite Süreçleri

- **QtTest Framework:** UI etkileşimleri (buton tıklamaları, veri girişleri) `QTest` modülü ile simüle edilerek test edilmelidir.
- **Headless Testing:** CI/CD süreçlerinde GUI olmadan testlerin koşulabilmesi için gerekli konfigürasyon (xvfb vb.) sağlanmalıdır.
- **Memory Leak Check:** Python'ın `Garbage Collection` mekanizmasına güvenilmemeli; `Parent-Child` ilişkisi kurularak (Qt Object Tree) nesne ömürleri manuel kontrol edilmelidir.

---

## 📦 6. Dağıtım (Distribution)

- **Bundling:** Uygulama `PyInstaller` veya `Nuitka` kullanılarak, son kullanıcının Python kurmasına gerek kalmadan çalışabileceği tek bir executable (.exe/.app) haline getirilmelidir.
- **Auto-Update:** Uygulama, kritik güncellemeleri kontrol eden ve kullanıcıya sunan bir mekanizmaya sahip olmalıdır.