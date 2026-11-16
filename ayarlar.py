"""
ayarlar.py - Programın bütün ayarları tek yerde.

İki tür ayar var:
1) Gizli bilgiler (OBS şifresi, Telegram token): Koda yazılmaz, .env dosyasından okunur.
2) Sitenin yapısına bağlı bilgiler (adresler, seçiciler): Gizli değil, burada durur.
   OBS'nin görünümü değişirse yalnızca bu dosyayı düzenlemen yeter.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJE_KLASORU = Path(__file__).resolve().parent
load_dotenv(PROJE_KLASORU / ".env")

# Playwright'ın tarayıcıları arayacağı klasör. Windows kullanıcı klasörünün adında
# Türkçe karakter (Ç, Ş, İ...) varsa Chromium oradan açılamıyor ("yan yana yapılandırması
# doğru değil" hatası). Bu yüzden tarayıcıları Türkçe karakter içermeyen bir klasörde tutuyoruz.
# Bu satır, program tarayıcıyı başlatmadan önce çalışır (main.py ve kesif.py önce ayarlar'ı içe aktarır).
# Yalnızca Windows'ta gerekli; Linux sunucuda Playwright kendi varsayılan klasörünü kullanır.
if os.name == "nt":
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", r"C:\ms-playwright")

# ---------------------------------------------------------------------------
# 1) Gizli bilgiler (.env dosyasından)
# ---------------------------------------------------------------------------
OBS_KULLANICI = os.getenv("OBS_KULLANICI", "")
OBS_SIFRE = os.getenv("OBS_SIFRE", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# 2) Adresler
# ---------------------------------------------------------------------------
GIRIS_URL = "https://ogubs1.ogu.edu.tr/giris.aspx"

# Giriş yaptıktan sonra notlarını gördüğün sayfanın adresi.
# kesif.py çalıştırınca ekrana yazar; oradan kopyalayıp buraya yapıştır.
NOT_SAYFASI_URL = "https://ogubs1.ogu.edu.tr/SinavSonuc.aspx"

# Notlar sayfanın içindeki bir çerçevede (iframe) duruyorsa, o çerçevenin
# adresinden ayırt edici bir parça (örn. "NotListesi.aspx"). Çerçeve yoksa boş bırak.
NOT_CERCEVE_URL_PARCASI = ""

# ---------------------------------------------------------------------------
# 3) Seçiciler
# ---------------------------------------------------------------------------
# Seçici (selector): Sayfadaki bir öğeyi (kutu, buton, resim) tarif eden ifade.
#   "#txtSifre"                -> id'si txtSifre olan öğe
#   'input[type="password"]'   -> şifre kutusu
#   "#gvNotlar tr"             -> id'si gvNotlar olan tablonun satırları
# Değerler kesif.py çıktısından (giris.aspx) alındı. Hepsi id'li, çünkü id'ler en az değişen şeydir.
SECICI_KULLANICI = "#txtKulAd"
SECICI_SIFRE = "#txtpwd"
# Resmin adresi her seferinde rastgele (örn. ../resim/rn3jcv0zkud.png), id'si ise sabit.
SECICI_CAPTCHA_RESIM = "#kappi2"
SECICI_CAPTCHA_KUTU = "#txtKappa"
SECICI_GIRIS_BUTONU = "#btnLogin"

# Yalnızca giriş yapılmışken görünen bir öğe. İçeride olup olmadığımızı buna bakarak anlarız.
# Not sayfasının üstündeki "Çıkış" butonu.
SECICI_CIKIS_BAGLANTISI = "#btnCikis"

# Not tablosundaki satırlar. Tablonun id'si gvSinavSonuc. Her sınav hücresinin içinde
# küçük bir tablo daha var ("YAZILI (%30): 75" gibi); "#gvSinavSonuc tr" yazsaydık o iç
# tabloların satırları da gelirdi. "> tbody > tr" yalnızca dış tablonun kendi satırlarını,
# yani ders başına bir satır alır. İç tablodaki notlar yine o satırın hücre yazısında görünür.
SECICI_NOT_SATIRLARI = "#gvSinavSonuc > tbody > tr"

# Bir satırı tanımlayan ilk kaç sütun. Burada: DERS KODU ve DERS -> 2.
# Bu sütunlar değişmez; geri kalan sütunlar (notlar) değişince bildirim gelir.
ANAHTAR_SUTUN_SAYISI = 2

# Not tablosunun sütun adları, soldan sağa (OBS'deki başlık satırına göre). Bildirim
# mesajında "Ara Sınav 1: 90" gibi yazmak için kullanılır. OBS'deki "NOT" sütunu, girilen
# notların ağırlıklı toplamı (örn. vize 90, %40 -> 36); mesajda "Ortalama" diye görünür.
SUTUN_ADLARI = [
    "Ders Kodu", "Ders", "Ara Sınav 1", "Ara Sınav 2", "Final",
    "Bütünleme", "Ek Sınavlar", "Ortalama", "Harf Notu",
]

# ---------------------------------------------------------------------------
# 4) Zamanlama
# ---------------------------------------------------------------------------
KONTROL_ARALIGI_DK = 5         # Bilgi İşlem 5 dk'ya onay verdi. Daha aşağı indirme (sunucularını yormayalım).
HATA_SONRASI_BEKLEME_DK = 2    # Bağlantı hatasında kısa bekle ki oturum süresi dolmasın.
CAPTCHA_CEVAP_BEKLEME_DK = 30  # Captcha'ya bu süre içinde cevap gelmezse vazgeçilir.
GIRIS_TEKRAR_BEKLEME_DK = 60   # Giriş olmazsa tekrar sormadan önce beklenen süre.
MAKS_GIRIS_DENEMESI = 3        # Arka arkaya en fazla bu kadar deneme (hesap kilitlenmesin diye).

# Sessiz saatler: Bu saatler arasında oturum düşerse captcha istenmez; program kendini durdurur
# ve sen Telegram'dan /devam yazana kadar bekler (bitiş saatinde de kendiliğinden sormaz).
# Not bildirimleri bu saatlerde de gelir. Gece yarısını aşan aralık da olur (örn. 23 ve 7).
# Sessiz saati kapatmak için ikisini aynı sayı yap (örn. 0 ve 0).
SESSIZ_BASLANGIC_SAATI = 0     # 00:00
SESSIZ_BITIS_SAATI = 8         # 08:00

# ---------------------------------------------------------------------------
# 5) Dosyalar
# ---------------------------------------------------------------------------
NOT_DOSYASI = PROJE_KLASORU / "notlar.json"
LOG_DOSYASI = PROJE_KLASORU / "notbekcisi.log"


def eksikleri_kontrol_et() -> None:
    """Program başlamadan önce zorunlu ayarların dolu olduğundan emin olur."""
    zorunlular = {
        "OBS_KULLANICI (.env)": OBS_KULLANICI,
        "OBS_SIFRE (.env)": OBS_SIFRE,
        "TELEGRAM_TOKEN (.env)": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID (.env)": TELEGRAM_CHAT_ID,
        "NOT_SAYFASI_URL (ayarlar.py)": NOT_SAYFASI_URL,
    }
    eksikler = [ad for ad, deger in zorunlular.items() if not deger]
    if eksikler:
        raise SystemExit(
            "Eksik ayar var: " + ", ".join(eksikler) + "\nKurulum adımları için README.md'ye bak."
        )
