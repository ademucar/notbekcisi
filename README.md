# Not Bekçisi

ESOGÜ (Eskişehir Osmangazi Üniversitesi) OBS'ye yeni not girildiğinde Telegram'dan haber veren küçük bir Python programı.

Program not sayfasını 5 dakikada bir kontrol eder. Bir not değişince Telegram'a şöyle bir mesaj gelir:

```
Yeni not girildi!

VERİ YAPILARI (A)
Ara Sınav 1: 75 (YAZILI %40)
Ortalama: 30
```

## Özellikler

- **Kısa bildirim:** Mesajda yalnızca değişen not yazar, tablonun tamamı gelmez.
- **Captcha'yı sen girersin:** Captcha resmi Telegram'dan sana gelir. Kodu yazarsın, program giriş yapar. Captcha otomatik çözülmez.
- **Oturumu açık tutar:** Not sayfası düzenli açıldığı için oturum hareketsizlikten kapanmaz. Kapanırsa ne kadar açık kaldığını yazar ve yeni captcha ister.
- **Telegram komutları:** `/durdur`, `/devam` ve `/durum` ile programı telefondan yönetebilirsin.
- **Sessiz saatler:** Gece oturum düşerse captcha göndermez. Sabah `/devam` yazana kadar bekler.
- **Sunucuda çalışabilir:** Bilgisayarın kapalıyken de çalışsın diye Oracle Cloud'un ücretsiz sunucusuna kurulum rehberi var ([SUNUCU.md](SUNUCU.md)).

## Nasıl çalışır?

1. Görünmez bir Chromium (Playwright) OBS giriş sayfasını açar, kullanıcı adını ve şifreni yazar.
2. Captcha resmini Telegram botu üzerinden sana gönderir ve cevabını bekler.
3. Giriş olunca not tablosunu okur ve `notlar.json`'a kaydeder.
4. 5 dakikada bir not sayfasını yeniden açar ve tabloyu kayıtla karşılaştırır. Fark varsa sana bildirir.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `main.py` | Ana döngü, Telegram komutları ve sessiz saatler. Programı bununla başlatırsın. |
| `obs.py` | OBS ile konuşan kısım: giriş, oturum kontrolü ve notları okuma. |
| `telegram_bot.py` | Telegram'a mesaj ve resim gönderir, cevap bekler. |
| `not_deposu.py` | Notları `notlar.json`'a kaydeder ve değişiklikleri bulur. |
| `ayarlar.py` | Bütün ayarlar: adresler, seçiciler, süreler. |
| `kesif.py` | Kurulum yardımcısı. OBS sayfalarının yapısını gösterir. |
| `notbekcisi.service` | Linux sunucuda sürekli çalıştırmak için systemd servisi. |
| `SUNUCU.md` | Oracle Cloud ücretsiz sunucuya adım adım kurulum. |
| `.env.ornek` | `.env` dosyası için şablon. |

## Kurulum

Python 3.10 veya daha yeni bir sürüm gerekir.

### 1. Paketler ve tarayıcı

```
pip install -r requirements.txt
playwright install chromium
```

> **Windows'ta kullanıcı adında Türkçe karakter (Ç, Ş, İ…) varsa** Chromium varsayılan klasörden açılmıyor.
> Bu yüzden `ayarlar.py` Windows'ta tarayıcıyı `C:\ms-playwright` klasöründe arar. Kurulumu da oraya yap:
> ```
> $env:PLAYWRIGHT_BROWSERS_PATH = "C:\ms-playwright"
> playwright install chromium
> ```

### 2. Telegram botu

1. Telegram'da **@BotFather**'a `/newbot` yaz ve botuna bir ad ver. BotFather sana bir **token** verir.
2. `.env.ornek` dosyasını kopyala ve adını `.env` yap. Token'ı `TELEGRAM_TOKEN=` satırına yaz.
3. Kendi botuna herhangi bir mesaj at.
4. `python telegram_bot.py` komutunu çalıştır. Ekrana çıkan sayıyı `TELEGRAM_CHAT_ID=` satırına yaz.

