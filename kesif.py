"""
kesif.py - OBS sayfalarının yapısını inceleyip ayarlar.py'yi doldurmana yardım eder.

Tarayıcıyı GÖRÜNÜR açar ve şu sırayla çalışır:
    1. Giriş sayfasındaki kutuları, resimleri, butonları listeler ve ayarlar.py'deki
       seçicilerin kaç öğe bulduğunu gösterir. Doğru bir seçici tam 1 öğe bulmalı.
    2. Sen açılan pencerede elle giriş yapıp not sayfana gidersin. Program Enter
       beklemez: SECICI_CIKIS_BAGLANTISI sayfada belirince girişin olduğunu anlar,
       not sayfasına geçebilmen için GIRIS_SONRASI_BEKLEME_SN kadar daha bekler,
       sonra o an açık olan sayfanın adresini, çerçevelerini (iframe) ve tablolarını listeler.
    3. NOT_SAYFASI_URL doluysa, main.py'nin her turda yaptığı gibi bu adresi doğrudan
       açar ve programın içeride olduğunu anlayıp notları okuyabildiğini kontrol eder.

Ekrana yazılan her şey kesif_cikti.txt dosyasına da yazılır.

Çalıştırma: python kesif.py
"""

import time

from playwright.sync_api import BrowserContext, Page, sync_playwright

import ayarlar
from obs import SATIR_OKUMA_JS  # notları main.py ile aynı mantıkla okumak için

CIKTI_DOSYASI = ayarlar.PROJE_KLASORU / "kesif_cikti.txt"
GIRIS_BEKLEME_SINIRI_DK = 10   # Bu sürede giriş anlaşılamazsa (seçici yanlışsa) yine de devam edilir.
GIRIS_SONRASI_BEKLEME_SN = 10  # Giriş anlaşıldıktan sonra not sayfasına geçmen için tanınan süre.

# Sayfadaki görünür form öğelerini ve resimleri listeleyen JavaScript.
FORM_JS = """
() => [...document.querySelectorAll('input, button, img, select')]
    .filter(e => e.type !== 'hidden')
    .map(e => ({
        etiket: e.tagName.toLowerCase(),
        tip: e.type || '',
        id: e.id,
        name: e.getAttribute('name') || '',
        bilgi: (e.tagName === 'IMG' ? (e.getAttribute('src') || '') : (e.value || e.innerText || '')).slice(0, 60),
    }))
"""

# Sayfadaki tabloları ve her birinin ilk birkaç satırını listeleyen JavaScript.
TABLO_JS = """
() => [...document.querySelectorAll('table')]
    .map((t, i) => ({
        sira: i,
        id: t.id,
        sinif: t.className,
        satir: t.rows.length,
        ornek: [...t.rows].slice(0, 4).map(r =>
            [...r.cells].map(c => c.innerText.trim().replace(/\\s+/g, ' ').slice(0, 25)).join(' | ')
        ),
    }))
    .filter(t => t.satir > 1)
"""

# Çıkış bağlantısına benzeyen öğeleri listeleyen JavaScript.
# SECICI_CIKIS_BAGLANTISI tutmazsa doğrusunu bulmak için.
CIKIS_ADAYLARI_JS = """
() => [...document.querySelectorAll('a, button, input[type=submit], input[type=button], input[type=image]')]
    .map(e => ({
        etiket: e.tagName.toLowerCase(),
        id: e.id,
        yazi: (e.innerText || e.value || e.title || '').trim().slice(0, 40),
        href: (e.getAttribute('href') || '').slice(0, 80),
    }))
    .filter(e => /çık|cik|logout|exit|kapat/i.test(e.yazi + ' ' + e.href + ' ' + e.id))
"""

GIRIS_SECICILERI = [
    "SECICI_KULLANICI",
    "SECICI_SIFRE",
    "SECICI_CAPTCHA_RESIM",
    "SECICI_CAPTCHA_KUTU",
    "SECICI_GIRIS_BUTONU",
]


