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

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0"))

REQUIRED_CHANNEL = "@roblox"

# Karta ma'lumotlari (o'zgartiring)
CARD_NUMBER  = "9860 1234 5678 9012"
CARD_OWNER   = "ISMOYILJON Q"

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ──────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────
DB = "bot.db"

def con():
    return sqlite3.connect(DB)

def init_db():
    c = con()
    cur = c.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT,
            roblox_nick  TEXT,
            balance      INTEGER DEFAULT 0,
            joined       TEXT
        );
        CREATE TABLE IF NOT EXISTS deposits (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT,
            roblox_nick TEXT,
            amount_sum INTEGER,
            status     TEXT DEFAULT 'pending',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            robux_amount INTEGER,
            price_sum   INTEGER,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            name        TEXT,
            bio         TEXT,
            photo_id    TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS sales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            name        TEXT,
            photo_id    TEXT,
            currency    TEXT,
            price       INTEGER,
            status      TEXT DEFAULT 'active',
            created_at  TEXT
        );
    """)
    c.commit()
    c.close()

# ── user helpers ──
def get_user(uid):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone(); c.close(); return r

def upsert_user(uid, uname, nick=None):
    c = con(); cur = c.cursor()
    u = get_user(uid)
    if u:
        if nick:
            cur.execute("UPDATE users SET username=?,roblox_nick=? WHERE user_id=?", (uname, nick, uid))
        else:
            cur.execute("UPDATE users SET username=? WHERE user_id=?", (uname, uid))
    else:
        cur.execute("INSERT INTO users VALUES(?,?,?,0,?)",
                    (uid, uname, nick, datetime.now().strftime("%d.%m.%Y %H:%M")))
    c.commit(); c.close()

def get_balance(uid):
    u = get_user(uid)
    return u[3] if u else 0

def add_balance(uid, amt):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    c.commit(); c.close()

def get_users_count():
    c = con(); cur = c.cursor()
    cur.execute("SELECT COUNT(*) FROM users"); n = cur.fetchone()[0]; c.close(); return n

# ── deposit helpers ──
def add_deposit(uid, uname, nick, amount):
    c = con(); cur = c.cursor()
    cur.execute("INSERT INTO deposits(user_id,username,roblox_nick,amount_sum,status,created_at) VALUES(?,?,?,?,?,?)",
                (uid, uname, nick, amount, "pending", datetime.now().strftime("%d.%m.%Y %H:%M")))
    did = cur.lastrowid; c.commit(); c.close(); return did

def set_deposit_status(did, status):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE deposits SET status=? WHERE id=?", (status, did))
    if status == "approved":
        cur.execute("SELECT user_id, amount_sum FROM deposits WHERE id=?", (did,))
        r = cur.fetchone()
        if r:
            cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r[1], r[0]))
    c.commit(); c.close()

def get_deposit(did):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM deposits WHERE id=?", (did,)); r = cur.fetchone(); c.close(); return r

# ── order helpers ──
def add_order(uid, uname, nick, robux, price):
    c = con(); cur = c.cursor()
    cur.execute("INSERT INTO orders(user_id,username,roblox_nick,robux_amount,price_sum,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (uid, uname, nick, robux, price, "pending", datetime.now().strftime("%d.%m.%Y %H:%M")))
    oid = cur.lastrowid; c.commit(); c.close(); return oid

def set_order_status(oid, status):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    if status == "approved":
        cur.execute("SELECT user_id, robux_amount FROM orders WHERE id=?", (oid,))
        r = cur.fetchone()
        if r:
            cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r[1], r[0]))
    c.commit(); c.close()

def get_order(oid):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,)); r = cur.fetchone(); c.close(); return r

def get_pending_orders():
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id DESC")
    r = cur.fetchall(); c.close(); return r

# ── trade helpers ──
def add_trade(uid, uname, nick, name, bio, photo_id):
    c = con(); cur = c.cursor()
    cur.execute("INSERT INTO trades(user_id,username,roblox_nick,name,bio,photo_id,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid, uname, nick, name, bio, photo_id, "active", datetime.now().strftime("%d.%m.%Y %H:%M")))
    tid = cur.lastrowid; c.commit(); c.close(); return tid

def get_active_trades():
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM trades WHERE status='active' ORDER BY id DESC")
    r = cur.fetchall(); c.close(); return r

def get_trade(tid):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM trades WHERE id=?", (tid,)); r = cur.fetchone(); c.close(); return r

def update_trade(tid, name, bio):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE trades SET name=?,bio=? WHERE id=?", (name, bio, tid)); c.commit(); c.close()

def delete_trade(tid):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE trades SET status='deleted' WHERE id=?", (tid,)); c.commit(); c.close()

def get_user_trades(uid):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM trades WHERE user_id=? AND status='active' ORDER BY id DESC", (uid,))
    r = cur.fetchall(); c.close(); return r

# ── sale helpers ──
def add_sale(uid, uname, nick, name, photo_id, currency, price):
    c = con(); cur = c.cursor()
    cur.execute("INSERT INTO sales(user_id,username,roblox_nick,name,photo_id,currency,price,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, uname, nick, name, photo_id, currency, price, "active", datetime.now().strftime("%d.%m.%Y %H:%M")))
    sid = cur.lastrowid; c.commit(); c.close(); return sid

def get_active_sales():
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM sales WHERE status='active' ORDER BY id DESC")
    r = cur.fetchall(); c.close(); return r

def get_sale(sid):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM sales WHERE id=?", (sid,)); r = cur.fetchone(); c.close(); return r

def update_sale(sid, name, price):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE sales SET name=?,price=? WHERE id=?", (name, price, sid)); c.commit(); c.close()

def delete_sale(sid):
    c = con(); cur = c.cursor()
    cur.execute("UPDATE sales SET status='deleted' WHERE id=?", (sid,)); c.commit(); c.close()

def get_user_sales(uid):
    c = con(); cur = c.cursor()
    cur.execute("SELECT * FROM sales WHERE user_id=? AND status='active' ORDER BY id DESC", (uid,))
    r = cur.fetchall(); c.close(); return r

# ──────────────────────────────────────────────
# ROBUX NARXLARI
# ──────────────────────────────────────────────
ROBUX_PRICES = [
    (40,7000),(80,14000),(120,21000),(160,28000),(200,35000),
    (240,42000),(280,49000),(320,56000),(360,63000),(400,65000),
    (440,72000),(480,79000),(520,86000),(560,93000),(700,100000),
    (740,107000),(780,114000),(820,121000),(860,128000),
    (1000,132000),(1500,197000),(2000,265000),
]

def price_for(robux):
    for r,p in ROBUX_PRICES:
        if r == robux: return p
    return None

# ──────────────────────────────────────────────
# STATES
# ──────────────────────────────────────────────
class Reg(StatesGroup):
    nick = State()

class Deposit(StatesGroup):
    amount   = State()
    roblox   = State()
    confirm  = State()
    check    = State()

class Buy(StatesGroup):
    pass  # inline tugmalar orqali

class TradeAdd(StatesGroup):
    name  = State()
    bio   = State()
    photo = State()

class TradeEdit(StatesGroup):
    name = State()
    bio  = State()

class SaleAdd(StatesGroup):
    name     = State()
    photo    = State()
    currency = State()
    price    = State()

class SaleEdit(StatesGroup):
    name  = State()
    price = State()

class AdminBroadcast(StatesGroup):
    photo = State()
    bio   = State()

class AdminTradeEdit(StatesGroup):
    trade_id = State()
    field    = State()

# ──────────────────────────────────────────────
# KEYBOARDS
# ──────────────────────────────────────────────
def sub_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")
    b.button(text="✅ Obunani tasdiqlash", callback_data="check_sub")
    b.adjust(1); return b.as_markup()

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
    b.adjust(2,2,2,2); return b.as_markup(resize_keyboard=True)

def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="❌ Bekor qilish")
    return b.as_markup(resize_keyboard=True)

def skip_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="⏭ O'tkazib yuborish")
    b.button(text="❌ Bekor qilish")
    b.adjust(2); return b.as_markup(resize_keyboard=True)

async def is_subscribed(uid):
    try:
        m = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=uid)
        return m.status in ["creator","administrator","member"]
    except Exception as e:
        logging.error(e); return False

async def admin_uname():
    try:
        ch = await bot.get_chat(ADMIN_ID)
        return ch.username or str(ADMIN_ID)
    except: return str(ADMIN_ID)

async def check_access(message: types.Message, state: FSMContext) -> bool:
    uid = message.from_user.id
    if not await is_subscribed(uid):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb())
        return False
    u = get_user(uid)
    if not u or not u[2]:
        upsert_user(uid, message.from_user.username or "user")
        await message.answer("📝 Roblox nickingizni yozing:", reply_markup=cancel_kb())
        await state.set_state(Reg.nick)
        return False
    return True

# ──────────────────────────────────────────────
# /START
# ──────────────────────────────────────────────
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    uid   = message.from_user.id
    uname = message.from_user.username or "Foydalanuvchi"
    if not await is_subscribed(uid):
        await message.answer(
            "❌ Botdan foydalanish uchun kanalimizga obuna bo'ling!",
            reply_markup=sub_kb()
        ); return
    upsert_user(uid, uname)
    u = get_user(uid)
    if not u[2]:
        await message.answer("📝 Roblox nickingizni yozing:", reply_markup=cancel_kb())
        await state.set_state(Reg.nick); return
    await message.answer(
        f"🌟 Assalomu alaykum, @{uname}!\n"
        f"🎮 Roblox: **{u[2]}** | 💰 Balans: **{u[3]} so'm**",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not await is_subscribed(uid):
        await cb.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True); return
    await cb.message.delete()
    upsert_user(uid, cb.from_user.username or "user")
    u = get_user(uid)
    if not u or not u[2]:
        await cb.message.answer("✅ Obuna tasdiqlandi!\n\n📝 Roblox nickingizni yozing:", reply_markup=cancel_kb())
        await state.set_state(Reg.nick); return
    await cb.message.answer("✅ Xush kelibsiz!", reply_markup=main_kb())

# ──────────────────────────────────────────────
# RO'YXATDAN O'TISH (faqat nick)
# ──────────────────────────────────────────────
@dp.message(Reg.nick)
async def reg_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    nick = message.text.strip()
    if len(nick) < 2 or len(nick) > 30:
        await message.answer("❌ Nick 2-30 belgi bo'lishi kerak:"); return
    upsert_user(message.from_user.id, message.from_user.username or "user", nick)
    await state.clear()
    await message.answer(
        f"✅ Ro'yxatdan o'tdingiz!\n🎮 Roblox Nick: **{nick}**\n\nMenyudan foydalaning 👇",
        reply_markup=main_kb()
    )

# ──────────────────────────────────────────────
# PROFIL
# ──────────────────────────────────────────────
@dp.message(F.text == "👤 Profil")
async def profile(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    uid = message.from_user.id
    u   = get_user(uid)
    my_trades = get_user_trades(uid)
    my_sales  = get_user_sales(uid)

    text = (
        f"👤 **Profilingiz**\n\n"
        f"🎮 Roblox Nick: **{u[2]}**\n"
        f"💰 Balans: **{u[3]:,} so'm**\n"
        f"📅 Ro'yxat: {u[4]}\n\n"
        f"🔄 Faol trade e'lonlarim: {len(my_trades)}\n"
        f"🛍 Faol sotuv e'lonlarim: {len(my_sales)}"
    )

    b = InlineKeyboardBuilder()
    if my_trades:
        b.button(text="🔄 Mening trade e'lonlarim", callback_data="my_trades")
    if my_sales:
        b.button(text="🛍 Mening sotuv e'lonlarim", callback_data="my_sales")
    b.button(text="✏️ Nickni yangilash", callback_data="update_nick")
    b.adjust(1)

    await message.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "update_nick")
async def update_nick_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("🎮 Yangi Roblox nickingizni yozing:", reply_markup=cancel_kb())
    await state.set_state(Reg.nick)
    await cb.answer()

# Mening trade e'lonlarim
@dp.callback_query(F.data == "my_trades")
async def my_trades_cb(cb: types.CallbackQuery):
    uid = cb.from_user.id
    trades = get_user_trades(uid)
    if not trades:
        await cb.answer("Faol trade e'lonlaringiz yo'q!", show_alert=True); return
    for t in trades:
        # t: id,user_id,username,roblox_nick,name,bio,photo_id,status,created_at
        caption = f"🔄 **{t[4]}**\n📝 {t[5]}\n📅 {t[8]}"
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"edit_trade_{t[0]}")
        b.button(text="🗑 O'chirish",  callback_data=f"del_trade_{t[0]}")
        b.adjust(2)
        if t[6]:
            await cb.message.answer_photo(t[6], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

# Mening sotuv e'lonlarim
@dp.callback_query(F.data == "my_sales")
async def my_sales_cb(cb: types.CallbackQuery):
    uid = cb.from_user.id
    sales = get_user_sales(uid)
    if not sales:
        await cb.answer("Faol sotuv e'lonlaringiz yo'q!", show_alert=True); return
    for s in sales:
        # s: id,user_id,username,roblox_nick,name,photo_id,currency,price,status,created_at
        caption = f"🛍 **{s[4]}**\n💰 {s[7]:,} {s[6]}\n📅 {s[9]}"
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"edit_sale_{s[0]}")
        b.button(text="🗑 O'chirish",  callback_data=f"del_sale_{s[0]}")
        b.adjust(2)
        if s[5]:
            await cb.message.answer_photo(s[5], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

# ── Trade tahrirlash ──
@dp.callback_query(F.data.startswith("edit_trade_"))
async def edit_trade_start(cb: types.CallbackQuery, state: FSMContext):
    tid = int(cb.data.split("_")[2])
    t = get_trade(tid)
    if not t or t[1] != cb.from_user.id:
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    await state.update_data(edit_trade_id=tid)
    await cb.message.answer("✏️ Yangi nom yozing:", reply_markup=cancel_kb())
    await state.set_state(TradeEdit.name)
    await cb.answer()

@dp.message(TradeEdit.name)
async def edit_trade_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(new_name=message.text.strip())
    await message.answer("📝 Yangi bio/tavsif yozing:")
    await state.set_state(TradeEdit.bio)

@dp.message(TradeEdit.bio)
async def edit_trade_bio(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    d = await state.get_data()
    update_trade(d["edit_trade_id"], d["new_name"], message.text.strip())
    await state.clear()
    await message.answer("✅ Trade e'loni yangilandi!", reply_markup=main_kb())

# ── Trade o'chirish ──
@dp.callback_query(F.data.startswith("del_trade_"))
async def del_trade_cb(cb: types.CallbackQuery):
    tid = int(cb.data.split("_")[2])
    t = get_trade(tid)
    if not t or (t[1] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    delete_trade(tid)
    await cb.message.edit_caption("🗑 E'lon o'chirildi.") if cb.message.photo else await cb.message.edit_text("🗑 E'lon o'chirildi.")
    await cb.answer("O'chirildi!")

# ── Sale tahrirlash ──
@dp.callback_query(F.data.startswith("edit_sale_"))
async def edit_sale_start(cb: types.CallbackQuery, state: FSMContext):
    sid = int(cb.data.split("_")[2])
    s = get_sale(sid)
    if not s or s[1] != cb.from_user.id:
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    await state.update_data(edit_sale_id=sid)
    await cb.message.answer("✏️ Yangi nom yozing:", reply_markup=cancel_kb())
    await state.set_state(SaleEdit.name)
    await cb.answer()

@dp.message(SaleEdit.name)
async def edit_sale_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(new_name=message.text.strip())
    await message.answer("💰 Yangi narxni yozing (raqam):")
    await state.set_state(SaleEdit.price)

@dp.message(SaleEdit.price)
async def edit_sale_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam:"); return
    d = await state.get_data()
    update_sale(d["edit_sale_id"], d["new_name"], int(message.text.strip()))
    await state.clear()
    await message.answer("✅ Sotuv e'loni yangilandi!", reply_markup=main_kb())

# ── Sale o'chirish ──
@dp.callback_query(F.data.startswith("del_sale_"))
async def del_sale_cb(cb: types.CallbackQuery):
    sid = int(cb.data.split("_")[2])
    s = get_sale(sid)
    if not s or (s[1] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    delete_sale(sid)
    await cb.message.edit_caption("🗑 E'lon o'chirildi.") if cb.message.photo else await cb.message.edit_text("🗑 E'lon o'chirildi.")
    await cb.answer("O'chirildi!")

# ──────────────────────────────────────────────
# HISOB TO'LDIRISH
# ──────────────────────────────────────────────
DEPOSIT_OPTIONS = [5000,10000,15000,20000,30000,50000,100000]

@dp.message(F.text == "💰 Hisob to'ldirish")
async def deposit_start(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return

    b = InlineKeyboardBuilder()
    for amt in DEPOSIT_OPTIONS:
        b.button(text=f"{amt:,} so'm", callback_data=f"dep_{amt}")
    b.button(text="✏️ Boshqa miqdor", callback_data="dep_custom")
    b.adjust(2)

    await message.answer(
        "💰 **Hisob to'ldirish**\n\nQancha to'ldirmoqchisiz?",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("dep_"))
async def dep_amount_cb(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not await is_subscribed(uid):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True); return

    if cb.data == "dep_custom":
        await cb.message.answer("✏️ To'ldirmoqchi bo'lgan miqdorni yozing (so'mda):", reply_markup=cancel_kb())
        await state.set_state(Deposit.amount)
        await cb.answer(); return

    amount = int(cb.data.split("_")[1])
    await state.update_data(dep_amount=amount)
    await _show_payment_card(cb.message, amount, state)
    await cb.answer()

@dp.message(Deposit.amount)
async def dep_custom_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    txt = message.text.strip().replace(" ","").replace(",","")
    if not txt.isdigit() or int(txt) < 1000:
        await message.answer("❌ Minimum 1000 so'm kiriting:"); return
    amount = int(txt)
    await state.update_data(dep_amount=amount)
    await _show_payment_card(message, amount, state)

async def _show_payment_card(message: types.Message, amount: int, state: FSMContext):
    b = InlineKeyboardBuilder()
    b.button(text="✅ To'lov qildim", callback_data="dep_paid")
    b.button(text="❌ Bekor qilish",  callback_data="dep_cancel")
    b.adjust(1)

    text = (
        f"💳 **To'lov ma'lumotlari**\n\n"
        f"💰 Miqdor: **{amount:,} so'm**\n\n"
        f"📋 Karta raqami:\n"
        f"`{CARD_NUMBER}`\n\n"
        f"👤 Karta egasi: **{CARD_OWNER}**\n\n"
        f"⚠️ To'lovni amalga oshirib, _To'lov qildim_ tugmasini bosing."
    )
    await message.answer(text, reply_markup=b.as_markup())
    await state.set_state(Deposit.confirm)

@dp.callback_query(F.data == "dep_cancel")
async def dep_cancel_cb(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("❌ Bekor qilindi.", reply_markup=main_kb())
    await cb.answer()

@dp.callback_query(F.data == "dep_paid")
async def dep_paid_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(
        "📸 To'lov chekining rasmini yuboring (screenshot yoki foto):",
        reply_markup=cancel_kb()
    )
    await state.set_state(Deposit.check)
    await cb.answer()

@dp.message(Deposit.check, F.photo)
async def dep_check_photo(message: types.Message, state: FSMContext):
    uid   = message.from_user.id
    uname = message.from_user.username or "user"
    u     = get_user(uid)
    d     = await state.get_data()
    amount = d.get("dep_amount", 0)

    did = add_deposit(uid, uname, u[2] if u else "-", amount)
    photo_id = message.photo[-1].file_id

    admin_text = (
        f"💰 **Yangi to'lov #{did}**\n\n"
        f"👤 @{uname} (`{uid}`)\n"
        f"🎮 Roblox: **{u[2] if u else '-'}**\n"
        f"💵 Miqdor: **{amount:,} so'm**\n"
        f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"adep_ok_{did}")
    b.button(text="❌ Rad etish",  callback_data=f"adep_no_{did}")
    b.adjust(2)

    try:
        await bot.send_photo(ADMIN_ID, photo_id, caption=admin_text, reply_markup=b.as_markup())
    except Exception as e:
        logging.error(e)

    await state.clear()
    await message.answer(
        f"✅ Chek yuborildi! Admin tasdiqlashini kuting.\n📋 To'lov #{did}",
        reply_markup=main_kb()
    )

@dp.message(Deposit.check)
async def dep_check_not_photo(message: types.Message):
    if message.text == "❌ Bekor qilish":
        return
    await message.answer("❌ Iltimos, rasm yuboring (chek screenshoti):")

# ── Admin: deposit tasdiqlash ──
@dp.callback_query(F.data.startswith("adep_ok_"))
async def adep_ok(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True); return
    did = int(cb.data.split("_")[2])
    dep = get_deposit(did)
    if not dep or dep[5] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    set_deposit_status(did, "approved")
    try:
        await bot.send_message(dep[1], f"✅ To'lovingiz tasdiqlandi!\n💰 **{dep[4]:,} so'm** hisobingizga qo'shildi!", reply_markup=main_kb())
    except: pass
    await cb.message.edit_caption(cb.message.caption + f"\n\n✅ TASDIQLANDI ({datetime.now().strftime('%H:%M')})")
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("adep_no_"))
async def adep_no(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌ Ruxsat yo'q!", show_alert=True); return
    did = int(cb.data.split("_")[2])
    dep = get_deposit(did)
    if not dep or dep[5] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    set_deposit_status(did, "rejected")
    try:
        await bot.send_message(dep[1], f"❌ To'lovingiz rad etildi.\n📋 To'lov #{did}\n\nSavollar uchun adminga murojaat qiling.", reply_markup=main_kb())
    except: pass
    await cb.message.edit_caption(cb.message.caption + f"\n\n❌ RAD ETILDI ({datetime.now().strftime('%H:%M')})")
    await cb.answer("❌ Rad etildi!")

# ──────────────────────────────────────────────
# ROBUX SOTIB OLISH
# ──────────────────────────────────────────────
@dp.message(F.text == "🛒 Robux sotib olish")
async def robux_buy(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    uid = message.from_user.id
    bal = get_balance(uid)

    text = f"🔥 **ROBUX NARXLAR**\n💰 Balansingiz: **{bal:,} so'm**\n\n"
    for r,p in ROBUX_PRICES:
        mark = "🔥" if r == 700 else "🪙"
        text += f"{mark} {r} Robux — {p:,} so'm\n"

    b = InlineKeyboardBuilder()
    for r,p in ROBUX_PRICES:
        b.button(text=f"{r} Robux — {p//1000}k", callback_data=f"buy_{r}")
    b.adjust(2)
    await message.answer(text + "\n👇 Miqdorni tanlang:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def buy_cb(cb: types.CallbackQuery):
    uid   = cb.from_user.id
    uname = cb.from_user.username or "user"
    if not await is_subscribed(uid):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True); return
    u = get_user(uid)
    if not u or not u[2]:
        await cb.answer("❌ Avval /start yozing!", show_alert=True); return

    robux = int(cb.data.split("_")[1])
    price = price_for(robux)
    bal   = get_balance(uid)

    if bal < price:
        await cb.answer(f"❌ Balans yetarli emas!\nKerak: {price:,} so'm\nBalans: {bal:,} so'm", show_alert=True); return

    # Balansdan ayirish
    c2 = con(); cur2 = c2.cursor()
    cur2.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, uid))
    c2.commit(); c2.close()

    oid = add_order(uid, uname, u[2], robux, price)

    admin_text = (
        f"🛒 **Robux buyurtma #{oid}**\n\n"
        f"👤 @{uname} (`{uid}`)\n"
        f"🎮 Roblox Nick: **{u[2]}**\n"
        f"🪙 Miqdor: **{robux} Robux**\n"
        f"💵 Narx: **{price:,} so'm**\n"
        f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    ab = InlineKeyboardBuilder()
    ab.button(text="✅ Tasdiqlash (yuborildi)", callback_data=f"aord_ok_{oid}")
    ab.button(text="❌ Rad etish (qaytarish)", callback_data=f"aord_no_{oid}")
    ab.adjust(1)

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=ab.as_markup())
    except: pass

    await cb.message.answer(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"🪙 **{robux} Robux**\n"
        f"💵 {price:,} so'm balansdan ayirildi.\n"
        f"📋 Buyurtma #{oid}\n\n"
        f"Admin Roblox accountingizga robux yuboradi. Kuting!"
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("aord_ok_"))
async def aord_ok(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌", show_alert=True); return
    oid = int(cb.data.split("_")[2])
    o = get_order(oid)
    if not o or o[6] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    set_order_status(oid, "approved")
    try:
        await bot.send_message(o[1], f"🎉 **{o[4]} Robux** Roblox accountingizga yuborildi!\n📋 Buyurtma #{oid}", reply_markup=main_kb())
    except: pass
    await cb.message.edit_text(cb.message.text + f"\n\n✅ TASDIQLANDI ({datetime.now().strftime('%H:%M')})")
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("aord_no_"))
async def aord_no(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌", show_alert=True); return
    oid = int(cb.data.split("_")[2])
    o = get_order(oid)
    if not o or o[6] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    set_order_status(oid, "rejected")
    # Pulni qaytarish
    add_balance(o[1], o[5])
    try:
        await bot.send_message(o[1], f"❌ Buyurtma #{oid} rad etildi.\n💰 {o[5]:,} so'm qaytarildi.", reply_markup=main_kb())
    except: pass
    await cb.message.edit_text(cb.message.text + f"\n\n❌ RAD ETILDI + pul qaytarildi ({datetime.now().strftime('%H:%M')})")
    await cb.answer("❌ Rad etildi!")

# ──────────────────────────────────────────────
# TRADELAR (pagination)
# ──────────────────────────────────────────────
@dp.message(F.text == "🔄 Tradelar")
async def view_trades(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    await show_trade_page(message, 0)

async def show_trade_page(target, page: int):
    trades = get_active_trades()
    if not trades:
        text = "🔄 Hozircha faol tradelar yo'q.\n\n➕ Trade qo'shish tugmasini bosing!"
        if hasattr(target, 'answer'):
            await target.answer(text)
        else:
            await target.message.answer(text)
        return

    total = len(trades)
    page  = max(0, min(page, total - 1))
    t     = trades[page]
    # t: id,user_id,username,roblox_nick,name,bio,photo_id,status,created_at

    caption = (
        f"🔄 **Trade #{t[0]}** [{page+1}/{total}]\n\n"
        f"🎮 {t[3]} (@{t[2]})\n"
        f"📦 **{t[4]}**\n"
        f"📝 {t[5]}\n"
        f"📅 {t[8]}"
    )

    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="⬅️ Oldingi", callback_data=f"tpage_{page-1}")
    if page < total - 1:
        b.button(text="➡️ Keyingi", callback_data=f"tpage_{page+1}")
    b.adjust(2)
    markup = b.as_markup()

    if hasattr(target, 'answer'):  # message
        if t[6]:
            await target.answer_photo(t[6], caption=caption, reply_markup=markup)
        else:
            await target.answer(caption, reply_markup=markup)
    else:  # callback
        try:
            if t[6]:
                await target.message.edit_caption(caption, reply_markup=markup)
            else:
                await target.message.edit_text(caption, reply_markup=markup)
        except:
            if t[6]:
                await target.message.answer_photo(t[6], caption=caption, reply_markup=markup)
            else:
                await target.message.answer(caption, reply_markup=markup)

@dp.callback_query(F.data.startswith("tpage_"))
async def trade_page_cb(cb: types.CallbackQuery):
    page = int(cb.data.split("_")[1])
    await show_trade_page(cb, page)
    await cb.answer()

# ──────────────────────────────────────────────
# TRADE QO'SHISH
# ──────────────────────────────────────────────
@dp.message(F.text == "➕ Trade qo'shish")
async def trade_add_start(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    await message.answer(
        "➕ **Yangi Trade e'loni**\n\nE'lon nomi/sarlavhasi yozing\n(masalan: Korblox x10 taklif qilaman):",
        reply_markup=cancel_kb()
    )
    await state.set_state(TradeAdd.name)

@dp.message(TradeAdd.name)
async def trade_add_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(t_name=message.text.strip())
    await message.answer("📝 Bio/tavsif yozing (nima taklif qilyapsiz, nima xohlaysiz):")
    await state.set_state(TradeAdd.bio)

@dp.message(TradeAdd.bio)
async def trade_add_bio(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(t_bio=message.text.strip())
    await message.answer(
        "📸 Rasm yuboring yoki o'tkazib yuboring:",
        reply_markup=skip_kb()
    )
    await state.set_state(TradeAdd.photo)

@dp.message(TradeAdd.photo, F.photo)
async def trade_add_photo(message: types.Message, state: FSMContext):
    d = await state.get_data()
    uid   = message.from_user.id
    uname = message.from_user.username or "user"
    u     = get_user(uid)
    photo_id = message.photo[-1].file_id
    tid = add_trade(uid, uname, u[2], d["t_name"], d["t_bio"], photo_id)
    await state.clear()
    # adminga xabar
    try:
        await bot.send_photo(ADMIN_ID, photo_id,
            caption=f"🔄 Yangi trade #{tid}\n👤 @{uname} | 🎮 {u[2]}\n📦 {d['t_name']}\n📝 {d['t_bio']}")
    except: pass
    await message.answer(f"✅ Trade #{tid} e'lon qilindi!", reply_markup=main_kb())

@dp.message(TradeAdd.photo)
async def trade_add_no_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    d = await state.get_data()
    uid   = message.from_user.id
    uname = message.from_user.username or "user"
    u     = get_user(uid)
    tid = add_trade(uid, uname, u[2], d["t_name"], d["t_bio"], None)
    await state.clear()
    try:
        await bot.send_message(ADMIN_ID,
            f"🔄 Yangi trade #{tid}\n👤 @{uname} | 🎮 {u[2]}\n📦 {d['t_name']}\n📝 {d['t_bio']}")
    except: pass
    await message.answer(f"✅ Trade #{tid} e'lon qilindi!", reply_markup=main_kb())

# ──────────────────────────────────────────────
# SOTUVLAR (pagination)
# ──────────────────────────────────────────────
@dp.message(F.text == "📊 Sotuvlar")
async def view_sales(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    await show_sale_page(message, 0)

async def show_sale_page(target, page: int):
    sales = get_active_sales()
    if not sales:
        text = "📊 Hozircha sotuvdagi buyumlar yo'q.\n\n➕ Sotish qo'shish tugmasini bosing!"
        if hasattr(target, 'answer'):
            await target.answer(text)
        else:
            await target.message.answer(text)
        return

    total = len(sales)
    page  = max(0, min(page, total - 1))
    s     = sales[page]
    # s: id,user_id,username,roblox_nick,name,photo_id,currency,price,status,created_at

    caption = (
        f"🛍 **Sotuv #{s[0]}** [{page+1}/{total}]\n\n"
        f"🎮 {s[3]} (@{s[2]})\n"
        f"📦 **{s[4]}**\n"
        f"💰 Narx: **{s[7]:,} {s[6]}**\n"
        f"📅 {s[9]}"
    )

    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="⬅️ Oldingi", callback_data=f"spage_{page-1}")
    if page < total - 1:
        b.button(text="➡️ Keyingi", callback_data=f"spage_{page+1}")
    b.adjust(2)
    markup = b.as_markup()

    if hasattr(target, 'answer'):
        if s[5]:
            await target.answer_photo(s[5], caption=caption, reply_markup=markup)
        else:
            await target.answer(caption, reply_markup=markup)
    else:
        try:
            if s[5]:
                await target.message.edit_caption(caption, reply_markup=markup)
            else:
                await target.message.edit_text(caption, reply_markup=markup)
        except:
            if s[5]:
                await target.message.answer_photo(s[5], caption=caption, reply_markup=markup)
            else:
                await target.message.answer(caption, reply_markup=markup)

@dp.callback_query(F.data.startswith("spage_"))
async def sale_page_cb(cb: types.CallbackQuery):
    page = int(cb.data.split("_")[1])
    await show_sale_page(cb, page)
    await cb.answer()

# ──────────────────────────────────────────────
# SOTISH QO'SHISH
# ──────────────────────────────────────────────
@dp.message(F.text == "➕ Sotish qo'shish")
async def sale_add_start(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    await message.answer(
        "➕ **Yangi Sotuv e'loni**\n\nNima sotmoqchisiz? Nomini yozing\n(masalan: Korblox x5, Dominus):",
        reply_markup=cancel_kb()
    )
    await state.set_state(SaleAdd.name)

@dp.message(SaleAdd.name)
async def sale_add_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(s_name=message.text.strip())
    await message.answer("📸 Rasm yuboring (ixtiyoriy):", reply_markup=skip_kb())
    await state.set_state(SaleAdd.photo)

@dp.message(SaleAdd.photo, F.photo)
async def sale_add_photo(message: types.Message, state: FSMContext):
    await state.update_data(s_photo=message.photo[-1].file_id)
    await _ask_currency(message, state)

@dp.message(SaleAdd.photo)
async def sale_add_no_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(s_photo=None)
    await _ask_currency(message, state)

async def _ask_currency(message: types.Message, state: FSMContext):
    b = InlineKeyboardBuilder()
    b.button(text="💵 So'm (UZS)", callback_data="cur_som")
    b.button(text="🪙 Robux",      callback_data="cur_robux")
    b.adjust(2)
    await message.answer("💱 Narx qaysi valyutada?", reply_markup=b.as_markup())
    await state.set_state(SaleAdd.currency)

@dp.callback_query(F.data.startswith("cur_"))
async def sale_currency_cb(cb: types.CallbackQuery, state: FSMContext):
    cur_map = {"cur_som": "so'm", "cur_robux": "Robux"}
    currency = cur_map.get(cb.data, "so'm")
    await state.update_data(s_currency=currency)
    await cb.message.answer(f"💰 Narxni yozing ({currency} da):", reply_markup=cancel_kb())
    await state.set_state(SaleAdd.price)
    await cb.answer()

@dp.message(SaleAdd.price)
async def sale_add_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    txt = message.text.strip().replace(" ","").replace(",","")
    if not txt.isdigit():
        await message.answer("❌ Faqat raqam kiriting:"); return
    d     = await state.get_data()
    uid   = message.from_user.id
    uname = message.from_user.username or "user"
    u     = get_user(uid)
    sid = add_sale(uid, uname, u[2], d["s_name"], d.get("s_photo"), d["s_currency"], int(txt))
    await state.clear()
    try:
        if d.get("s_photo"):
            await bot.send_photo(ADMIN_ID, d["s_photo"],
                caption=f"🛍 Yangi sotuv #{sid}\n👤 @{uname} | 🎮 {u[2]}\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}")
        else:
            await bot.send_message(ADMIN_ID,
                f"🛍 Yangi sotuv #{sid}\n👤 @{uname} | 🎮 {u[2]}\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}")
    except: pass
    await message.answer(f"✅ Sotuv #{sid} e'lon qilindi!\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}", reply_markup=main_kb())

# ──────────────────────────────────────────────
# CHAT
# ──────────────────────────────────────────────
@dp.message(F.text == "💬 Bizning chatimiz")
async def chat_link(message: types.Message, state: FSMContext):
    if not await check_access(message, state): return
    b = InlineKeyboardBuilder()
    b.button(text="💬 Chatga kirish", url="https://t.me/roblox_uz")
    await message.answer("💬 Rasmiy chatimizga xush kelibsiz!", reply_markup=b.as_markup())

# ──────────────────────────────────────────────
# ADMIN PANEL
# ──────────────────────────────────────────────
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yo'q!"); return

    trades = get_active_trades()
    sales  = get_active_sales()
    orders = get_pending_orders()

    b = InlineKeyboardBuilder()
    b.button(text=f"📦 Kutayotgan buyurtmalar ({len(orders)})", callback_data="adm_orders")
    b.button(text=f"🔄 Barcha tradelar ({len(trades)})",        callback_data="adm_trades")
    b.button(text=f"🛍 Barcha sotuvlar ({len(sales)})",         callback_data="adm_sales")
    b.button(text="📢 Hammaga xabar yuborish",                  callback_data="adm_broadcast")
    b.button(text=f"👥 Foydalanuvchilar: {get_users_count()}",  callback_data="adm_users")
    b.adjust(1)

    await message.answer(
        f"🛠 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: **{get_users_count()}**\n"
        f"📦 Kutayotgan buyurtmalar: **{len(orders)}**\n"
        f"🔄 Faol tradelar: **{len(trades)}**\n"
        f"🛍 Faol sotuvlar: **{len(sales)}**",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "adm_orders")
async def adm_orders(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    orders = get_pending_orders()
    if not orders:
        await cb.answer("Kutayotgan buyurtmalar yo'q!", show_alert=True); return
    for o in orders[:10]:
        text = (
            f"🛒 **Buyurtma #{o[0]}**\n"
            f"👤 @{o[2]} | 🎮 {o[3]}\n"
            f"🪙 {o[4]} Robux — {o[5]:,} so'm\n"
            f"🕐 {o[7]}"
        )
        b = InlineKeyboardBuilder()
        b.button(text="✅ Yuborildi", callback_data=f"aord_ok_{o[0]}")
        b.button(text="❌ Rad etish", callback_data=f"aord_no_{o[0]}")
        b.adjust(2)
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_trades")
async def adm_trades(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    trades = get_active_trades()
    if not trades:
        await cb.answer("Tradelar yo'q!", show_alert=True); return
    for t in trades[:10]:
        caption = f"🔄 **Trade #{t[0]}**\n🎮 {t[3]} (@{t[2]})\n📦 {t[4]}\n📝 {t[5]}\n📅 {t[8]}"
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"edit_trade_{t[0]}")
        b.button(text="🗑 O'chirish",  callback_data=f"del_trade_{t[0]}")
        b.adjust(2)
        if t[6]:
            await cb.message.answer_photo(t[6], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_sales")
async def adm_sales(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    sales = get_active_sales()
    if not sales:
        await cb.answer("Sotuvlar yo'q!", show_alert=True); return
    for s in sales[:10]:
        caption = f"🛍 **Sotuv #{s[0]}**\n🎮 {s[3]} (@{s[2]})\n📦 {s[4]}\n💰 {s[7]:,} {s[6]}\n📅 {s[9]}"
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"edit_sale_{s[0]}")
        b.button(text="🗑 O'chirish",  callback_data=f"del_sale_{s[0]}")
        b.adjust(2)
        if s[5]:
            await cb.message.answer_photo(s[5], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_users")
async def adm_users(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer(f"Jami foydalanuvchilar: {get_users_count()}", show_alert=True)

# ── Broadcast ──
@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.message.answer("📸 Rasm yuboring (ixtiyoriy):", reply_markup=skip_kb())
    await state.set_state(AdminBroadcast.photo)
    await cb.answer()

@dp.message(AdminBroadcast.photo, F.photo)
async def broadcast_photo(message: types.Message, state: FSMContext):
    await state.update_data(br_photo=message.photo[-1].file_id)
    await message.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(AdminBroadcast.bio)

@dp.message(AdminBroadcast.photo)
async def broadcast_no_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(br_photo=None)
    await message.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(AdminBroadcast.bio)

@dp.message(AdminBroadcast.bio)
async def broadcast_send(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("Bekor qilindi.", reply_markup=main_kb()); return
    d = await state.get_data()
    text  = message.text.strip()
    photo = d.get("br_photo")
    await state.clear()

    c2 = con(); cur2 = c2.cursor()
    cur2.execute("SELECT user_id FROM users")
    users = cur2.fetchall(); c2.close()

    sent = 0
    for (uid,) in users:
        try:
            if photo:
                await bot.send_photo(uid, photo, caption=text)
            else:
                await bot.send_message(uid, text)
            sent += 1
        except: pass
        await asyncio.sleep(0.05)

    await message.answer(f"✅ Xabar {sent}/{len(users)} foydalanuvchiga yuborildi!", reply_markup=main_kb())

# ── Admin balans qo'shish ──
@dp.message(Command("addbalance"))
async def admin_add_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yo'q!"); return
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("❌ Format: /addbalance <user_id> <so'm_miqdori>"); return
    uid, amt = int(parts[1]), int(parts[2])
    add_balance(uid, amt)
    try:
        await bot.send_message(uid, f"💰 Hisobingizga **{amt:,} so'm** qo'shildi!", reply_markup=main_kb())
    except: pass
    await message.answer(f"✅ {uid} ga {amt:,} so'm qo'shildi.")

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
async def main():
    init_db()
    logging.info("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