### 3. OBS bilgileri

`.env` dosyasında `OBS_KULLANICI` ve `OBS_SIFRE` satırlarını doldur.

### 4. (Gerekirse) Sayfa yapısını kontrol et

`ayarlar.py`'deki seçiciler ESOGÜ OBS'ye göre hazır. OBS'nin görünümü değişirse şu komutla yeni yapıyı görebilirsin:

```
python kesif.py
```

- Komut görünür bir tarayıcı açar ve giriş sayfasındaki öğeleri listeler. Her seçici tam **1** öğe bulmalı.
- Açılan pencerede elle giriş yap ve not sayfana git. Program girişi kendisi anlar ve not sayfasındaki tabloları listeler.
- Çıktının tamamı `kesif_cikti.txt` dosyasına da yazılır.

### 5. Çalıştır

```
python main.py
```

Telegram'a önce "Not Bekçisi başladı" mesajı, ardından captcha resmi gelir. Kodu yazınca giriş yapılır. İlk kontrolde mevcut notlar kaydedilir. Bundan sonra yalnızca değişiklikler bildirilir.

Durdurmak için terminalde `Ctrl+C` tuşlarına bas.

## Telegram komutları

Telegram'da `/` yazınca komut listesi açılır.

| Komut | Ne yapar |
|---|---|
| `/durdur` | Not kontrolünü durdurur. Captcha da istemez. |
| `/devam` | Kaldığı yerden devam eder. Oturum o arada kapandıysa captcha ister, açıksa "yeni not yok" der. |
| `/durum` | Son kontrolün zamanını ve sonucunu, oturumun ne zamandır açık olduğunu ve sessiz saatleri yazar. |

## Sessiz saatler

Varsayılan aralık 00:00–08:00. `ayarlar.py`'deki `SESSIZ_BASLANGIC_SAATI` ve `SESSIZ_BITIS_SAATI` ile değiştirebilirsin.

- **Oturum bu saatlerde düşerse:** Program captcha göndermez ve kendini durdurur. Sabah da kendiliğinden sormaz. Uyanınca `/devam` yazarsın, captcha o zaman gelir.
- **Oturum açık kaldığı sürece:** Not bildirimleri gece de gelir.

## Sunucuda çalıştırma

Bilgisayarın kapalıyken de çalışması için Oracle Cloud Always Free sunucusuna kurulum adımları [SUNUCU.md](SUNUCU.md) dosyasında. Program orada bir systemd servisi olarak çalışır ve çökerse kendiliğinden yeniden başlar.

## Önemli notlar

- **`.env` dosyasını kimseyle paylaşma.** İçinde OBS şifren ve bot token'ın var. `.gitignore` sayesinde bu dosya git'e eklenmez.
- **Kontrol aralığı 5 dakika** (`KONTROL_ARALIGI_DK`). Bu aralık için üniversitenin Bilgi İşlem birimi onay verdi. Daha aşağı indirme, üniversitenin sunucusunu gereksiz yere yormuş olursun.
- **Arka arkaya en fazla 3 giriş denenir.** Böylece hesap kilitlenmez.
- **Programın aynı anda iki kopyasını çalıştırma.** Telegram cevaplarını birbirinden kaparlar, OBS oturumları da birbirini atabilir.
- Bu proje kişisel kullanım için yazıldı. Üniversiteyle resmi bir bağlantısı yoktur.

## Sorun giderme

- **Doğru kodu yazmana rağmen "kod yanlış olabilir" mesajı geliyor:** `SECICI_CIKIS_BAGLANTISI` sayfada bulunamıyor olabilir. `kesif.py` ile kontrol et.
- **"Not tablosunda satır bulunamadı" hatası:** `SECICI_NOT_SATIRLARI` yanlış olabilir. OBS'nin görünümü değişmiş olabilir.
- **Ayrıntılı kayıtlar:** `notbekcisi.log` dosyasında.