def yaz(*parcalar) -> None:
    """print gibi ekrana yazar; aynı satırı kesif_cikti.txt dosyasına da ekler."""
    print(*parcalar, flush=True)
    with open(CIKTI_DOSYASI, "a", encoding="utf-8") as dosya:
        print(*parcalar, file=dosya)


def secici_say(kaynak, secici: str):
    try:
        return kaynak.locator(secici).count()
    except Exception as hata:
        return f"hatalı seçici ({hata})"


def icerde_mi(sayfa: Page) -> bool:
    """obs.py'deki icerde_mi ile aynı kural: Çıkış bağlantısı var ve şifre kutusu yok."""
    try:
        cerceveler = sayfa.frames
        cikis_var = any(c.locator(ayarlar.SECICI_CIKIS_BAGLANTISI).count() > 0 for c in cerceveler)
        sifre_var = any(c.locator(ayarlar.SECICI_SIFRE).count() > 0 for c in cerceveler)
        return cikis_var and not sifre_var
    except Exception:
        # Sen bir yere tıkladığın için sayfa o an yükleniyorsa sorgu yarıda kalır; "henüz değil" sayıyoruz.
        return False


def girisi_bekle(baglam: BrowserContext) -> bool:
    """Herhangi bir sekmede giriş yapılmış görünene kadar bekler. Görünürse True döner."""
    bitis = time.monotonic() + GIRIS_BEKLEME_SINIRI_DK * 60
    while time.monotonic() < bitis:
        if not baglam.pages:
            return False  # pencere kapatıldı
        if any(icerde_mi(s) for s in baglam.pages):
            return True
        # time.sleep yerine bunu kullanıyoruz: Playwright beklerken tarayıcıdan gelen
        # olayları (yeni sekme açılması gibi) işlemeye devam eder.
        baglam.pages[-1].wait_for_timeout(1000)
    return False


def satirlari_yaz(sayfa: Page) -> None:
    """ayarlar.py'deki SECICI_NOT_SATIRLARI ile okunan satırları yazar (obs.py ile aynı okuma)."""
    kaynak = sayfa
    parca = ayarlar.NOT_CERCEVE_URL_PARCASI
    if parca:
        kaynak = next((c for c in sayfa.frames if parca in c.url), None)
        if kaynak is None:
            yaz(f"    Adresinde '{parca}' geçen çerçeve yok! NOT_CERCEVE_URL_PARCASI yanlış.")
            return

    satirlar = [h for h in kaynak.locator(ayarlar.SECICI_NOT_SATIRLARI).evaluate_all(SATIR_OKUMA_JS) if h]
    anahtarlar = {" | ".join(" ".join(x.split()) for x in h[: ayarlar.ANAHTAR_SUTUN_SAYISI]) for h in satirlar}
    yaz(f"    Okunan satır: {len(satirlar)}, farklı anahtar: {len(anahtarlar)} (ikisi eşit olmalı)")
    for hucreler in satirlar[:15]:
        yaz("    ", " | ".join(" ".join(h.split()) or "-" for h in hucreler))


def sayfayi_incele(sayfa: Page) -> None:
    """Açık olan sayfanın adresini, çerçevelerini ve tablolarını yazar."""
    yaz("Adres (NOT_SAYFASI_URL için):", sayfa.url)
    for cerceve in sayfa.frames:
        ad = "ana sayfa" if cerceve == sayfa.main_frame else f"çerçeve: {cerceve.url}"
        yaz(f"\n--- {ad} ---")
        yaz("SECICI_CIKIS_BAGLANTISI eşleşmesi:", secici_say(cerceve, ayarlar.SECICI_CIKIS_BAGLANTISI))
        yaz("SECICI_SIFRE eşleşmesi (0 olmalı):", secici_say(cerceve, ayarlar.SECICI_SIFRE))
        for e in cerceve.evaluate(CIKIS_ADAYLARI_JS):
            yaz(f"Çıkışa benzeyen: <{e['etiket']}> id={e['id']!r} yazı={e['yazi']!r} href={e['href']!r}")
        for t in cerceve.evaluate(TABLO_JS):
            yaz(f"\nTablo #{t['sira']}  id={t['id']!r}  class={t['sinif']!r}  satır sayısı={t['satir']}")
            for satir in t["ornek"]:
                yaz("    ", satir)

    yaz("\nŞu an ayarlar.py'deki SECICI_NOT_SATIRLARI ile okunan satırlar:")
    satirlari_yaz(sayfa)


