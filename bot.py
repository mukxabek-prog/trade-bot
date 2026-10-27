import asyncio
import html
import logging
import os
import time
from datetime import datetime

from aiohttp import ClientSession, ClientTimeout, web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
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
    ReplyKeyboardRemove,
)
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.getenv("DB_NAME", "robloxbot")
CHANNEL = os.getenv("CHANNEL", "@BLOXFRUIT_UZBEKISTAN_SHOP")        # majburiy obuna
POST_CHANNEL = os.getenv("POST_CHANNEL", "@roblox_accunt_savdo")    # e'lonlar kanali
GARANT = os.getenv("GARANT", "@kazen_rbx")
CHANNEL_URL = f"https://t.me/{CHANNEL.lstrip('@')}"

# Adminlar: limitlar (7 kun va 3 ta e'lon) ularga ishlamaydi
ADMIN_IDS = {8789323396}
ADMIN_IDS |= {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

# Render o'zi beradigan tashqi manzil (uxlab qolmaslik uchun ping)
SELF_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("SELF_URL", "")
PING_SECONDS = int(os.getenv("PING_SECONDS", "300"))  # har 5 daqiqada

COOLDOWN_DAYS = 7
MAX_ACTIVE = 3
MAX_PHOTOS = 5

GAMES = [
    ("🧠", "Steal a Brainrot"),
    ("🍎", "Blox Fruit"),
    ("🌊", "Escape Tsunami"),
    ("🥚", "Steal an Egg"),
]

POST_BTN = "📝 Akkaunt e'lon berish"
MY_BTN = "🗂 E'lonlarim"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ---------- Baza (MongoDB) ----------
mongo = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=10000)
posts_col = mongo[DB_NAME]["posts"]


async def db_init() -> None:
    await posts_col.create_index([("user_id", 1), ("active", 1)])
    await posts_col.create_index([("user_id", 1), ("created_at", -1)])


async def db_add_post(user_id: int, msg_ids: list[int], game: str, nick: str) -> None:
    await posts_col.insert_one({
        "user_id": user_id,
        "msg_ids": msg_ids,
        "game": game,
        "nick": nick,
        "created_at": int(time.time()),
        "active": True,
    })


async def db_active_posts(user_id: int) -> list[dict]:
    cursor = posts_col.find({"user_id": user_id, "active": True}).sort("created_at", -1)
    return await cursor.to_list(length=50)


async def db_last_post_time(user_id: int) -> int:
    doc = await posts_col.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    return doc["created_at"] if doc else 0


async def db_get_post(post_id: str):
    try:
        return await posts_col.find_one({"_id": ObjectId(post_id)})
    except Exception:
        return None


async def db_deactivate(post_id) -> None:
    await posts_col.update_one({"_id": post_id}, {"$set": {"active": False}})


async def check_limits(user_id: int) -> tuple[bool, str]:
    """E'lon berish mumkinmi? (True, '') yoki (False, sabab). Adminlarga cheklov yo'q."""
    if user_id in ADMIN_IDS:
        return True, ""

    last = await db_last_post_time(user_id)
    wait = last + COOLDOWN_DAYS * 86400 - int(time.time())
    if wait > 0:
        d, h = wait // 86400, (wait % 86400) // 3600
        return False, (
            f"⏳ E'lonni har {COOLDOWN_DAYS} kunda faqat 1 marta berish mumkin.\n\n"
            f"Keyingi e'lon: <b>{d} kun {h} soatdan</b> keyin."
        )

    if len(await db_active_posts(user_id)) >= MAX_ACTIVE:
        return False, (
            f"⚠️ Kanalda sizning {MAX_ACTIVE} ta faol e'loningiz bor (maksimal).\n\n"
            f"Yangi e'lon berish uchun «{MY_BTN}» orqali eskisini o'chiring."
        )
    return True, ""


# ---------- Holatlar ----------
class Post(StatesGroup):
    game = State()
    nick = State()
    trade_ask = State()
    trade_what = State()
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
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=POST_BTN, style="success")],
            [KeyboardButton(text=MY_BTN, style="primary")],
        ],
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


def trade_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data="trade:yes", style="success"),
            InlineKeyboardButton(text="🚫 Yo'q", callback_data="trade:no", style="danger"),
        ],
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


def delete_kb(post_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Kanaldan o'chirish", callback_data=f"del:{post_id}", style="danger")],
    ])


# ---------- Obuna ----------
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
            await bot.send_message(event.new_chat_member.user.id, MENU_TEXT, reply_markup=main_menu())
        except Exception as e:
            logging.info("Xabar yuborib bo'lmadi: %s", e)


