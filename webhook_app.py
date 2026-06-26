# 🧠 Steal a Brainrot Trade Bot — Render (bepul) uchun

Bu versiya Render.com'ning **bepul** tarifida 24/7 ishlashi uchun moslangan:

- ❌ SQLite emas → ✅ **PostgreSQL** (chunki Render bepul tarifida fayl
  tizimi vaqtinchalik — servis uxlab qolsa/qayta ishga tushsa, SQLite fayli
  o'chib ketardi va barcha coin/itemlar yo'qolardi).
- ❌ Polling emas → ✅ **Webhook** (Render bepul "Web Service" portda HTTP
  so'rovlarini kutib turishni talab qiladi; webhook bu shartni o'zi
  bajaradi, polling esa hech qaysi portni ochmaydi).

> ⚠️ Coin va brainrotlar **100% virtual** — real pul/Robux bilan aloqasi yo'q.

---

## ⚠️ Bepul tarifning 2 ta cheklovi (oldindan bilib qo'ying)

1. **Spin-down (uxlash):** 15 daqiqa hech kim yozmasa, bot "uxlab qoladi".
   Keyingi xabarga javob berishi ~30-60 soniya kechikadi (birinchi xabardan
   keyin tezlashadi). Ma'lumotlar Postgres'da bo'lgani uchun **yo'qolmaydi**,
   faqat javob sekinroq keladi. Buni butunlay yo'qotish uchun pastdagi
   "Botni doim uyg'oq saqlash" bo'limiga qarang.
