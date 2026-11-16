# Not Bekçisi'ni Oracle Cloud'da (ücretsiz) çalıştırma

Bu rehber, programı bilgisayarın kapalıyken de çalışsın diye Oracle Cloud'un
ücretsiz (Always Free) sunucusuna taşımak için. Yaklaşık 30–45 dakika sürer.

## Başlamadan önce bil
- **Sunucu captcha'yı kaldırmaz.** Oturum düşünce kod yine Telegram'dan sana gelir.
- **Kayıt için kredi/banka kartı ister.** Ücretsiz katmanda para çekilmez, kart sadece kimlik doğrulama içindir. Kart bilgisini sen gireceksin.
- **Boşta kalan sunucuyu geri alabilirler.** Oracle, 7 gün boyunca çok az işlemci/ağ/bellek kullanan ücretsiz sunucuları durdurabiliyor. Bizim program çok az kaynak kullanıyor. Sunucu durdurulursa konsoldan tekrar başlatabilirsin. Sürekli olursa hesabı "Pay As You Go"ya yükseltmek bu kuralı kaldırır (ücretsiz sınırlar içinde kaldıkça yine para ödemezsin, ama sınırı aşarsan ücret çıkar).
- **Programın aynı anda iki kopyası çalışmasın.** Sunucudaki çalışırken bilgisayarındakini kapat. İkisi aynı anda çalışırsa Telegram'daki captcha cevabını birbirinden kapar, OBS oturumları da birbirini atabilir.

---

## 1. Oracle hesabı aç (sen yapacaksın)
1. https://www.oracle.com/cloud/free/ adresine git, **Start for free**'ye tıkla.
2. Bilgilerini gir. **Home Region** (ana bölge) seçimi önemli:
   - Sonradan **değiştirilemez** ve ücretsiz sunucular sadece bu bölgede açılır.
   - Türkiye bölgesi yok. Yakın bir Avrupa bölgesi seç. Frankfurt çok kalabalık olduğu için sık sık "kapasite yok" hatası veriyor; başka bir Avrupa bölgesi daha şanslı olabilir.
3. Kart doğrulamasını yap. Hesabın açılması birkaç dakika sürebilir.

## 2. Sunucuyu oluştur
1. Oracle konsolunda: **Menü (☰) → Compute → Instances → Create instance**.
2. **Name:** `notbekcisi`
3. **Image:** *Change image* → **Canonical Ubuntu 24.04**.
4. **Shape:** *Change shape* →
   - Önce **Ampere → VM.Standard.A1.Flex**, **1 OCPU, 6 GB** dene.
   - "Out of capacity" hatası verirse **Specialty and previous generation → VM.Standard.E2.1.Micro** (1 GB RAM) seç. Bu durumda 4. adımdaki "swap" komutlarını da çalıştır.
   - Seçtiğin şeklin yanında **Always Free-eligible** yazdığından emin ol.
5. **Networking:** Program sadece dışarıya bağlanıyor, ekstra port açmaya gerek yok. Ama sunucunun bir **public IPv4** adresi olmalı, yoksa ona ssh ile bağlanamazsın.
   - Form içinde yeni ağ oluştururken "Automatically assign public IPv4 address" anahtarı kilitli kalabiliyor.
   - Bu durumda ayrı bir sekmede **☰ → Networking → Virtual cloud networks → Start VCN Wizard → Create VCN with Internet Connectivity** ile ağı oluştur (örn. `notbekcisi-vcn`).
   - Formda **Select existing virtual cloud network** → o ağ, **Select existing subnet** → adında **public subnet** geçen, sonra public IPv4 anahtarını aç.
   - Özet sayfasında `Public IPv4 address: Yes` yazdığını kontrol et.
6. **Add SSH keys:** **Generate a key pair for me** → **Save private key**'e tıkla ve dosyayı indir. Bu dosya sunucunun anahtarı; kaybetme, kimseyle paylaşma.
7. **Create**'e bas. Birkaç dakika sonra durum **Running** olur. Sayfadaki **Public IP address**'i not al.

## 3. Bilgisayarından sunucuya bağlan
İndirdiğin anahtarı yolunda Türkçe karakter olmayan bir klasöre taşı (kullanıcı klasöründeki "Ç" yine sorun çıkarabilir), örneğin `C:\anahtarlar\notbekcisi.key`.
PowerShell'de (IP'yi kendi IP'nle değiştir):

```
$key = "C:\anahtarlar\notbekcisi.key"
$ip  = "SUNUCU_IP_ADRESI"
icacls $key /inheritance:r /grant:r "$($env:USERNAME):R"
ssh -i $key ubuntu@$ip
```

`icacls` satırı anahtar dosyasını sadece senin okuyabileceğin hâle getirir; yoksa ssh "UNPROTECTED PRIVATE KEY FILE" hatası verip anahtarı kullanmaz.
İlk bağlantıda "Are you sure you want to continue connecting?" diye sorar, `yes` yaz.

