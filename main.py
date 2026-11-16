"""
main.py - Not Bekçisi'nin ana döngüsü. Programı bununla başlatırsın: python main.py

Her turda:
    1. Not sayfasını aç. Oturum kapalıysa Telegram'dan captcha sorarak giriş yap.
       Sessiz saatlerdeysek (gece) captcha isteme; kendini durdur, /devam yazılmasını bekle.
    2. Notları oku, kayıtlı olanlarla karşılaştır.
    3. Fark varsa Telegram'dan bildir ve yeni hâli kaydet.
    4. KONTROL_ARALIGI_DK kadar bekle; beklerken Telegram komutlarına cevap ver. 1'e dön.
Not sayfasının her açılışı OBS oturumunu da tazeler; 15 dakikalık süre hiç dolmaz.

Telegram komutları:
    /durdur  Not kontrolünü ve captcha istemeyi durdurur.
    /devam   Kaldığı yerden devam eder.
    /durum   Son kontrolü ve oturumun ne zamandır açık olduğunu yazar.

Durdurmak için terminalde Ctrl+C.
"""

import logging
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

import ayarlar
from not_deposu import NotDeposu, farklari_bul
from obs import ObsIstemcisi
from telegram_bot import TelegramBot

log = logging.getLogger("notbekcisi")

ARDISIK_HATA_SINIRI = 3  # Üst üste bu kadar hatada tarayıcı oturumu sıfırlanır.
DURAKLAMA_YOKLAMA_DK = 60  # Durdurulmuşken döngü bu aralıkla kendini yoklar (komutlar yine anında işlenir).

# Telegram'da "/" yazınca çıkan menü. Anahtar komutun adı, değer açıklaması.
KOMUTLAR = {
    "durdur": "Not kontrolünü ve captcha istemeyi durdur",
    "devam": "Kaldığı yerden devam et",
    "durum": "Son kontrolü ve oturum süresini göster",
}
KOMUT_LISTESI = "Komutlar: /durdur, /devam, /durum"


