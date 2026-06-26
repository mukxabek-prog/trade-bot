"""
Render.com kabi BEPUL (free tier) hosting xizmatlarida ishlatish uchun
webhook rejimidagi ishga tushirish skripti.

NEGA POLLING EMAS, WEBHOOK?
Render'ning bepul "Web Service" tarifi servisingiz biror portda HTTP
so'rovlarini kutib turishini talab qiladi (aks holda deploy muvaffaqiyatsiz
bo'ladi yoki servis "uxlab qoladi"). Oddiy polling (bot.py) hech qanday HTTP
portini ochmaydi, shu sababli Render buni "web service" deb tanimaydi.
Webhook esa — Telegram yangilanishlarni to'g'ridan-to'g'ri HTTP POST sifatida
yuboradi, demak bizning servis tabiiy ravishda portda "tinglab" turadi.

Lokal kompyuteringizda sinab ko'rish uchun shunchaki bot.py (polling)
faylidan foydalaning — webhook uchun ochiq internetga chiqadigan HTTPS manzil
kerak, shu sababli lokalda odatda ishlatilmaydi.
"""

import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import config
import db
from bot import router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("webhook_app")


async def health(request: web.Request) -> web.Response:
    """Render va UptimeRobot kabi xizmatlar shu yo'lni "tirik" ekanini
    tekshirish (health check) uchun chaqiradi."""
    return web.Response(text="🧠 Brainrot Trade Bot ishlayapti ✅")


async def on_startup(bot: Bot):
    await db.init_db()

    webhook_url = config.WEBHOOK_HOST.rstrip("/") + config.WEBHOOK_PATH
    current = await bot.get_webhook_info()
    if current.url != webhook_url:
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
    log.info("Webhook o'rnatildi: %s", webhook_url)


async def on_shutdown(bot: Bot):
    await db.close_db()


def create_app() -> web.Application:
    if not config.BOT_TOKEN or config.BOT_TOKEN == "BOT_TOKEN_NI_BU_YERGA_QOYING":
        raise RuntimeError(
            "BOT_TOKEN o'rnatilmagan! Render Dashboard > Environment bo'limida "
            "BOT_TOKEN muhit o'zgaruvchisini @BotFather bergan token bilan to'ldiring."
        )
    if not config.WEBHOOK_HOST:
        raise RuntimeError(
            "WEBHOOK_HOST aniqlanmadi. Render odatda buni RENDER_EXTERNAL_URL "
            "orqali avtomatik beradi. Agar baribir ishlamasa, Render "
            "Dashboard > Environment bo'limiga qo'lda WEBHOOK_HOST="
            "https://sizning-servis-nomi.onrender.com qo'shing."
        )

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=config.PORT)