2. **Render'ning bepul Postgres'i 30 kundan keyin o'chiriladi** (yana 14 kun
   "grace period" beriladi, keyin butunlay o'chadi). Agar botni uzoq muddat
   (30 kundan ko'p) ishlatmoqchi bo'lsangiz, ikki yo'l bor:
   - Har ~30 kunda Render'da yangi bepul Postgres yarating va `DATABASE_URL`
     ni yangilang (eski ma'lumotlar shu paytda yo'qoladi), **yoki**
   - **Tavsiya etiladi:** o'rniga muddatsiz bepul Postgres beruvchi
     [Neon.tech](https://neon.tech) yoki [Supabase](https://supabase.com)
     dan foydalaning — ular ham bepul, lekin 30 kunda o'chmaydi. Faqat
     Render Postgres yaratishni o'tkazib yuborib, Neon/Supabase'dan olgan
     connection string'ni to'g'ridan-to'g'ri `DATABASE_URL` qilib qo'yasiz.

---

## 1. Bot tokenini olish

1. Telegramda **@BotFather**ga `/newbot` yuboring.
2. Nom va username tanlang (username `bot` bilan tugashi kerak).
3. Tokenni saqlab qo'ying — `123456789:AAEh...` ko'rinishida bo'ladi.

## 2. Kodni GitHub'ga joylash

Render Git repodan deploy qiladi, shu sababli avval shu fayllarni GitHub'ga
yuklashingiz kerak:

```bash
cd brainrot_trade_bot
git init
git add .
git commit -m "Steal a Brainrot Trade Bot"
git branch -M main
git remote add origin https://github.com/SIZNING_USERNAME/brainrot-trade-bot.git
git push -u origin main
```

(GitHub'da avval bo'sh repo yaratib olishingiz kerak: github.com/new)

## 3. Render'da deploy qilish — eng oson yo'l (Blueprint)

1. [render.com](https://render.com)da ro'yxatdan o'ting (karta kerak emas).
2. Dashboard'da **New → Blueprint** ni bosing.
3. GitHub repongizni ulang — Render `render.yaml` faylini avtomatik topadi.
4. Render sizdan **BOT_TOKEN** qiymatini so'raydi — BotFather bergan
   tokenni kiriting.
5. **Deploy Blueprint** tugmasini bosing.

Render avtomatik ravishda:
- bepul PostgreSQL bazasi (`brainrot-db`),
- bepul web-servis (botning o'zi),

yaratadi va ularni bir-biriga ulaydi (`DATABASE_URL` avtomatik beriladi).

Deploy tugagach, Render servisingizga `https://brainrot-trade-bot-xxxx.onrender.com`
kabi manzil beradi — bu avtomatik `RENDER_EXTERNAL_URL` orqali botga
yetkaziladi va webhook shu manzilga o'rnatiladi. Hech narsa qo'lda qilish
shart emas.

Telegramda botingizni topib `/start` bosing — ishlayotganini ko'rasiz! 🎉

### Agar Neon/Supabase'dan Postgres ishlatmoqchi bo'lsangiz

`render.yaml` dagi `databases:` qismini o'chirib tashlang va
`DATABASE_URL` qatorini quyidagicha o'zgartiring:

```yaml
envVars:
  - key: BOT_TOKEN
    sync: false
  - key: DATABASE_URL
    sync: false   # deploy paytida Render Neon/Supabase'dan olgan connection string'ni so'raydi
```

## 4. Render'da deploy qilish — qo'lda (Blueprint ishlatmasdan)

1. Render Dashboard > **New → PostgreSQL** > Free tarifni tanlang > yaratib oling.
2. Render Dashboard > **New → Web Service** > GitHub repongizni ulang.
3. Sozlamalar:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python webhook_app.py`
   - **Instance Type:** Free
4. **Environment** bo'limida quyidagilarni qo'shing:
   - `BOT_TOKEN` = BotFather bergan token
   - `DATABASE_URL` = 2-qadamda yaratgan Postgres'ning "Internal Database URL"si
     (Postgres servisining "Connections" bo'limidan ko'chirib olinadi)
5. **Create Web Service** tugmasini bosing.

---

## Lokal kompyuteringizda sinab ko'rish (polling rejimi)

Webhook uchun ochiq internetga chiqadigan HTTPS manzil kerak, shu sababli
lokalda odatda **polling** (`bot.py`) ishlatiladi:

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

export BOT_TOKEN="123456789:AAEh..."
export DATABASE_URL="postgresql://user:pass@host:port/dbname"  # Render/Neon'dan oling

python3 bot.py
```

> Eslatma: lokal test va production bir xil `DATABASE_URL`ni ishlatsa,
> ikkalasi bir xil coin/inventarni ko'radi — bu normal, chunki ma'lumotlar
> botning o'zida emas, Postgres'da saqlanadi.

---

## Botni doim uyg'oq saqlash (ixtiyoriy)

Spin-down tufayli birinchi xabarga javob sekinlashishini istamasangiz, bepul
[UptimeRobot](https://uptimerobot.com) yoki [cron-job.org](https://cron-job.org)
orqali botning manzilini (masalan `https://brainrot-trade-bot-xxxx.onrender.com/`)
har 5-10 daqiqada "ping" qilib turing — bu Render'ga servis "band" ekanini
bildiradi va u uxlab qolmaydi. (Ma'lumotlar baribir yo'qolmaydi, bu faqat
tezlik uchun.)

---

## Fayllar tuzilishi

```
brainrot_trade_bot/
├── bot.py            # buyruqlar/handlerlar (router) — lokal polling uchun ham ishga tushadi
├── webhook_app.py     # Render'da ishga tushiriladigan webhook + aiohttp server
├── config.py          # token, DATABASE_URL, webhook sozlamalari
├── data.py            # brainrot katalogi: nom, rarity, narx
├── db.py              # PostgreSQL (asyncpg) funksiyalari
├── keyboards.py        # inline tugmalar
├── render.yaml         # Render Blueprint (bir click deploy)
└── requirements.txt
```

## Sozlash / o'zgartirish

- **Brainrot ro'yxati, narxlar, rarity** — `data.py` dagi `BRAINROTS`.
- **Boshlang'ich balans, kunlik bonus** — `config.py` dagi `STARTING_BALANCE`,
  `DAILY_BONUS_MIN/MAX`.
- **Do'kon konveyerida nechta tovar chiqishi** — `config.py` dagi `SHOP_SLOTS`.

## Muhim cheklov: `/trade` haqida

Telegram bot faqat **avval o'ziga `/start` bosgan** foydalanuvchiga xabar
yubora oladi. `/trade @username ...` ishlashi uchun ikkala tomon ham avval
botga kamida bir marta `/start` bosgan bo'lishi kerak.

## Buyruqlar ro'yxati

| Buyruq | Tavsif |
|---|---|
| `/start` | Ro'yxatdan o'tish, boshlang'ich coin olish |
| `/help` | Yordam |
| `/balance` | Balansni ko'rish |
| `/shop` | Do'kondan brainrot sotib olish |
| `/inventory` | Sizdagi brainrotlar ro'yxati |
| `/sell <id> <narx>` | Itemni umumiy marketga qo'yish |
| `/market` | Marketdagi itemlarni ko'rish/sotib olish |
| `/mylistings` | O'z e'lonlaringiz (bekor qilish mumkin) |
| `/trade <@user> <id> <narx>` | To'g'ridan-to'g'ri trade taklifi |
| `/daily` | Kunlik bonus coin |
| `/top` | Eng boy o'yinchilar reytingi |

---

Muammo chiqsa — Render Dashboard > sizning servis > **Logs** bo'limida
xato xabarlarini ko'rishingiz mumkin (eng tez-tez uchraydigani: noto'g'ri
yoki bo'sh `BOT_TOKEN`/`DATABASE_URL`).
