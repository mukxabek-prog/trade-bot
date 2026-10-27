import asyncio
import html
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.getenv("CHANNEL", "@BLOXFRUIT_UZBEKISTAN_SHOP")        # majburiy obuna
POST_CHANNEL = os.getenv("POST_CHANNEL", "@roblox_accunt_savdo")    # e'lonlar chiqadigan kanal
CHANNEL_URL = f"https://t.me/{CHANNEL.lstrip('@')}"

# O'yinlar ro'yxati (nomini shu yerdan o'zgartirasiz)
GAMES = [
    ("🧠", "Steal a Brainrot"),
    ("🍎", "Blox Fruit"),
    ("🌊", "Escape Tsunami"),
    ("🥚", "Steal an Egg"),
]

MAX_PHOTOS = 5
MENU_BTN = "📝 Akkaunt e'lon berish"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


class Post(StatesGroup):
    game = State()
    nick = State()
    photos = State()
    info = State()
    confirm = State()


# ---------- Tugmalar (primary=ko'k, success=yashil, danger=qizil) ----------
def sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_URL, style="primary")],
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check", style="success")],
    ])


def main_menu() -> ReplyKeyboardMarkup:
    # Pastdagi doimiy menyu
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MENU_BTN, style="success")]],
        resize_keyboard=True,
    )


def games_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{emo} {name}", callback_data=f"game:{i}", style="primary")]
        for i, (emo, name) in enumerate(GAMES)
    ]
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")],
    ])


def photos_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Rasmlar tayyor", callback_data="photos_done", style="success")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")],
    ])


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 E'lon berish", callback_data="publish", style="success")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")],
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
MENU_TEXT = "✅ Obuna tasdiqlandi!\n\nPastdagi menyudan bo'limni tanlang 👇"


# ---------- Start va obuna ----------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if await is_subscribed(message.from_user.id):
        await message.answer(MENU_TEXT, reply_markup=main_menu())
    else:
        await message.answer(SUB_TEXT, reply_markup=sub_kb())


@dp.callback_query(F.data == "check")
async def check(call: CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer(MENU_TEXT, reply_markup=main_menu())
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)


@dp.chat_member()
async def on_join(event: ChatMemberUpdated):
    if (event.chat.username or "").lower() != CHANNEL.lstrip("@").lower():
        return
    if event.new_chat_member.status in ("member", "administrator", "creator"):
        try:
            await bot.send_message(
                event.new_chat_member.user.id, MENU_TEXT, reply_markup=main_menu()
            )
        except Exception as e:
            logging.info("Xabar yuborib bo'lmadi: %s", e)


# ---------- Bekor qilish ----------
@dp.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu())


# ---------- 1) O'yinni tanlash ----------
@dp.message(F.text == MENU_BTN)
async def post_start(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await message.answer(SUB_TEXT, reply_markup=sub_kb())
        return
    await state.clear()
    await state.set_state(Post.game)
    await message.answer("🎮 Qaysi o'yin akkaunti?", reply_markup=games_kb())


@dp.callback_query(Post.game, F.data.startswith("game:"))
async def pick_game(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":")[1])
    emo, name = GAMES[idx]
    await state.update_data(game=f"{emo} {name}", photos=[])
    await state.set_state(Post.nick)
    await call.message.edit_text(
        f"🎮 O'yin: <b>{html.escape(name)}</b>\n\n👤 Akkaunt <b>nikini</b> yozing:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


# ---------- 2) Nik ----------
@dp.message(Post.nick, F.text)
async def get_nick(message: Message, state: FSMContext):
    await state.update_data(nick=message.text.strip()[:64])
    await state.set_state(Post.photos)
    await message.answer(
        f"🖼 Akkaunt rasmlarini yuboring (kamida 1 ta, ko'pi bilan {MAX_PHOTOS} ta).\n"
        "Hammasini yuborib bo'lgach «✅ Rasmlar tayyor» ni bosing.",
        reply_markup=photos_kb(),
    )


# ---------- 3) Rasmlar ----------
@dp.message(Post.photos, F.photo)
async def get_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"⚠️ Eng ko'pi bilan {MAX_PHOTOS} ta rasm. «✅ Rasmlar tayyor» ni bosing.")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"✅ Rasm qabul qilindi ({len(photos)}/{MAX_PHOTOS})", reply_markup=photos_kb())


