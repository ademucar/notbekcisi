"""
telegram_bot.py - Telegram ile konuşan parça.

Telegram botları basit bir web adresi (HTTP API) üzerinden çalışır:
    https://api.telegram.org/bot<TOKEN>/<metot>
Kullandığımız metotlar:
    sendMessage    : yazı gönderir
    sendPhoto      : resim gönderir (captcha için)
    getUpdates     : bota gelen mesajları getirir (captcha cevabın ve komutların için)
    setMyCommands  : Telegram'da "/" yazınca çıkan komut listesini ayarlar

Bu dosyayı tek başına çalıştırırsan (python telegram_bot.py) bota son mesaj
atanların chat id'sini gösterir. .env'deki TELEGRAM_CHAT_ID'yi böyle bulursun.
"""

import json
import time

import requests

MAKS_MESAJ_UZUNLUGU = 4096  # Telegram'ın tek mesaj için sınırı


class TelegramHatasi(Exception):
    """Telegram isteği reddedince fırlatılır."""


class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self._adres = f"https://api.telegram.org/bot{token}/"
        self._chat_id = str(chat_id)
        # offset: Telegram'a "bu numaradan öncekileri okudum" demenin yolu.
        # Böylece aynı mesajı iki kez okumayız.
        self._offset = 0

    def _istek(self, metot: str, zaman_asimi: float = 30, **kwargs):
        cevap = requests.post(self._adres + metot, timeout=zaman_asimi, **kwargs)
        veri = cevap.json()
        if not veri.get("ok"):
            raise TelegramHatasi(f"{metot} başarısız: {veri.get('description')}")
        return veri["result"]

    def mesaj_gonder(self, metin: str) -> None:
        if len(metin) > MAKS_MESAJ_UZUNLUGU:
            metin = metin[: MAKS_MESAJ_UZUNLUGU - 20] + "\n...(kısaltıldı)"
        self._istek("sendMessage", data={"chat_id": self._chat_id, "text": metin})

    def foto_gonder(self, foto: bytes, aciklama: str = "") -> None:
        self._istek(
            "sendPhoto",
            data={"chat_id": self._chat_id, "caption": aciklama},
            files={"photo": ("captcha.png", foto, "image/png")},
        )

    def komutlari_tanit(self, komutlar: dict[str, str]) -> None:
        """Telegram'da "/" yazınca çıkan komut listesini ayarlar. Örn. {"durum": "Durumu göster"}"""
        liste = [{"command": ad, "description": aciklama} for ad, aciklama in komutlar.items()]
        self._istek("setMyCommands", data={"commands": json.dumps(liste, ensure_ascii=False)})

    def eski_mesajlari_atla(self) -> None:
        """Daha önce gelmiş mesajları okunmuş sayar.

        Program başlarken ve captcha'yı göndermeden hemen önce çağrılır; böylece saatler
        önce yazdığın bir mesaj captcha cevabı ya da yeni bir komut sanılmaz.
        """
        # offset=-1 yalnızca en son mesajı getirir; onun bir fazlası "hepsini okudum" demektir.
        guncellemeler = self._istek("getUpdates", data={"offset": -1, "timeout": 0})
        if guncellemeler:
            self._offset = guncellemeler[-1]["update_id"] + 1

    def cevap_bekle(self, sure_sn: float) -> str | None:
        """Senden gelen ilk yazılı mesajı döndürür. Süre dolarsa None döner."""
        bitis = time.monotonic() + sure_sn
        while (kalan := bitis - time.monotonic()) > 0:
            # Uzun yoklama (long polling): Telegram, mesaj gelene kadar bağlantıyı
            # en fazla 'timeout' saniye açık tutar. Sürekli istek atmaktan çok daha verimli.
            bekleme = int(min(25, max(1, kalan)))
            guncellemeler = self._istek(
                "getUpdates",
                zaman_asimi=bekleme + 10,
                data={"offset": self._offset, "timeout": bekleme},
            )
            for guncelleme in guncellemeler:
                self._offset = guncelleme["update_id"] + 1
                mesaj = guncelleme.get("message") or {}
                # Sadece senin sohbetinden gelen yazılara bak; başkası bota yazarsa yok sayılır.
                if str(mesaj.get("chat", {}).get("id")) == self._chat_id and mesaj.get("text"):
                    return mesaj["text"].strip()
        return None


def chat_id_bul() -> None:
    """Kurulum yardımcısı: bota mesaj atanların chat id'lerini yazdırır."""
    import ayarlar

    if not ayarlar.TELEGRAM_TOKEN:
        raise SystemExit("Önce .env dosyasına TELEGRAM_TOKEN yaz.")
    input("Telegram'da botuna herhangi bir mesaj at, sonra buraya dönüp Enter'a bas...")
    veri = requests.get(
        f"https://api.telegram.org/bot{ayarlar.TELEGRAM_TOKEN}/getUpdates", timeout=30
    ).json()
    if not veri.get("ok"):
        raise SystemExit(f"Telegram hatası: {veri.get('description')} (token doğru mu?)")

    sohbetler = {}
    for guncelleme in veri["result"]:
        sohbet = (guncelleme.get("message") or {}).get("chat")
        if sohbet:
            sohbetler[sohbet["id"]] = sohbet.get("first_name") or sohbet.get("title") or ""

    if not sohbetler:
        print("Mesaj bulunamadı. Bota mesaj attığından emin ol ve tekrar dene.")
    for sohbet_id, ad in sohbetler.items():
        print(f"chat id: {sohbet_id}   ({ad})")
    print("Kendi adının yanındaki sayıyı .env'deki TELEGRAM_CHAT_ID'ye yaz.")


if __name__ == "__main__":
    chat_id_bul()