def sure_yazisi(sure: timedelta) -> str:
    saat, dakika = divmod(int(sure.total_seconds()) // 60, 60)
    return f"{saat} sa {dakika} dk"


# ---------------------------------------------------------------- sessiz saatler

def sessiz_saatte_mi(an: datetime) -> bool:
    """Verilen an, ayarlar.py'deki sessiz saatlerin içinde mi?"""
    bas, bit = ayarlar.SESSIZ_BASLANGIC_SAATI, ayarlar.SESSIZ_BITIS_SAATI
    if bas == bit:
        return False  # sessiz saat kapalı
    if bas < bit:
        return bas <= an.hour < bit  # örn. 0–8
    return an.hour >= bas or an.hour < bit  # gece yarısını aşan aralık, örn. 23–7


def tekrar_sorma_yazisi() -> str:
    """Giriş olmadıysa bir sonraki captcha'nın ne zaman isteneceğini anlatan cümle."""
    zaman = datetime.now() + timedelta(minutes=ayarlar.GIRIS_TEKRAR_BEKLEME_DK)
    if sessiz_saatte_mi(zaman):
        return "Sessiz saatlere denk geldiği için kendiliğimden sormayacağım; hazır olunca /devam yaz."
    return f"Saat {zaman:%H:%M} civarında tekrar soracağım."


class NotBekcisi:
    def __init__(self, obs: ObsIstemcisi, bot: TelegramBot, depo: NotDeposu):
        self.obs = obs
        self.bot = bot
        self.depo = depo
        self.oturum_baslangici: datetime | None = None  # Oturumun ne kadar dayandığını ölçmek için
        self.kapanan_oturum_suresi: timedelta | None = None  # Kapanan oturumun süresi, henüz bildirilmediyse
        self.ardisik_hata = 0
        self.duraklatildi = False  # /durdur ile ya da gece oturum düşünce True olur
        self.durdurma_sebebi = ""
        self.duraklamadan_dondu = False  # /devam'dan sonraki ilk turda True; oturum süresi ölçümünü bozmamak için
        self.son_kontrol: datetime | None = None
        self.son_kontrol_sonucu = ""

    # ------------------------------------------------------------ yardımcılar

    def gonder(self, metin: str) -> bool:
        """Telegram'a mesaj atar. Ulaşılamazsa program çökmez, sadece log'a yazar."""
        try:
            self.bot.mesaj_gonder(metin)
            return True
        except Exception:
            log.exception("Telegram mesajı gönderilemedi")
            return False

    # ------------------------------------------------------------ komutlar

    def komutu_isle(self, metin: str) -> bool:
        """Telegram'dan gelen bir mesajı işler. Beklemenin hemen bitmesi gerekiyorsa True döner."""
        # "/durum" ya da "/durum@botadi" -> "durum". "/" ile başlamıyorsa komut değil.
        komut = metin.split()[0].split("@")[0][1:].lower() if metin.startswith("/") else ""

        if komut == "durdur":
            if self.duraklatildi:
                self.gonder("Zaten durdurulmuş. Devam etmek için /devam yaz.")
                return False
            self.duraklatildi = True
            self.durdurma_sebebi = "/durdur ile"
            log.info("Telegram'dan durduruldu")
            self.gonder("Durdurdum. Not kontrolü yapmayacağım, captcha da istemeyeceğim.\nDevam etmek için /devam yaz.")
            return True

        if komut == "devam":
            if not self.duraklatildi:
                self.gonder("Zaten çalışıyorum. " + KOMUT_LISTESI)
                return False
            self.duraklatildi = False
            self.duraklamadan_dondu = True
            log.info("Telegram'dan devam ettirildi")
            self.gonder("Devam ediyorum, şimdi kontrol ediyorum.")
            return True

        if komut == "durum":
            self.gonder(self.durum_yazisi())
            return False

        self.gonder("Şu an captcha kodu beklemiyorum. " + KOMUT_LISTESI)
        return False

    def durum_yazisi(self) -> str:
        simdi = datetime.now()
        if self.duraklatildi:
            durum = f"Durduruldu ({self.durdurma_sebebi}). Devam için /devam yaz"
        else:
            durum = "Çalışıyor"
        oturum = f"açık ({sure_yazisi(simdi - self.oturum_baslangici)})" if self.oturum_baslangici else "kapalı"
        son = f"{self.son_kontrol:%d.%m %H:%M}, {self.son_kontrol_sonucu}" if self.son_kontrol else "henüz yok"
        bas, bit = ayarlar.SESSIZ_BASLANGIC_SAATI, ayarlar.SESSIZ_BITIS_SAATI
        sessiz = f"{bas:02d}:00–{bit:02d}:00" if bas != bit else "kapalı"
        return f"Durum: {durum}\nOturum: {oturum}\nSon kontrol: {son}\nSessiz saatler: {sessiz}"

    def bekle(self, dakika: float) -> None:
        """Bir sonraki tura kadar bekler; bu arada Telegram komutlarına cevap verir.

        /durdur ya da /devam gelirse beklemeyi erken bitirir ki döngü hemen tepki versin.
        """
        bitis = time.monotonic() + dakika * 60
        while (kalan := bitis - time.monotonic()) > 0:
            try:
                mesaj = self.bot.cevap_bekle(kalan)
            except Exception:
                # İnternet bir anlığına giderse program çökmesin; biraz bekleyip tekrar dinle.
                log.exception("Telegram'dan mesaj okunamadı")
                time.sleep(min(60, kalan))
                continue
            if mesaj is not None and self.komutu_isle(mesaj):
                return

    # ------------------------------------------------------------ giriş

    def captcha_cevabi_bekle(self) -> str | None:
        """Captcha kodunu bekler; arada gelen komutları işler.

        Kodu döndürür. Süre dolarsa ya da /durdur gelirse None döner.
        """
        bitis = time.monotonic() + ayarlar.CAPTCHA_CEVAP_BEKLEME_DK * 60
        while (kalan := bitis - time.monotonic()) > 0:
            mesaj = self.bot.cevap_bekle(kalan)
            if mesaj is None:
                return None
            if not mesaj.startswith("/"):
                return mesaj  # komut değil, captcha kodu
            self.komutu_isle(mesaj)
            if self.duraklatildi:
                return None
        return None

    def captcha_ile_giris(self) -> bool:
        """Captcha'yı Telegram'dan sorarak giriş yapar. Başarılıysa True."""
        maks = ayarlar.MAKS_GIRIS_DENEMESI
        for deneme in range(1, maks + 1):
            resim = self.obs.giris_formunu_doldur()
            self.bot.eski_mesajlari_atla()
            self.bot.foto_gonder(resim, f"OBS'ye girmek için bu kodu yaz ({deneme}/{maks}).")
            log.info("Captcha gönderildi (%d/%d), cevap bekleniyor", deneme, maks)

            kod = self.captcha_cevabi_bekle()
            if kod is None:
                # /durdur ile kesildiyse ya da gece olduysa ayrıca mesaj atıp rahatsız etme.
                if not self.duraklatildi and not sessiz_saatte_mi(datetime.now()):
                    self.gonder(
                        f"{ayarlar.CAPTCHA_CEVAP_BEKLEME_DK} dk içinde cevap gelmedi. {tekrar_sorma_yazisi()}"
                    )
                return False
            if self.obs.girisi_tamamla(kod):
                return True
            self.gonder("Giriş olmadı, kod yanlış olabilir.")

        self.gonder(f"{maks} deneme üst üste olmadı. Şifreni ve ayarları kontrol et. {tekrar_sorma_yazisi()}")
        return False

    def oturum_kapandi(self) -> None:
        """Oturumun düştüğünü kaydeder. Ne kadar açık kaldığı, captcha istenmeden hemen önce bildirilir."""
        if self.oturum_baslangici is None:
            return  # Zaten açık bir oturum yoktu (örneğin program yeni başladı).
        if self.duraklamadan_dondu:
            # Durdurulmuşken oturumu canlı tutmadık; düşmesi normal, süresini ölçüme katmıyoruz.
            log.info("Durdurulmuşken oturum kapanmış")
        else:
            self.kapanan_oturum_suresi = datetime.now() - self.oturum_baslangici
            log.info("Oturum kapandı, açık kalma süresi: %s", sure_yazisi(self.kapanan_oturum_suresi))
        self.oturum_baslangici = None

    # ------------------------------------------------------------ notlar

    def notlari_kontrol_et(self) -> None:
        yeni = self.obs.notlari_oku()
        self.son_kontrol = datetime.now()
        if not yeni:
            log.warning("Not tablosunda satır bulunamadı; kayıt değiştirilmedi.")
            self.son_kontrol_sonucu = "not tablosu boş geldi"
            return

        if not self.depo.var_mi():
            # İlk çalışma: Var olan notları "zaten biliniyor" say, hepsini bildirme.
            self.depo.yaz(yeni)
            self.son_kontrol_sonucu = "takip başladı"
            self.gonder(f"Takip başladı. {len(yeni)} satır kaydedildi; bundan sonraki değişiklikleri bildireceğim.")
            return

        farklar = farklari_bul(self.depo.oku(), yeni, ayarlar.SUTUN_ADLARI, ayarlar.ANAHTAR_SUTUN_SAYISI)
        if not farklar:
            log.info("Değişiklik yok (%d satır)", len(yeni))
            self.son_kontrol_sonucu = "değişiklik yok"
            self.depo.yaz(yeni)
            return

        log.info("%d değişiklik bulundu", len(farklar))
        self.son_kontrol_sonucu = f"{len(farklar)} yeni not bildirildi"
        # Mesaj gidemezse kaydetmiyoruz; böylece bir sonraki turda aynı fark yine bulunur ve tekrar denenir.
        if self.gonder("Yeni not girildi!\n\n" + "\n\n".join(farklar)):
            self.depo.yaz(yeni)

    # ------------------------------------------------------------ döngü

    def tur(self) -> float:
        """Bir kontrol turu yapar. Bir sonraki tura kadar kaç dakika bekleneceğini döndürür."""
        if not self.obs.not_sayfasini_ac():
            self.oturum_kapandi()
            # /devam'ı sen yazdıysan uyanıksın demektir: saat kaç olursa olsun captcha iste.
            sen_istedin = self.duraklamadan_dondu
            self.duraklamadan_dondu = False
            if sessiz_saatte_mi(datetime.now()) and not sen_istedin:
                # Gece captcha isteyip uyandırmak yerine kendimizi durduruyoruz; sen uyanınca /devam yazarsın.
                self.duraklatildi = True
                self.durdurma_sebebi = "gece oturum kapandı"
                log.info("Oturum kapalı ve sessiz saatlerdeyiz; /devam yazılana kadar durduruldu")
                return 0
            if self.kapanan_oturum_suresi is not None:
                self.gonder(f"Oturum kapandı (açık kalma süresi: {sure_yazisi(self.kapanan_oturum_suresi)}).")
                self.kapanan_oturum_suresi = None
            if not self.captcha_ile_giris():
                return ayarlar.GIRIS_TEKRAR_BEKLEME_DK
            self.oturum_baslangici = datetime.now()
            self.gonder("Giriş yapıldı, takip sürüyor.")
            if not self.obs.not_sayfasini_ac():
                raise RuntimeError("Girişten hemen sonra not sayfası açılamadı. NOT_SAYFASI_URL doğru mu?")

        # /devam yazdıysan ve oturum hâlâ açıksa (yani "Giriş yapıldı" mesajı gelmediyse) sonucu da söyle;
        # yoksa "şimdi kontrol ediyorum" dedikten sonra sessiz kalmak takılmış gibi görünür.
        sonucu_soyle = self.duraklamadan_dondu
        self.duraklamadan_dondu = False
        self.notlari_kontrol_et()
        if sonucu_soyle and self.son_kontrol_sonucu == "değişiklik yok":
            self.gonder("Kontrol ettim, yeni not yok. Takip sürüyor.")
        return ayarlar.KONTROL_ARALIGI_DK

    def calis(self) -> None:
        try:
            self.bot.eski_mesajlari_atla()  # Program kapalıyken yazılmış eski komutlar işlenmesin.
            self.bot.komutlari_tanit(KOMUTLAR)
        except Exception:
            log.exception("Telegram hazırlığı yapılamadı (komut menüsü görünmeyebilir)")
        self.gonder("Not Bekçisi başladı. " + KOMUT_LISTESI)

        while True:
            if self.duraklatildi:
                self.bekle(DURAKLAMA_YOKLAMA_DK)  # /devam gelince erken döner
                continue
            try:
                bekleme_dk = self.tur()
                self.ardisik_hata = 0
            except Exception as hata:
                self.ardisik_hata += 1
                log.exception("Tur sırasında hata (%d. kez üst üste)", self.ardisik_hata)
                bekleme_dk = ayarlar.HATA_SONRASI_BEKLEME_DK
                if self.ardisik_hata >= ARDISIK_HATA_SINIRI:
                    self.gonder(f"Üst üste {self.ardisik_hata} hata oldu, tarayıcıyı sıfırlıyorum. Son hata: {hata}")
                    self.obs.yeni_oturum()
                    self.oturum_baslangici = None
                    self.ardisik_hata = 0
            self.bekle(bekleme_dk)


def log_ayarla() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ayarlar.LOG_DOSYASI, encoding="utf-8"),
        ],
    )


def main() -> None:
    log_ayarla()
    ayarlar.eksikleri_kontrol_et()
    bot = TelegramBot(ayarlar.TELEGRAM_TOKEN, ayarlar.TELEGRAM_CHAT_ID)
    depo = NotDeposu(ayarlar.NOT_DOSYASI)

    with sync_playwright() as p:
        tarayici = p.chromium.launch(headless=True)
        try:
            NotBekcisi(ObsIstemcisi(tarayici), bot, depo).calis()
        except KeyboardInterrupt:
            log.info("Kapatılıyor (Ctrl+C).")
        finally:
            tarayici.close()


if __name__ == "__main__":
    main()