@dp.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu())


# ---------- E'lonlarim (o'chirish) ----------
@dp.message(F.text == MY_BTN)
async def my_posts(message: Message, state: FSMContext):
    await state.clear()
    if not await is_subscribed(message.from_user.id):
        await message.answer(SUB_TEXT, reply_markup=sub_kb())
        return
    posts = await db_active_posts(message.from_user.id)
    if not posts:
        await message.answer("📭 Kanalda sizning faol e'loningiz yo'q.")
        return
    limit_text = "∞" if message.from_user.id in ADMIN_IDS else str(MAX_ACTIVE)
    await message.answer(f"🗂 Faol e'lonlaringiz: <b>{len(posts)}/{limit_text}</b>", parse_mode="HTML")
    for p in posts:
        date = datetime.fromtimestamp(p["created_at"]).strftime("%d.%m.%Y %H:%M")
        await message.answer(
            f"🎮 {html.escape(p['game'])}\n👤 Nik: <code>{html.escape(p['nick'])}</code>\n🕒 {date}",
            parse_mode="HTML",
            reply_markup=delete_kb(str(p["_id"])),
        )


@dp.callback_query(F.data.startswith("del:"))
async def delete_post(call: CallbackQuery):
    post = await db_get_post(call.data.split(":", 1)[1])
    if not post or post["user_id"] != call.from_user.id or not post["active"]:
        await call.answer("Bu e'lon topilmadi yoki allaqachon o'chirilgan.", show_alert=True)
        return
    try:
        await bot.delete_messages(POST_CHANNEL, post["msg_ids"])
    except Exception as e:
        # Kanaldan qo'lda o'chirilgan bo'lishi mumkin, baribir bazada yopamiz
        logging.warning("Kanaldan o'chirishda xato: %s", e)
    await db_deactivate(post["_id"])
    await call.message.edit_text("🗑 E'lon kanaldan o'chirildi.")
    await call.answer()


