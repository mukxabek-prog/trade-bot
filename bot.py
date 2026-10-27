import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.getenv("CHANNEL", "@BLOXFRUIT_UZBEKISTAN_SHOP")
CHANNEL_URL = f"https://t.me/{CHANNEL.lstrip('@')}"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ---------- Tugmalar (style: primary=ko'k, success=yashil, danger=qizil) ----------
def sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_URL, style="primary")],
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check", style="success")],
    ])


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Akkaunt e'lon berish", callback_data="post_account", style="success")],
        [InlineKeyboardButton(text="📢 Bizning kanal", url=CHANNEL_URL, style="primary")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu", style="danger")],
    ])


# ---------- Obunani tekshirish ----------
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.warning("Obunani tekshirib bo'lmadi: %s", e)
        return False


SUB_TEXT = (
    "👋 Botdan foydalanish uchun avval kanalimizga obuna bo'ling.\n\n"
    "Obuna bo'lgach, bot sizni avtomatik tasdiqlaydi."
)
MENU_TEXT = "✅ Obuna tasdiqlandi!\n\nBo'limni tanlang:"


# ---------- Handlerlar ----------
@dp.message(CommandStart())
async def start(message: Message):
    if await is_subscribed(message.from_user.id):
        await message.answer(MENU_TEXT, reply_markup=menu_kb())
    else:
        await message.answer(SUB_TEXT, reply_markup=sub_kb())


@dp.callback_query(F.data == "check")
async def check(call: CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.edit_text(MENU_TEXT, reply_markup=menu_kb())
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)


@dp.callback_query(F.data == "menu")
async def menu(call: CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        await call.message.edit_text(SUB_TEXT, reply_markup=sub_kb())
        return
    await call.message.edit_text("Bo'limni tanlang:", reply_markup=menu_kb())


@dp.callback_query(F.data == "post_account")
async def post_account(call: CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        await call.message.edit_text(SUB_TEXT, reply_markup=sub_kb())
        return
    await call.message.edit_text(
        "📝 Akkaunt e'lon berish bo'limi.\n\nTez orada qo'shiladi...",
        reply_markup=back_kb(),
    )


# Foydalanuvchi kanalga qo'shilganda avtomatik tasdiqlash
# (bot kanalda ADMIN bo'lishi shart)
@dp.chat_member()
async def on_join(event: ChatMemberUpdated):
    if (event.chat.username or "").lower() != CHANNEL.lstrip("@").lower():
        return
    if event.new_chat_member.status in ("member", "administrator", "creator"):
        try:
            await bot.send_message(
                event.new_chat_member.user.id, MENU_TEXT, reply_markup=menu_kb()
            )
        except Exception as e:
            logging.info("Xabar yuborib bo'lmadi: %s", e)


# ---------- Render uchun web server ----------
async def health(request):
    return web.Response(text="Bot ishlayapti")


async def main():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