def main() -> None:
    CIKTI_DOSYASI.write_text("", encoding="utf-8")  # önceki çalıştırmanın çıktısını temizle

    with sync_playwright() as p:
        tarayici = p.chromium.launch(headless=False)
        # obs.py ile aynı dil ayarı; site dile göre farklı yazı gösterirse ("Logout" gibi) şaşırmayalım.
        baglam = tarayici.new_context(locale="tr-TR")
        sayfa = baglam.new_page()
        sayfa.goto(ayarlar.GIRIS_URL, wait_until="load")

        yaz("\n=== 1) GİRİŞ SAYFASINDAKİ ÖĞELER ===")
        for e in sayfa.evaluate(FORM_JS):
            yaz(f"<{e['etiket']}> tip={e['tip']!r} id={e['id']!r} name={e['name']!r}  {e['bilgi']!r}")

        yaz("\n=== ayarlar.py'deki seçiciler kaç öğe buluyor? (1 olmalı) ===")
        for ad in GIRIS_SECICILERI:
            secici = getattr(ayarlar, ad)
            yaz(f"{ad:24} {secici!r:50} -> {secici_say(sayfa, secici)}")

        yaz(
            "\nŞimdi açılan pencerede ELLE giriş yap ve notlarını gördüğün sayfaya git."
            f"\nGiriş anlaşılınca {GIRIS_SONRASI_BEKLEME_SN} saniye sonra o an açık olan sayfa incelenecek."
            f"\n(En fazla {GIRIS_BEKLEME_SINIRI_DK} dakika beklenir.)"
        )
        if girisi_bekle(baglam):
            yaz(f"Giriş anlaşıldı. {GIRIS_SONRASI_BEKLEME_SN} saniye bekleniyor...")
            baglam.pages[-1].wait_for_timeout(GIRIS_SONRASI_BEKLEME_SN * 1000)
        elif baglam.pages:
            yaz(
                f"UYARI: {GIRIS_BEKLEME_SINIRI_DK} dakikada giriş anlaşılamadı. SECICI_CIKIS_BAGLANTISI "
                "yanlış olabilir; aşağıdaki 'Çıkışa benzeyen' satırlarına bak. Açık sayfayla devam ediliyor."
            )
        if not baglam.pages:
            yaz("Pencere kapatıldı, not sayfası incelenemedi.")
            return

        # Not sayfası yeni sekmede açıldıysa en son açılan sekme odur.
        sayfa = baglam.pages[-1]
        yaz("\n=== 2) NOT SAYFASI ===")
        sayfayi_incele(sayfa)

        if ayarlar.NOT_SAYFASI_URL:
            yaz("\n=== 3) NOT_SAYFASI_URL DOĞRUDAN AÇILINCA (main.py böyle yapar) ===")
            yeni = baglam.new_page()
            yeni.goto(ayarlar.NOT_SAYFASI_URL, wait_until="load")
            yaz("Açılan adres:", yeni.url)
            yaz("İçeride mi? (True olmalı):", icerde_mi(yeni))
            satirlari_yaz(yeni)

        yaz(f"\nBitti. Bu çıktı {CIKTI_DOSYASI.name} dosyasına da yazıldı.")
        tarayici.close()


if __name__ == "__main__":
    main()