@dp.message(Post.photos)
async def photo_wrong(message: Message):
    await message.answer("⚠️ Iltimos, rasm yuboring.")


@dp.callback_query(Post.photos, F.data == "photos_done")
async def photos_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos"):
        await call.answer("❌ Kamida 1 ta rasm yuborish majburiy!", show_alert=True)
        return
    await state.set_state(Post.info)
    await call.message.answer(
        "📄 Endi akkaunt haqida <b>ma'lumot</b> yozing:\n"
        "(narxi, level, nimalari bor, qo'shimcha gaplar...)",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


# ---------- 4) Ma'lumot ----------
def build_caption(data: dict, user) -> str:
    seller = f'<a href="tg://user?id={user.id}">{html.escape(user.full_name)}</a>'
    if user.username:
        seller = f"@{user.username}"
    info = html.escape(data["info"])
    caption = (
        "🔥 <b>YANGI AKKAUNT SOTUVDA!</b> 🔥\n\n"
        f"🎮 <b>O'yin:</b> {html.escape(data['game'])}\n\n"
        f"👤 <b>Nik:</b> <code>{html.escape(data['nick'])}</code>\n\n"
        f"📄 <b>Ma'lumot:</b>\n{info}\n\n"
        f"🧑‍💼 <b>Sotuvchi:</b> {seller}\n\n"
        "💬 Sotib olish uchun sotuvchiga yozing!"
    )
    if len(caption) > 1024:  # Telegram caption limiti
        over = len(caption) - 1020
        info = html.escape(data["info"][: max(0, len(data["info"]) - over - 10)]) + "..."
        caption = (
            "🔥 <b>YANGI AKKAUNT SOTUVDA!</b> 🔥\n\n"
            f"🎮 <b>O'yin:</b> {html.escape(data['game'])}\n\n"
            f"👤 <b>Nik:</b> <code>{html.escape(data['nick'])}</code>\n\n"
            f"📄 <b>Ma'lumot:</b>\n{info}\n\n"
            f"🧑‍💼 <b>Sotuvchi:</b> {seller}"
        )
    return caption[:1024]


def build_media(data: dict, user) -> list[InputMediaPhoto]:
    caption = build_caption(data, user)
    media = []
    for i, fid in enumerate(data["photos"]):
        if i == 0:
            media.append(InputMediaPhoto(media=fid, caption=caption, parse_mode="HTML"))
        else:
            media.append(InputMediaPhoto(media=fid))
    return media


@dp.message(Post.info, F.text)
async def get_info(message: Message, state: FSMContext):
    await state.update_data(info=message.text.strip()[:700])
    data = await state.get_data()
    await state.set_state(Post.confirm)

    await message.answer("👀 E'loningiz mana shunday ko'rinadi:")
    await bot.send_media_group(message.chat.id, build_media(data, message.from_user))
    await message.answer("Kanalga chiqaraymi?", reply_markup=confirm_kb())


# ---------- 5) Kanalga e'lon berish ----------
@dp.callback_query(Post.confirm, F.data == "publish")
async def publish(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_media_group(POST_CHANNEL, build_media(data, call.from_user))
    except Exception as e:
        logging.error("E'lon berishda xato: %s", e)
        await call.answer("❌ Xatolik! Bot e'lon kanalida admin ekanini tekshiring.", show_alert=True)
        return
    await state.clear()
    await call.message.delete()
    await call.message.answer(
        f"🚀 E'loningiz {POST_CHANNEL} kanaliga joylandi!", reply_markup=main_menu()
    )


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
