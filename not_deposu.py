"""
not_deposu.py - Son görülen notları saklar ve yenileriyle karşılaştırır.

Notlar bir sözlük (dict) olarak tutulur:
    anahtar -> satırı tanımlayan kısım   örn. "MAT301 | Modern Cebir"
    değer   -> satırın tamamı            örn. "MAT301 | Modern Cebir | 75 | - | -"
Bir satırın değeri değiştiyse ya da yeni bir satır geldiyse, not girilmiş demektir.
Bu dosyada tarayıcı ya da internet yok; o yüzden tek başına kolayca test edilebilir.
"""

import json
import os
import re
from pathlib import Path

HUCRE_AYRACI = " | "  # obs.py hücreleri bununla birleştirir

# OBS'de bir sınav hücresi "YAZILI (%40): 90" gibi görünür; puan girilmemişse "YAZILI (%40):".
# Bir hücrede birden fazla parça olabilir: "YAZILI (%30): 80 PROJE (%30): 70".
# Bu desen her parçayı (tür, ağırlık, puan) olarak yakalar. Puan, bir sonraki
# "TÜR (%..):" başlangıcına ya da hücrenin sonuna kadar olan kısımdır.
PARCA_DESENI = re.compile(r"(\w+) \((%\d+)\):(.*?)(?=\s+\w+ \(%\d+\):|$)")


def hucre_ozeti(hucre: str) -> str:
    """Bir hücreyi kısaltır: "YAZILI (%40): 90" -> "90 (YAZILI %40)".

    Puanı girilmemiş parçalar atlanır. Hücre bu biçimde değilse ("36", "BA" gibi) olduğu gibi döner.
    """
    parcalar = PARCA_DESENI.findall(hucre)
    if not parcalar:
        return hucre
    dolu = [f"{puan.strip()} ({tur} {agirlik})" for tur, agirlik, puan in parcalar if puan.strip()]
    return ", ".join(dolu) if dolu else "boş"


def farklari_bul(
    eski: dict[str, str],
    yeni: dict[str, str],
    sutun_adlari: list[str],
    anahtar_sutun_sayisi: int,
) -> list[str]:
    """Yeni gelen ya da değişen satırları kısa mesajlar olarak döndürür.

    Her ders için yalnızca değişen sütunlar yazılır, örneğin:
        VERİ YAPILARI (A)
        Ara Sınav 1: 75 (YAZILI %40)
        Ortalama: 30

    Kaybolan satırlar bildirilmez: Sayfa bir anlığına eksik yüklenirse
    boşuna "not silindi" alarmı çalmasın.
    """
    mesajlar = []
    for anahtar, satir in yeni.items():
        eski_satir = eski.get(anahtar)
        if eski_satir == satir:
            continue

        hucreler = satir.split(HUCRE_AYRACI)
        eski_hucreler = eski_satir.split(HUCRE_AYRACI) if eski_satir else []
        degisenler = []
        # Anahtar sütunları (ders kodu, ders adı) değişmez; notlar onlardan sonra başlar.
        for i in range(anahtar_sutun_sayisi, len(hucreler)):
            onceki = eski_hucreler[i] if i < len(eski_hucreler) else None
            if hucreler[i] == onceki:
                continue
            ozet = hucre_ozeti(hucreler[i])
            if onceki is None and ozet in ("-", "boş"):
                continue  # yeni gelen bir dersin boş sütunlarını yazmaya gerek yok
            ad = sutun_adlari[i] if i < len(sutun_adlari) else f"{i + 1}. sütun"
            degisenler.append(f"{ad}: {ozet}")

        # Başlık: anahtarın son sütunu, yani ders adı.
        baslik = hucreler[anahtar_sutun_sayisi - 1] if anahtar_sutun_sayisi else anahtar
        if eski_satir is None:
            baslik = f"Yeni ders: {baslik}"
        if not degisenler and eski_satir is not None:
            # Beklenmedik bir durum (örn. sütun sayısı değişti): bilgi kaybolmasın diye satırın tamamını yaz.
            degisenler = [f"Önce:  {eski_satir}", f"Şimdi: {satir}"]
        mesajlar.append("\n".join([baslik, *degisenler]))
    return mesajlar


class NotDeposu:
    def __init__(self, dosya: Path):
        self._dosya = Path(dosya)

    def var_mi(self) -> bool:
        return self._dosya.exists()

    def oku(self) -> dict[str, str]:
        if not self._dosya.exists():
            return {}
        return json.loads(self._dosya.read_text(encoding="utf-8"))

    def yaz(self, notlar: dict[str, str]) -> None:
        # Önce geçici dosyaya yazıp sonra adını değiştiriyoruz. Yazma sırasında
        # program kapanırsa eski dosya bozulmadan kalır (yarım dosya oluşmaz).
        gecici = self._dosya.with_suffix(".tmp")
        gecici.write_text(json.dumps(notlar, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(gecici, self._dosya)
