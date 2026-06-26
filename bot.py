import os
import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────
# ENV
# ─────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))

REQUIRED_CHANNEL = "@roblox_uz"   # ← kanalingiz

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ─────────────────────────────────────────────
# DATABASE  (SQLite – Render free tier uchun)
# ─────────────────────────────────────────────
DB_PATH = "bot_data.db"

def db_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    con = db_conn()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            roblox_nick TEXT,
            roblox_id   TEXT,
            balance     INTEGER DEFAULT 0,
            registered  TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            roblox_id   TEXT,
            amount      INTEGER,
            price       INTEGER,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            offer       TEXT,
            want        TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            item_name   TEXT,
            price_robux INTEGER,
            status      TEXT DEFAULT 'active',
            created_at  TEXT
        )
    """)

    con.commit()
    con.close()

def get_user(user_id: int):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def upsert_user(user_id, username, roblox_nick=None, roblox_id=None):
    con = db_conn()
    cur = con.cursor()
    existing = get_user(user_id)
    if existing:
        if roblox_nick:
            cur.execute("UPDATE users SET roblox_nick=?, roblox_id=?, username=? WHERE user_id=?",
                        (roblox_nick, roblox_id, username, user_id))
        else:
            cur.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
    else:
        cur.execute(
            "INSERT INTO users (user_id, username, roblox_nick, roblox_id, balance, registered) VALUES (?,?,?,?,0,?)",
            (user_id, username, roblox_nick, roblox_id, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
    con.commit()
    con.close()

def get_balance(user_id):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def add_order(user_id, username, roblox_nick, roblox_id, amount, price):
    con = db_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO orders (user_id,username,roblox_nick,roblox_id,amount,price,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, username, roblox_nick, roblox_id, amount, price, "pending", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    oid = cur.lastrowid
    con.commit()
    con.close()
    return oid

def set_order_status(oid, status):
    con = db_conn()
    cur = con.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    if status == "approved":
        cur.execute("SELECT user_id, amount FROM orders WHERE id=?", (oid,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (row[1], row[0]))
    con.commit()
    con.close()

def get_order(oid):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()
    return row

def add_trade(user_id, username, roblox_nick, offer, want):
    con = db_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO trades (user_id,username,roblox_nick,offer,want,status,created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, username, roblox_nick, offer, want, "active", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def get_active_trades():
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT * FROM trades WHERE status='active' ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    con.close()
    return rows

def add_sale(user_id, username, roblox_nick, item_name, price_robux):
    con = db_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sales (user_id,username,roblox_nick,item_name,price_robux,status,created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, username, roblox_nick, item_name, price_robux, "active", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    sid = cur.lastrowid
    con.commit()
    con.close()
    return sid

def get_active_sales():
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT * FROM sales WHERE status='active' ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    con.close()
    return rows

def get_all_users_count():
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]
    con.close()
    return n

def get_pending_orders():
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()
    return rows

# ─────────────────────────────────────────────
# ROBUX NARXLARI
# ─────────────────────────────────────────────
ROBUX_PRICES = [
    (40,   7_000),
    (80,   14_000),
    (120,  21_000),
    (160,  28_000),
    (200,  35_000),
    (240,  42_000),
    (280,  49_000),
    (320,  56_000),
    (360,  63_000),
    (400,  65_000),
    (440,  72_000),
    (480,  79_000),
    (520,  86_000),
    (560,  93_000),
    (700,  100_000),
    (740,  107_000),
    (780,  114_000),
    (820,  121_000),
    (860,  128_000),
    (1000, 132_000),
    (1500, 197_000),
    (2000, 265_000),
]

def price_for(robux: int):
    for r, p in ROBUX_PRICES:
        if r == robux:
            return p
    return None

# ─────────────────────────────────────────────
# STATES
# ─────────────────────────────────────────────
class RegisterState(StatesGroup):
    roblox_nick = State()
    roblox_id   = State()

class BuyState(StatesGroup):
    choose_amount = State()

class TradeState(StatesGroup):
    offer = State()
    want  = State()

class SaleState(StatesGroup):
    item_name   = State()
    price_robux = State()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
async def is_subscribed(user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return m.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.error(f"Obuna tekshirish xato: {e}")
        return False

def sub_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")
    b.button(text="✅ Obunani tasdiqlash", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()

def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="🛒 Robux sotib olish")
    b.button(text="👤 Profil")
    b.button(text="💰 Hisob to'ldirish")
    b.button(text="🔄 Tradelar")
    b.button(text="📊 Sotuvlar")
    b.button(text="➕ Trade qo'shish")
    b.button(text="➕ Sotish qo'shish")
    b.button(text="💬 Bizning chatimiz")
    b.adjust(2, 2, 2, 2)
    return b.as_markup(resize_keyboard=True)

def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="❌ Bekor qilish")
    return b.as_markup(resize_keyboard=True)

async def check_and_register(message: types.Message, state: FSMContext) -> bool:
    """
    Obuna + ro'yxatdan o'tganini tekshiradi.
    Agar ro'yxatdan o'tmagan bo'lsa, ro'yxatdan o'tish jarayonini boshlaydi.
    True qaytaradi — davom etish mumkin; False — davom etmaslik kerak.
    """
    uid = message.from_user.id
    if not await is_subscribed(uid):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb())
        return False
    user = get_user(uid)
    if not user or not user[2]:   # roblox_nick ustuni
        await message.answer(
            "📝 Siz hali ro'yxatdan o'tmagansiz!\n\n"
            "Roblox nickingizni yozing (masalan: CoolPlayer123):",
            reply_markup=cancel_kb()
        )
        await state.set_state(RegisterState.roblox_nick)
        return False
    return True

# ─────────────────────────────────────────────
# /START
# ─────────────────────────────────────────────
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    uid  = message.from_user.id
    uname = message.from_user.username or "Foydalanuvchi"

    if not await is_subscribed(uid):
        await message.answer(
            f"❌ Botdan foydalanish uchun kanalimizga obuna bo'ling!\n\n"
            f"Obuna bo'lib, ✅ Tasdiqlash tugmasini bosing.",
            reply_markup=sub_kb()
        )
        return

    upsert_user(uid, uname)
    user = get_user(uid)

    if not user[2]:  # roblox_nick yo'q
        await message.answer(
            f"👋 Assalomu alaykum, @{uname}!\n\n"
            f"Botdan foydalanish uchun avval Roblox ma'lumotlaringizni kiriting.\n\n"
            f"🎮 Roblox nickingizni yozing:",
            reply_markup=cancel_kb()
        )
        await state.set_state(RegisterState.roblox_nick)
        return

    await message.answer(
        f"🌟 Assalomu alaykum, @{uname}!\n"
        f"🎮 Roblox: **{user[2]}** | 💰 Balans: **{user[4]} Robux**\n\n"
        f"Quyidagi menyudan foydalaning 👇",
        reply_markup=main_kb()
    )

# ─────────────────────────────────────────────
# OBUNA TASDIQLASH
# ─────────────────────────────────────────────
@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(cb: types.CallbackQuery, state: FSMContext):
    uid   = cb.from_user.id
    uname = cb.from_user.username or "Foydalanuvchi"

    if not await is_subscribed(uid):
        await cb.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)
        return

    await cb.message.delete()
    upsert_user(uid, uname)
    user = get_user(uid)

    if not user[2]:
        await cb.message.answer(
            "✅ Obuna tasdiqlandi!\n\n📝 Endi Roblox nickingizni yozing:",
            reply_markup=cancel_kb()
        )
        await state.set_state(RegisterState.roblox_nick)
        return

    await cb.message.answer(
        f"✅ Obuna tasdiqlandi! Xush kelibsiz, @{uname}!",
        reply_markup=main_kb()
    )

# ─────────────────────────────────────────────
# RO'YXATDAN O'TISH
# ─────────────────────────────────────────────
@dp.message(RegisterState.roblox_nick)
async def reg_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb())
        return

    nick = message.text.strip()
    if len(nick) < 2 or len(nick) > 30:
        await message.answer("❌ Nick 2–30 ta belgi bo'lishi kerak. Qayta yozing:")
        return

    await state.update_data(roblox_nick=nick)
    await message.answer(
        f"✅ Nick: **{nick}**\n\n"
        f"Endi Roblox ID ingizni yozing (masalan: 123456789):\n"
        f"_(Profilingizga kiring → URL dagi raqam)_"
    )
    await state.set_state(RegisterState.roblox_id)

@dp.message(RegisterState.roblox_id)
async def reg_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb())
        return

    rid = message.text.strip()
    if not rid.isdigit():
        await message.answer("❌ Roblox ID faqat raqamlardan iborat bo'lishi kerak. Qayta yozing:")
        return

    data  = await state.get_data()
    nick  = data["roblox_nick"]
    uid   = message.from_user.id
    uname = message.from_user.username or "Foydalanuvchi"

    upsert_user(uid, uname, nick, rid)
    await state.clear()

    await message.answer(
        f"🎉 Ro'yxatdan muvaffaqiyatli o'tdingiz!\n\n"
        f"🎮 Roblox Nick: **{nick}**\n"
        f"🔢 Roblox ID: `{rid}`\n\n"
        f"Menyudan foydalaning 👇",
        reply_markup=main_kb()
    )

# ─────────────────────────────────────────────
# PROFIL
# ─────────────────────────────────────────────
@dp.message(F.text == "👤 Profil")
async def profile(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return
    uid  = message.from_user.id
    user = get_user(uid)

    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='approved'", (uid,))
    order_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trades WHERE user_id=? AND status='active'", (uid,))
    trade_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sales WHERE user_id=? AND status='active'", (uid,))
    sale_count = cur.fetchone()[0]
    con.close()

    text = (
        f"👤 **Sizning profilingiz**\n\n"
        f"🆔 Telegram ID: `{uid}`\n"
        f"👤 Username: @{message.from_user.username or 'yoq'}\n"
        f"🎮 Roblox Nick: **{user[2]}**\n"
        f"🔢 Roblox ID: `{user[3]}`\n"
        f"💰 Balans: **{user[4]} Robux**\n"
        f"📅 Ro'yxat sanasi: {user[5]}\n\n"
        f"📦 Tasdiqlangan buyurtmalar: {order_count}\n"
        f"🔄 Faol tradelar: {trade_count}\n"
        f"🛍 Faol sotuvlar: {sale_count}"
    )

    b = InlineKeyboardBuilder()
    b.button(text="✏️ Roblox ma'lumotlarini yangilash", callback_data="update_roblox")
    await message.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "update_roblox")
async def update_roblox_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("🎮 Yangi Roblox nickingizni yozing:", reply_markup=cancel_kb())
    await state.set_state(RegisterState.roblox_nick)
    await cb.answer()

# ─────────────────────────────────────────────
# ROBUX SOTIB OLISH
# ─────────────────────────────────────────────
@dp.message(F.text == "🛒 Robux sotib olish")
async def robux_buy_menu(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    prices_text = "🔥 **ROBUX NARXLAR** 🔥\n\n"
    for i, (r, p) in enumerate(ROBUX_PRICES):
        star = "🔥 " if r == 700 else "🪙 "
        prices_text += f"{star}{r} Robux — {p:,} so'm\n"

    prices_text += "\n💡 Miqdorni tanlang 👇"

    # Inline tugmalar
    b = InlineKeyboardBuilder()
    for r, p in ROBUX_PRICES:
        b.button(text=f"{r} Robux — {p//1000}k so'm", callback_data=f"buy_{r}")
    b.adjust(2)

    await message.answer(prices_text, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def buy_amount_cb(cb: types.CallbackQuery, state: FSMContext):
    uid   = cb.from_user.id
    uname = cb.from_user.username or "Foydalanuvchi"

    if not await is_subscribed(uid):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        return

    user = get_user(uid)
    if not user or not user[2]:
        await cb.answer("❌ Avval ro'yxatdan o'ting! /start yozing.", show_alert=True)
        return

    amount = int(cb.data.split("_")[1])
    price  = price_for(amount)

    # Adminga yuborish
    oid = add_order(uid, uname, user[2], user[3], amount, price)

    admin_text = (
        f"🛒 **Yangi Robux buyurtma** #{oid}\n\n"
        f"👤 Telegram: @{uname} (`{uid}`)\n"
        f"🎮 Roblox Nick: **{user[2]}**\n"
        f"🔢 Roblox ID: `{user[3]}`\n"
        f"🪙 Miqdor: **{amount} Robux**\n"
        f"💵 Narx: **{price:,} so'm**\n"
        f"🕐 Vaqt: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )

    ab = InlineKeyboardBuilder()
    ab.button(text="✅ Tasdiqlash", callback_data=f"approve_order_{oid}")
    ab.button(text="❌ Rad etish", callback_data=f"reject_order_{oid}")
    ab.adjust(2)

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=ab.as_markup())
    except Exception as e:
        logging.error(f"Admin ga yuborishda xato: {e}")

    await cb.message.answer(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"🪙 **{amount} Robux** — {price:,} so'm\n"
        f"📋 Buyurtma #{oid}\n\n"
        f"💳 To'lovni amalga oshirib, admin tasdiqlashini kuting.\n"
        f"Admin: @{await get_admin_username()}"
    )
    await cb.answer()

async def get_admin_username():
    try:
        chat = await bot.get_chat(ADMIN_ID)
        return chat.username or str(ADMIN_ID)
    except:
        return str(ADMIN_ID)

# ─────────────────────────────────────────────
# ADMIN: BUYURTMA TASDIQLASH / RAD ETISH
# ─────────────────────────────────────────────
@dp.callback_query(F.data.startswith("approve_order_"))
async def approve_order(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    oid   = int(cb.data.split("_")[2])
    order = get_order(oid)
    if not order:
        await cb.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order[7] != "pending":
        await cb.answer("Bu buyurtma allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    set_order_status(oid, "approved")

    # Userga xabar
    try:
        await bot.send_message(
            order[1],  # user_id
            f"🎉 Buyurtmangiz tasdiqlandi!\n\n"
            f"🪙 **{order[5]} Robux** hisobingizga qo'shildi.\n"
            f"📋 Buyurtma #{oid}\n\n"
            f"🎮 Robuxlaringiz tez orada Roblox accountingizga o'tkaziladi!",
            reply_markup=main_kb()
        )
    except:
        pass

    await cb.message.edit_text(
        cb.message.text + f"\n\n✅ **TASDIQLANDI** ({datetime.now().strftime('%H:%M %d.%m.%Y')})"
    )
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("reject_order_"))
async def reject_order(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    oid   = int(cb.data.split("_")[2])
    order = get_order(oid)
    if not order:
        await cb.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order[7] != "pending":
        await cb.answer("Bu buyurtma allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    set_order_status(oid, "rejected")

    try:
        await bot.send_message(
            order[1],
            f"❌ Buyurtmangiz rad etildi.\n\n"
            f"📋 Buyurtma #{oid} — {order[5]} Robux\n\n"
            f"❓ Savol bo'lsa adminga murojaat qiling.",
            reply_markup=main_kb()
        )
    except:
        pass

    await cb.message.edit_text(
        cb.message.text + f"\n\n❌ **RAD ETILDI** ({datetime.now().strftime('%H:%M %d.%m.%Y')})"
    )
    await cb.answer("❌ Rad etildi!")

# ─────────────────────────────────────────────
# HISOB TO'LDIRISH
# ─────────────────────────────────────────────
@dp.message(F.text == "💰 Hisob to'ldirish")
async def deposit(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    admin_uname = await get_admin_username()
    balance = get_balance(message.from_user.id)

    await message.answer(
        f"💰 **Hisobni to'ldirish**\n\n"
        f"Joriy balans: **{balance} Robux**\n\n"
        f"💳 To'lov qilish uchun adminga murojaat qiling:\n"
        f"👤 Admin: @{admin_uname}\n\n"
        f"To'lov qilgandan so'ng admin hisobingizni to'ldiradi."
    )

# ─────────────────────────────────────────────
# TRADELAR
# ─────────────────────────────────────────────
@dp.message(F.text == "🔄 Tradelar")
async def view_trades(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    trades = get_active_trades()
    if not trades:
        await message.answer("🔄 Hozircha faol tradelar yo'q.\n\n➕ Trade qo'shish tugmasini bosing!")
        return

    text = "🔄 **Faol Tradelar** (oxirgi 20 ta)\n\n"
    for t in trades:
        # t: id, user_id, username, roblox_nick, offer, want, status, created_at
        text += (
            f"🔸 **#{t[0]}** | 🎮 {t[3]} (@{t[2]})\n"
            f"   🟢 Taklif: {t[4]}\n"
            f"   🔴 Xohlaydi: {t[5]}\n"
            f"   📅 {t[7]}\n\n"
        )

    await message.answer(text)

# ─────────────────────────────────────────────
# TRADE QO'SHISH
# ─────────────────────────────────────────────
@dp.message(F.text == "➕ Trade qo'shish")
async def add_trade_start(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    await message.answer(
        "➕ **Yangi Trade e'lon qilish**\n\n"
        "Nima taklif qilasiz? (Masalan: Korblox x10, Dominus, 100 Robux)\n"
        "Yozing:",
        reply_markup=cancel_kb()
    )
    await state.set_state(TradeState.offer)

@dp.message(TradeState.offer)
async def trade_offer(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb())
        return

    await state.update_data(offer=message.text.strip())
    await message.answer("Evaziga nima xohlaysiz? Yozing:")
    await state.set_state(TradeState.want)

@dp.message(TradeState.want)
async def trade_want(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb())
        return

    data = await state.get_data()
    uid   = message.from_user.id
    uname = message.from_user.username or "user"
    user  = get_user(uid)

    tid = add_trade(uid, uname, user[2], data["offer"], message.text.strip())
    await state.clear()

    # Adminga xabar
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🔄 **Yangi Trade** #{tid}\n\n"
            f"👤 @{uname} | 🎮 {user[2]}\n"
            f"🟢 Taklif: {data['offer']}\n"
            f"🔴 Xohlaydi: {message.text.strip()}"
        )
    except:
        pass

    await message.answer(
        f"✅ Trade #{tid} e'lon qilindi!\n\n"
        f"🟢 Taklif: **{data['offer']}**\n"
        f"🔴 Xohlaydi: **{message.text.strip()}**\n\n"
        f"Boshqalar 🔄 Tradelar bo'limida ko'radi.",
        reply_markup=main_kb()
    )

# ─────────────────────────────────────────────
# SOTUVLAR
# ─────────────────────────────────────────────
@dp.message(F.text == "📊 Sotuvlar")
async def view_sales(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    sales = get_active_sales()
    if not sales:
        await message.answer("📊 Hozircha sotuvdagi buyumlar yo'q.\n\n➕ Sotish qo'shish tugmasini bosing!")
        return

    text = "📊 **Sotuvdagi Buyumlar** (oxirgi 20 ta)\n\n"
    for s in sales:
        # s: id, user_id, username, roblox_nick, item_name, price_robux, status, created_at
        text += (
            f"🛍 **#{s[0]}** | 🎮 {s[3]} (@{s[2]})\n"
            f"   📦 Narsa: {s[4]}\n"
            f"   💰 Narx: {s[5]} Robux\n"
            f"   📅 {s[7]}\n\n"
        )

    await message.answer(text)

# ─────────────────────────────────────────────
# SOTISH QO'SHISH
# ─────────────────────────────────────────────
@dp.message(F.text == "➕ Sotish qo'shish")
async def add_sale_start(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    await message.answer(
        "➕ **Yangi Sotish e'loni**\n\n"
        "Nima sotmoqchisiz? (Masalan: Korblox x5, Dominus Empyreus)\n"
        "Yozing:",
        reply_markup=cancel_kb()
    )
    await state.set_state(SaleState.item_name)

@dp.message(SaleState.item_name)
async def sale_item(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb())
        return

    await state.update_data(item_name=message.text.strip())
    await message.answer("Narxini Robux da yozing (masalan: 500):")
    await state.set_state(SaleState.price_robux)

@dp.message(SaleState.price_robux)
async def sale_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb())
        return

    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam kiriting (masalan: 500):")
        return

    data  = await state.get_data()
    uid   = message.from_user.id
    uname = message.from_user.username or "user"
    user  = get_user(uid)
    price = int(message.text.strip())

    sid = add_sale(uid, uname, user[2], data["item_name"], price)
    await state.clear()

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🛍 **Yangi Sotuv** #{sid}\n\n"
            f"👤 @{uname} | 🎮 {user[2]}\n"
            f"📦 Narsa: {data['item_name']}\n"
            f"💰 Narx: {price} Robux"
        )
    except:
        pass

    await message.answer(
        f"✅ Sotuv #{sid} e'lon qilindi!\n\n"
        f"📦 Narsa: **{data['item_name']}**\n"
        f"💰 Narx: **{price} Robux**\n\n"
        f"Boshqalar 📊 Sotuvlar bo'limida ko'radi.",
        reply_markup=main_kb()
    )

# ─────────────────────────────────────────────
# CHAT HAVOLASI
# ─────────────────────────────────────────────
@dp.message(F.text == "💬 Bizning chatimiz")
async def community_chat(message: types.Message, state: FSMContext):
    if not await check_and_register(message, state):
        return

    b = InlineKeyboardBuilder()
    b.button(text="💬 Chatga o'tish", url="https://t.me/roblox_uz")  # ← chat linkini o'zgartiring
    await message.answer(
        "💬 **Rasmiy chatimiz**\n\n"
        "Trade, sotuv va savol-javoblar uchun guruhimizga qo'shiling 👇",
        reply_markup=b.as_markup()
    )

# ─────────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────────
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    total_users  = get_all_users_count()
    pending_ords = get_pending_orders()
    active_tr    = get_active_trades()
    active_sl    = get_active_sales()

    b = InlineKeyboardBuilder()
    b.button(text=f"📦 Kutilayotgan buyurtmalar ({len(pending_ords)})", callback_data="admin_pending")
    b.button(text=f"👥 Foydalanuvchilar soni: {total_users}", callback_data="admin_stats")
    b.button(text=f"🔄 Faol tradelar: {len(active_tr)}", callback_data="admin_trades")
    b.button(text=f"🛍 Faol sotuvlar: {len(active_sl)}", callback_data="admin_sales")
    b.adjust(1)

    await message.answer(
        f"🛠 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: **{total_users}**\n"
        f"📦 Kutilayotgan buyurtmalar: **{len(pending_ords)}**\n"
        f"🔄 Faol tradelar: **{len(active_tr)}**\n"
        f"🛍 Faol sotuvlar: **{len(active_sl)}**",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "admin_pending")
async def admin_pending_cb(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    orders = get_pending_orders()
    if not orders:
        await cb.answer("Kutilayotgan buyurtmalar yo'q!", show_alert=True)
        return

    for order in orders[:10]:
        text = (
            f"🛒 **Buyurtma #{order[0]}**\n\n"
            f"👤 @{order[2]} (`{order[1]}`)\n"
            f"🎮 Roblox Nick: **{order[3]}**\n"
            f"🔢 Roblox ID: `{order[4]}`\n"
            f"🪙 Miqdor: **{order[5]} Robux**\n"
            f"💵 Narx: **{order[6]:,} so'm**\n"
            f"🕐 Vaqt: {order[8]}"
        )
        b = InlineKeyboardBuilder()
        b.button(text="✅ Tasdiqlash", callback_data=f"approve_order_{order[0]}")
        b.button(text="❌ Rad etish",  callback_data=f"reject_order_{order[0]}")
        b.adjust(2)
        await cb.message.answer(text, reply_markup=b.as_markup())

    await cb.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_cb(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await cb.answer(f"Jami foydalanuvchilar: {get_all_users_count()}", show_alert=True)

@dp.callback_query(F.data == "admin_trades")
async def admin_trades_cb(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    trades = get_active_trades()
    if not trades:
        await cb.answer("Faol tradelar yo'q!", show_alert=True)
        return
    text = f"🔄 Faol tradelar: {len(trades)} ta"
    await cb.answer(text, show_alert=True)

@dp.callback_query(F.data == "admin_sales")
async def admin_sales_cb(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    sales = get_active_sales()
    if not sales:
        await cb.answer("Faol sotuvlar yo'q!", show_alert=True)
        return
    await cb.answer(f"🛍 Faol sotuvlar: {len(sales)} ta", show_alert=True)

# Admin: balans qo'shish  /addbalance <user_id> <amount>
@dp.message(Command("addbalance"))
async def admin_add_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yo'q!")
        return
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("❌ Format: /addbalance <user_id> <robux_miqdori>")
        return

    uid, amount = int(parts[1]), int(parts[2])
    con = db_conn()
    cur = con.cursor()
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
    con.commit()
    con.close()

    try:
        await bot.send_message(uid, f"💰 Hisobingizga **{amount} Robux** qo'shildi!", reply_markup=main_kb())
    except:
        pass
    await message.answer(f"✅ {uid} ga {amount} Robux qo'shildi.")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main():
    init_db()
    logging.info("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
