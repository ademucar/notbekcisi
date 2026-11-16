"""
obs.py - ESOGÜ OBS ile konuşan parça (Playwright ile).

Playwright gerçek bir tarayıcıyı (Chromium) kodla yönetir: adres açar, kutulara
yazar, butona basar, ekran görüntüsü alır. Tarayıcı görünmez (headless) çalışır.

Oturum nerede yaşıyor?
    Tarayıcının "context"inde. Context, çerezlerin (cookie) tutulduğu yerdir;
    normal tarayıcıdaki bir profil gibi düşünebilirsin. Context kapanmadığı ve
    sayfa düzenli açıldığı sürece OBS bizi içeride tutar.
"""

from playwright.sync_api import Browser, Frame, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

import ayarlar

SAYFA_ZAMAN_ASIMI_MS = 30_000

# Tablo satırlarını tek seferde okuyan JavaScript. r.cells yalnızca satırın kendi
# hücrelerini verir (iç içe tablolardaki hücreleri karıştırmaz). Başlık hücreleri (th) atlanır.
SATIR_OKUMA_JS = """
satirlar => satirlar.map(r =>
    Array.from(r.cells).filter(c => c.tagName === 'TD').map(c => c.innerText)
)
"""


class ObsIstemcisi:
    def __init__(self, tarayici: Browser):
        self._tarayici = tarayici
        self._context = None
        self._sayfa: Page | None = None
        self.yeni_oturum()

    def yeni_oturum(self) -> None:
        """Çerezleri sıfırlar (yani oturumu kapatır) ve temiz bir sekme açar."""
        if self._context:
            self._context.close()
        self._context = self._tarayici.new_context(locale="tr-TR")
        self._sayfa = self._context.new_page()
        self._sayfa.set_default_timeout(SAYFA_ZAMAN_ASIMI_MS)

    # ------------------------------------------------------------------ giriş

    def giris_formunu_doldur(self) -> bytes:
        """Giriş sayfasını açar, kullanıcı adı ve şifreyi yazar, captcha resmini döndürür."""
        s = self._sayfa
        s.goto(ayarlar.GIRIS_URL, wait_until="load")
        s.locator(ayarlar.SECICI_KULLANICI).first.fill(ayarlar.OBS_KULLANICI)
        s.locator(ayarlar.SECICI_SIFRE).first.fill(ayarlar.OBS_SIFRE)
        resim = s.locator(ayarlar.SECICI_CAPTCHA_RESIM).first
        resim.wait_for(state="visible")
        # Sayfanın tamamının değil, sadece captcha resminin ekran görüntüsü.
        return resim.screenshot()

    def girisi_tamamla(self, captcha_kodu: str) -> bool:
        """Captcha kodunu yazıp giriş butonuna basar. Giriş olduysa True döner."""
        s = self._sayfa
        s.locator(ayarlar.SECICI_CAPTCHA_KUTU).first.fill(captcha_kodu)
        buton = s.locator(ayarlar.SECICI_GIRIS_BUTONU).first
        try:
            # ASP.NET sayfalarında butona basınca sayfa yeniden yüklenir; onu bekliyoruz.
            with s.expect_navigation(wait_until="load"):
                buton.click()
        except PlaywrightTimeout:
            pass  # Sayfa yenilenmese bile aşağıdaki kontrol karar verir.
        return self.icerde_mi()

    # ------------------------------------------------------------------ durum

    def icerde_mi(self) -> bool:
        """Giriş yapılmış mı?

        Adrese bakmıyoruz, çünkü bazı siteler başarılı girişten sonra da aynı adreste
        kalır. Onun yerine sayfanın içeriğine bakıyoruz:
        şifre kutusu yoksa ve 'Çıkış' bağlantısı varsa içerideyiz.
        """
        cerceveler = self._sayfa.frames  # Öğeler bir çerçevenin içinde olabilir; hepsine bakıyoruz.
        sifre_kutusu_var = any(c.locator(ayarlar.SECICI_SIFRE).count() > 0 for c in cerceveler)
        cikis_var = any(c.locator(ayarlar.SECICI_CIKIS_BAGLANTISI).count() > 0 for c in cerceveler)
        return cikis_var and not sifre_kutusu_var

    def not_sayfasini_ac(self) -> bool:
        """Not sayfasını açar. Bu aynı zamanda oturumu tazeler. İçerideysek True döner."""
        self._sayfa.goto(ayarlar.NOT_SAYFASI_URL, wait_until="load")
        return self.icerde_mi()

    # ------------------------------------------------------------------ notlar

    def notlari_oku(self) -> dict[str, str]:
        """Not tablosunu {anahtar: satırın tamamı} sözlüğüne çevirir."""
        hucre_listeleri = self._not_kaynagi().locator(ayarlar.SECICI_NOT_SATIRLARI).evaluate_all(
            SATIR_OKUMA_JS
        )
        notlar: dict[str, str] = {}
        for hucreler in hucre_listeleri:
            if not hucreler:
                continue  # başlık satırı ya da boş satır
            # Hücre içindeki fazla boşlukları ve satır sonlarını tek boşluğa indir.
            # Boş hücre "-" olur ki sütunların yeri kaymasın.
            hucreler = [" ".join(h.split()) or "-" for h in hucreler]
            anahtar = " | ".join(hucreler[: ayarlar.ANAHTAR_SUTUN_SAYISI])
            # Aynı anahtar ikinci kez gelirse (örn. aynı ders iki satırda) numara ekle.
            asil_anahtar, sira = anahtar, 2
            while anahtar in notlar:
                anahtar = f"{asil_anahtar} #{sira}"
                sira += 1
            notlar[anahtar] = " | ".join(hucreler)
        return notlar

    def _not_kaynagi(self) -> Page | Frame:
        """Notların bulunduğu yer: ana sayfa ya da ayarlarda belirtilen çerçeve."""
        parca = ayarlar.NOT_CERCEVE_URL_PARCASI
        if not parca:
            return self._sayfa
        for cerceve in self._sayfa.frames:
            if parca in cerceve.url:
                return cerceve
        raise RuntimeError(f"Adresinde '{parca}' geçen çerçeve bulunamadı. kesif.py ile kontrol et.")