## 4. Sunucuyu hazırla (sunucuda, ssh içinde)
```
sudo apt update && sudo apt -y upgrade
sudo apt install -y python3-venv libatomic1
sudo timedatectl set-timezone Europe/Istanbul
mkdir -p ~/notbekcisi
```
`timedatectl` satırı log'daki saatlerin Türkiye saatiyle yazılmasını sağlar.
`libatomic1` olmadan Playwright'ın içindeki Node.js açılmıyor ("libatomic.so.1: cannot open shared object file").

**Sadece E2.1.Micro (1 GB) seçtiysen**, Chromium'un belleği yetsin diye 2 GB swap ekle:
```
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 5. Dosyaları gönder (bilgisayarında, proje klasöründe PowerShell)
Önce bilgisayarındaki programı **Ctrl+C** ile durdur ki `notlar.json` son hâlinde kalsın. Sonra:

```
$key = "C:\anahtarlar\notbekcisi.key"
$ip  = "SUNUCU_IP_ADRESI"
scp -i $key ayarlar.py main.py obs.py telegram_bot.py not_deposu.py requirements.txt notbekcisi.service .env notlar.json "ubuntu@${ip}:~/notbekcisi/"
```

`.env` (şifren ve token) ve `notlar.json` (bilinen notlar) da gidiyor; böylece sunucu kaldığın yerden devam eder.

## 6. Programı kur (sunucuda)
```
cd ~/notbekcisi
chmod 600 .env
python3 -m venv venv
venv/bin/pip install -r requirements.txt
sudo venv/bin/playwright install-deps chromium
venv/bin/playwright install chromium
```
- `chmod 600 .env`: `.env`'yi sunucuda sadece senin kullanıcın okuyabilir.
- `venv`: Programın paketlerini sistemden ayrı bir klasöre kurar (Ubuntu, pip'in sisteme doğrudan kurmasına izin vermiyor).
- `install-deps`: Chromium'un Linux'ta ihtiyaç duyduğu sistem kütüphanelerini kurar.

## 7. Önce elle dene
```
venv/bin/python main.py
```
Telegram'a "Not Bekçisi başladı" ve captcha gelmeli. Kodu yaz, "Giriş yapıldı, takip sürüyor." gelince **Ctrl+C** ile durdur.

Bu adım aynı zamanda OBS'nin yurt dışındaki bir sunucudan girişe izin verip vermediğini de gösterir. Giriş sayfası hiç açılmıyorsa (zaman aşımı hatası) OBS yurt dışı IP'leri engelliyor olabilir; o zaman Türkiye'de bir VPS gerekir.

## 8. Sürekli çalışır hâle getir
```
sudo cp notbekcisi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now notbekcisi
```
Artık program arka planda çalışıyor. ssh'tan çıkabilir (`exit`), bilgisayarını kapatabilirsin. Sunucu yeniden başlarsa ya da program çökerse kendiliğinden tekrar başlar (her başlangıçta yine captcha gelir).

Captcha geldiyse kodu Telegram'dan yaz, gerisi aynı.

**Otomatik güncellemeler programı yeniden başlatmasın:** Ubuntu güvenlik güncellemelerini kendisi kurar
ve bazı güncellemelerden sonra (örn. `libc6`) servisleri yeniden başlatır. Bu, açık OBS oturumunu düşürür ve
sessiz saatlerde bile "Not Bekçisi başladı" mesajı attırır. Bunu kapatmak için:
```
sudo tee /etc/needrestart/conf.d/notbekcisi.conf >/dev/null <<'EOF'
$nrconf{override_rc}{qr(^notbekcisi\.service$)} = 0;
EOF
```
Güncellemeler yine kurulur; program yeni kütüphanelere bir sonraki elle yeniden başlatmada geçer.

## Günlük kullanım (sunucuda)
| Ne | Komut |
|---|---|
| Çalışıyor mu? | `systemctl status notbekcisi` |
| Log'u izle | `tail -f ~/notbekcisi/notbekcisi.log` (çıkmak için Ctrl+C) |
| Durdur | `sudo systemctl stop notbekcisi` |
| Yeniden başlat | `sudo systemctl restart notbekcisi` |

**Kodu değiştirdiğinde:** Değişen dosyayı 5. adımdaki gibi `scp` ile gönder, sonra `sudo systemctl restart notbekcisi`.

## Sorun giderme
- **"Out of capacity":** Seçtiğin şekil o an dolu. Birkaç saat sonra tekrar dene ya da E2.1.Micro'yu seç.
- **ssh bağlanmıyor:** IP doğru mu, sunucu "Running" mi? Kullanıcı adı `ubuntu` olmalı.
- **Sunucu kendiliğinden durmuş:** Büyük ihtimalle "boşta kalma" kuralı. Konsoldan **Start**'a bas. Program servis olarak kurulu olduğu için sunucuyla birlikte başlar.
- **Tarayıcı açılmıyor / "missing dependencies":** `sudo venv/bin/playwright install-deps chromium` adımını tekrar çalıştır.