# ---------- 1) O'yin ----------
@dp.message(F.text == POST_BTN)
async def post_start(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await message.answer(SUB_TEXT, reply_markup=sub_kb())
        return
    await state.clear()
    ok, reason = await check_limits(message.from_user.id)
    if not ok:
        await message.answer(reason, parse_mode="HTML")
        return

    # Pastdagi menyuni yashiramiz (belgi xabarni darhol o'chiramiz)
    tmp = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await tmp.delete()
    except Exception:
        pass

    await state.set_state(Post.game)
    await message.answer("🎮 Qaysi o'yin akkaunti?", reply_markup=games_kb())


@dp.callback_query(Post.game, F.data.startswith("game:"))
async def pick_game(call: CallbackQuery, state: FSMContext):
    emo, name = GAMES[int(call.data.split(":")[1])]
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
    await state.set_state(Post.trade_ask)
    await message.answer("🔄 Akkaunt <b>trade</b> qilinadimi?", parse_mode="HTML", reply_markup=trade_kb())


# ---------- 3) Trade ----------
@dp.callback_query(Post.trade_ask, F.data == "trade:yes")
async def trade_yes(call: CallbackQuery, state: FSMContext):
    await state.update_data(trade=True)
    await state.set_state(Post.trade_what)
    await call.message.edit_text(
        "🔄 Nimaga trade qilinadi?\n(masalan: akkauntga, pet, mevaga...)",
        reply_markup=cancel_kb(),
    )


@dp.callback_query(Post.trade_ask, F.data == "trade:no")
async def trade_no(call: CallbackQuery, state: FSMContext):
    await state.update_data(trade=False, trade_for="")
    await ask_photos(call.message, state, edit=True)


@dp.message(Post.trade_what, F.text)
async def trade_what(message: Message, state: FSMContext):
    await state.update_data(trade_for=message.text.strip()[:100])
    await ask_photos(message, state)


async def ask_photos(message: Message, state: FSMContext, edit: bool = False):
    await state.set_state(Post.photos)
    text = (
        f"🖼 Akkaunt rasmlarini yuboring (kamida 1 ta, ko'pi bilan {MAX_PHOTOS} ta).\n"
        "Hammasini yuborib bo'lgach «✅ Rasmlar tayyor» ni bosing."
    )
    if edit:
        await message.edit_text(text, reply_markup=photos_kb())
    else:
        await message.answer(text, reply_markup=photos_kb())


# ---------- 4) Rasmlar ----------
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


# ---------- E'lon matni ----------
def build_caption(data: dict, user) -> str:
    if user.username:
        seller = f"@{user.username}"
    else:
        seller = f'<a href="tg://user?id={user.id}">{html.escape(user.full_name)}</a>'

    if data.get("trade"):
        trade = f"✅ Ha — {html.escape(data.get('trade_for', ''))}"
    else:
        trade = "🚫 Yo'q"

    def make(info: str) -> str:
        return (
            "🔥 <b>YANGI AKKAUNT SOTUVDA!</b> 🔥\n\n"
            f"🎮 <b>O'yin:</b> {html.escape(data['game'])}\n\n"
            f"👤 <b>Nik:</b> <code>{html.escape(data['nick'])}</code>\n\n"
            f"🔄 <b>Trade:</b> {trade}\n\n"
            f"📄 <b>Ma'lumot:</b>\n{html.escape(info)}\n\n"
            f"🧑‍💼 <b>Sotuvchi:</b> {seller}\n\n"
            f"🛡 <b>Garant:</b> {GARANT}\n"
            "⚠️ Aldanib qolmaslik uchun savdoni faqat garant orqali qiling!"
        )

    info = data["info"]
    caption = make(info)
    while len(caption) > 1024 and info:  # Telegram caption limiti
        info = info[:-30]
        caption = make(info.rstrip() + "...")
    return caption


def build_media(data: dict, user) -> list[InputMediaPhoto]:
    caption = build_caption(data, user)
    media = []
    for i, fid in enumerate(data["photos"]):
        if i == 0:
            media.append(InputMediaPhoto(media=fid, caption=caption, parse_mode="HTML"))
        else:
            media.append(InputMediaPhoto(media=fid))
    return media


# ---------- 5) Ma'lumot va ko'rib chiqish ----------
@dp.message(Post.info, F.text)
async def get_info(message: Message, state: FSMContext):
    await state.update_data(info=message.text.strip()[:700])
    data = await state.get_data()
    await state.set_state(Post.confirm)
    await message.answer("👀 E'loningiz mana shunday ko'rinadi:")
    await bot.send_media_group(message.chat.id, build_media(data, message.from_user))
    await message.answer("Kanalga chiqaraymi?", reply_markup=confirm_kb())


# ---------- 6) Kanalga e'lon berish ----------
@dp.callback_query(Post.confirm, F.data == "publish")
async def publish(call: CallbackQuery, state: FSMContext):
    # Limitni yana bir bor tekshiramiz (ikki marta bosib yuborishdan himoya)
    ok, reason = await check_limits(call.from_user.id)
    if not ok:
        await state.clear()
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(reason, parse_mode="HTML", reply_markup=main_menu())
        return

    data = await state.get_data()
    try:
        msgs = await bot.send_media_group(POST_CHANNEL, build_media(data, call.from_user))
    except Exception as e:
        logging.error("E'lon berishda xato: %s", e)
        await call.answer("❌ Xatolik! Bot e'lon kanalida admin ekanini tekshiring.", show_alert=True)
        return

    await db_add_post(call.from_user.id, [m.message_id for m in msgs], data["game"], data["nick"])
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass

    if call.from_user.id in ADMIN_IDS:
        tail = "Admin sifatida sizda cheklov yo'q."
    else:
        tail = f"Keyingi e'lonni {COOLDOWN_DAYS} kundan keyin berishingiz mumkin."
    await call.message.answer(
        f"🚀 E'loningiz {POST_CHANNEL} kanaliga joylandi!\n\n{tail}",
        reply_markup=main_menu(),
    )


# ---------- Render: web server va uxlab qolishdan himoya ----------
async def health(request):
    return web.Response(text="Bot ishlayapti")


async def keep_alive():
    """Har PING_SECONDS da o'z manzilini ping qiladi, Render uxlatib qo'ymaydi."""
    if not SELF_URL:
        logging.warning(
            "RENDER_EXTERNAL_URL topilmadi. Environment'ga SELF_URL=https://sizning-bot.onrender.com qo'shing."
        )
        return
    await asyncio.sleep(30)
    async with ClientSession(timeout=ClientTimeout(total=20)) as session:
        while True:
            try:
                async with session.get(SELF_URL) as resp:
                    logging.info("Ping: %s", resp.status)
            except Exception as e:
                logging.warning("Ping xatosi: %s", e)
            await asyncio.sleep(PING_SECONDS)


async def main():
    await mongo.admin.command("ping")
    logging.info("MongoDB ulandi")
    await db_init()

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()

    ping_task = asyncio.create_task(keep_alive())  # noqa: F841 (havolani saqlab turamiz)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
