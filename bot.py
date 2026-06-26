cat > /home/claude/roblox_trade_bot/bot.py << 'ENDOFFILE'
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

REQUIRED_CHANNEL = "@bulldrop_n1"   # ← o'zgartiring
CARD_NUMBER      = "9860 1234 5678 9012"  # ← o'zgartiring
CARD_OWNER       = "MUHammadjon osha iosha" # ← o'zgartiring

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ══════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════
DB = "bot.db"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            roblox_nick TEXT,
            balance     INTEGER DEFAULT 0,
            joined      TEXT
        );
        CREATE TABLE IF NOT EXISTS deposits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            roblox_nick TEXT,
            amount      INTEGER,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            username     TEXT,
            roblox_nick  TEXT,
            robux_amount INTEGER,
            price_sum    INTEGER,
            status       TEXT DEFAULT 'pending',
            created_at   TEXT
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
    c.commit(); c.close()

# ── helpers ──
def _one(table, uid):
    c = db(); r = c.execute(f"SELECT * FROM {table} WHERE user_id=?", (uid,)).fetchone(); c.close(); return r

def get_user(uid):   return _one("users", uid)

def upsert_user(uid, uname, nick=None):
    c = db()
    u = c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,)).fetchone()
    if u:
        if nick:
            c.execute("UPDATE users SET username=?,roblox_nick=? WHERE user_id=?", (uname, nick, uid))
        else:
            c.execute("UPDATE users SET username=? WHERE user_id=?", (uname, uid))
    else:
        c.execute("INSERT INTO users VALUES(?,?,?,0,?)",
                  (uid, uname, nick, now()))
    c.commit(); c.close()

def get_balance(uid):
    c = db(); r = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone(); c.close()
    return r[0] if r else 0

def add_balance(uid, amt):
    c = db(); c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid)); c.commit(); c.close()

def sub_balance(uid, amt):
    c = db(); c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid)); c.commit(); c.close()

def users_count():
    c = db(); n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]; c.close(); return n

def all_user_ids():
    c = db(); rows = c.execute("SELECT user_id FROM users").fetchall(); c.close(); return [r[0] for r in rows]

# deposits
def add_deposit(uid, uname, nick, amount):
    c = db()
    c.execute("INSERT INTO deposits(user_id,username,roblox_nick,amount,status,created_at) VALUES(?,?,?,?,?,?)",
              (uid, uname, nick, amount, "pending", now()))
    did = c.lastrowid; c.commit(); c.close(); return did

def get_deposit(did):
    c = db(); r = c.execute("SELECT * FROM deposits WHERE id=?", (did,)).fetchone(); c.close(); return r

def approve_deposit(did):
    c = db()
    r = c.execute("SELECT user_id, amount FROM deposits WHERE id=?", (did,)).fetchone()
    if r:
        c.execute("UPDATE deposits SET status='approved' WHERE id=?", (did,))
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r[0], r[1]))  # fixed: amount=r[1] uid=r[0]... wait
        # Row: id,user_id,username,roblox_nick,amount,status,created_at  → user_id=r[1], amount=r[4]
    c.commit(); c.close()

def reject_deposit(did):
    c = db(); c.execute("UPDATE deposits SET status='rejected' WHERE id=?", (did,)); c.commit(); c.close()

# Fix approve_deposit — sqlite3.Row order: id=0,user_id=1,username=2,roblox_nick=3,amount=4
def approve_deposit(did):
    c = db()
    r = c.execute("SELECT * FROM deposits WHERE id=?", (did,)).fetchone()
    if r:
        c.execute("UPDATE deposits SET status='approved' WHERE id=?", (did,))
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r[4], r[1]))
    c.commit(); c.close()

# orders
def add_order(uid, uname, nick, robux, price):
    c = db()
    c.execute("INSERT INTO orders(user_id,username,roblox_nick,robux_amount,price_sum,status,created_at) VALUES(?,?,?,?,?,?,?)",
              (uid, uname, nick, robux, price, "pending", now()))
    oid = c.lastrowid; c.commit(); c.close(); return oid

def get_order(oid):
    c = db(); r = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone(); c.close(); return r

def approve_order(oid):
    c = db(); c.execute("UPDATE orders SET status='approved' WHERE id=?", (oid,)); c.commit(); c.close()

def reject_order(oid):
    c = db()
    r = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if r:
        c.execute("UPDATE orders SET status='rejected' WHERE id=?", (oid,))
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r[5], r[1]))  # price_sum=r[5], user_id=r[1]
    c.commit(); c.close()

def pending_orders():
    c = db(); r = c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id DESC").fetchall(); c.close(); return r

# trades
def add_trade(uid, uname, nick, name, bio, photo_id):
    c = db()
    c.execute("INSERT INTO trades(user_id,username,roblox_nick,name,bio,photo_id,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
              (uid, uname, nick, name, bio, photo_id, "active", now()))
    tid = c.lastrowid; c.commit(); c.close(); return tid

def get_trade(tid):
    c = db(); r = c.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone(); c.close(); return r

def active_trades():
    c = db(); r = c.execute("SELECT * FROM trades WHERE status='active' ORDER BY id DESC").fetchall(); c.close(); return r

def my_trades(uid):
    c = db(); r = c.execute("SELECT * FROM trades WHERE user_id=? AND status='active' ORDER BY id DESC", (uid,)).fetchall(); c.close(); return r

def edit_trade(tid, name, bio):
    c = db(); c.execute("UPDATE trades SET name=?,bio=? WHERE id=?", (name, bio, tid)); c.commit(); c.close()

def delete_trade(tid):
    c = db(); c.execute("UPDATE trades SET status='deleted' WHERE id=?", (tid,)); c.commit(); c.close()

# sales
def add_sale(uid, uname, nick, name, photo_id, currency, price):
    c = db()
    c.execute("INSERT INTO sales(user_id,username,roblox_nick,name,photo_id,currency,price,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (uid, uname, nick, name, photo_id, currency, price, "active", now()))
    sid = c.lastrowid; c.commit(); c.close(); return sid

def get_sale(sid):
    c = db(); r = c.execute("SELECT * FROM sales WHERE id=?", (sid,)).fetchone(); c.close(); return r

def active_sales():
    c = db(); r = c.execute("SELECT * FROM sales WHERE status='active' ORDER BY id DESC").fetchall(); c.close(); return r

def my_sales(uid):
    c = db(); r = c.execute("SELECT * FROM sales WHERE user_id=? AND status='active' ORDER BY id DESC", (uid,)).fetchall(); c.close(); return r

def edit_sale(sid, name, price):
    c = db(); c.execute("UPDATE sales SET name=?,price=? WHERE id=?", (name, price, sid)); c.commit(); c.close()

def delete_sale(sid):
    c = db(); c.execute("UPDATE sales SET status='deleted' WHERE id=?", (sid,)); c.commit(); c.close()

def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

# ══════════════════════════════════════════════
# ROBUX NARXLARI
# ══════════════════════════════════════════════
ROBUX_PRICES = [
    (40,7000),(80,14000),(120,21000),(160,28000),(200,35000),
    (240,42000),(280,49000),(320,56000),(360,63000),(400,65000),
    (440,72000),(480,79000),(520,86000),(560,93000),(700,100000),
    (740,107000),(780,114000),(820,121000),(860,128000),
    (1000,132000),(1500,197000),(2000,265000),
]

def price_for(robux):
    for r, p in ROBUX_PRICES:
        if r == robux: return p
    return None

DEPOSIT_OPTIONS = [5000, 10000, 15000, 20000, 30000, 50000, 100000]

# ══════════════════════════════════════════════
# STATES
# ══════════════════════════════════════════════
class Reg(StatesGroup):
    nick = State()

class Dep(StatesGroup):
    custom_amount = State()   # faqat boshqa miqdor uchun
    check_photo   = State()   # chek rasmi kutish

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

class Broadcast(StatesGroup):
    photo = State()
    text  = State()

# ══════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════
def sub_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")
    b.button(text="✅ Obunani tasdiqlash", callback_data="check_sub")
    b.adjust(1); return b.as_markup()

def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="🛒 Robux sotib olish"); b.button(text="👤 Profil")
    b.button(text="💰 Hisob to'ldirish");  b.button(text="🔄 Tradelar")
    b.button(text="📊 Sotuvlar");          b.button(text="➕ Trade qo'shish")
    b.button(text="➕ Sotish qo'shish");   b.button(text="💬 Bizning chatimiz")
    b.adjust(2,2,2,2)
    return b.as_markup(resize_keyboard=True)

def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="❌ Bekor qilish")
    return b.as_markup(resize_keyboard=True)

def skip_cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="⏭ O'tkazib yuborish"); b.button(text="❌ Bekor qilish")
    b.adjust(2); return b.as_markup(resize_keyboard=True)

# ══════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════
async def is_sub(uid):
    try:
        m = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=uid)
        return m.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.error(f"Sub check error: {e}"); return False

async def check_access(msg: types.Message, state: FSMContext) -> bool:
    uid = msg.from_user.id
    if not await is_sub(uid):
        await msg.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb()); return False
    u = get_user(uid)
    if not u or not u[2]:
        upsert_user(uid, msg.from_user.username or "user")
        await msg.answer("📝 Roblox nickingizni yozing:", reply_markup=cancel_kb())
        await state.set_state(Reg.nick); return False
    return True

# ══════════════════════════════════════════════
# /START  +  OBUNA
# ══════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    if not await is_sub(uid):
        await msg.answer("❌ Botdan foydalanish uchun kanalimizga obuna bo'ling!", reply_markup=sub_kb()); return
    upsert_user(uid, msg.from_user.username or "user")
    u = get_user(uid)
    if not u[2]:
        await msg.answer("📝 Roblox nickingizni yozing:", reply_markup=cancel_kb())
        await state.set_state(Reg.nick); return
    await msg.answer(
        f"🌟 Assalomu alaykum, @{msg.from_user.username or 'do\'st'}!\n"
        f"🎮 Roblox: **{u[2]}** | 💰 Balans: **{u[3]:,} so'm**",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not await is_sub(uid):
        await cb.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True); return
    await cb.message.delete()
    upsert_user(uid, cb.from_user.username or "user")
    u = get_user(uid)
    if not u or not u[2]:
        await cb.message.answer("✅ Obuna tasdiqlandi!\n📝 Roblox nickingizni yozing:", reply_markup=cancel_kb())
        await state.set_state(Reg.nick); return
    await cb.message.answer("✅ Xush kelibsiz!", reply_markup=main_kb())

# ══════════════════════════════════════════════
# RO'YXAT
# ══════════════════════════════════════════════
@dp.message(Reg.nick)
async def reg_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    nick = msg.text.strip()
    if not 2 <= len(nick) <= 30:
        await msg.answer("❌ Nick 2–30 belgi bo'lishi kerak:"); return
    upsert_user(msg.from_user.id, msg.from_user.username or "user", nick)
    await state.clear()
    await msg.answer(f"✅ Ro'yxatdan o'tdingiz!\n🎮 Roblox Nick: **{nick}**", reply_markup=main_kb())

# ══════════════════════════════════════════════
# PROFIL
# ══════════════════════════════════════════════
@dp.message(F.text == "👤 Profil")
async def cmd_profile(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    uid = msg.from_user.id
    u   = get_user(uid)
    tr  = my_trades(uid)
    sl  = my_sales(uid)

    b = InlineKeyboardBuilder()
    if tr: b.button(text=f"🔄 Mening tradelarim ({len(tr)})", callback_data="my_trades_0")
    if sl: b.button(text=f"🛍 Mening sotuvlarim ({len(sl)})",  callback_data="my_sales_0")
    b.button(text="✏️ Nickni yangilash", callback_data="upd_nick")
    b.adjust(1)

    await msg.answer(
        f"👤 **Profilingiz**\n\n"
        f"🎮 Roblox Nick: **{u[2]}**\n"
        f"💰 Balans: **{u[3]:,} so'm**\n"
        f"📅 Ro'yxat: {u[4]}\n\n"
        f"🔄 Faol tradelarim: {len(tr)}\n"
        f"🛍 Faol sotuvlarim: {len(sl)}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "upd_nick")
async def cb_upd_nick(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("🎮 Yangi Roblox nickingizni yozing:", reply_markup=cancel_kb())
    await state.set_state(Reg.nick); await cb.answer()

# ─── Mening tradelarim (sahifalash) ───
@dp.callback_query(F.data.startswith("my_trades_"))
async def cb_my_trades(cb: types.CallbackQuery):
    uid = cb.from_user.id
    page = int(cb.data.split("_")[2])
    items = my_trades(uid)
    if not items:
        await cb.answer("Faol trade e'lonlaringiz yo'q!", show_alert=True); return

    page = max(0, min(page, len(items)-1))
    t = items[page]
    # id=0,user_id=1,username=2,roblox_nick=3,name=4,bio=5,photo_id=6,status=7,created_at=8
    caption = f"🔄 **{t[4]}** [{page+1}/{len(items)}]\n📝 {t[5]}\n📅 {t[8]}"
    b = InlineKeyboardBuilder()
    if page > 0:            b.button(text="⬅️", callback_data=f"my_trades_{page-1}")
    if page < len(items)-1: b.button(text="➡️", callback_data=f"my_trades_{page+1}")
    b.button(text="✏️ Tahrirlash", callback_data=f"etrade_{t[0]}")
    b.button(text="🗑 O'chirish",  callback_data=f"dtrade_{t[0]}")
    b.adjust(2, 2)
    await _send_or_edit(cb, t[6], caption, b.as_markup())
    await cb.answer()

# ─── Mening sotuvlarim (sahifalash) ───
@dp.callback_query(F.data.startswith("my_sales_"))
async def cb_my_sales(cb: types.CallbackQuery):
    uid = cb.from_user.id
    page = int(cb.data.split("_")[2])
    items = my_sales(uid)
    if not items:
        await cb.answer("Faol sotuv e'lonlaringiz yo'q!", show_alert=True); return

    page = max(0, min(page, len(items)-1))
    s = items[page]
    # id=0,user_id=1,username=2,roblox_nick=3,name=4,photo_id=5,currency=6,price=7,status=8,created_at=9
    caption = f"🛍 **{s[4]}** [{page+1}/{len(items)}]\n💰 {s[7]:,} {s[6]}\n📅 {s[9]}"
    b = InlineKeyboardBuilder()
    if page > 0:            b.button(text="⬅️", callback_data=f"my_sales_{page-1}")
    if page < len(items)-1: b.button(text="➡️", callback_data=f"my_sales_{page+1}")
    b.button(text="✏️ Tahrirlash", callback_data=f"esale_{s[0]}")
    b.button(text="🗑 O'chirish",  callback_data=f"dsale_{s[0]}")
    b.adjust(2, 2)
    await _send_or_edit(cb, s[5], caption, b.as_markup())
    await cb.answer()

# ══════════════════════════════════════════════
# UNIVERSAL send_or_edit helper
# ══════════════════════════════════════════════
async def _send_or_edit(cb: types.CallbackQuery, photo_id, text, markup):
    """Mavjud xabarni edit qilishga harakat qiladi, bo'lmasa yangi yuboradi."""
    try:
        if photo_id:
            if cb.message.photo:
                await cb.message.edit_caption(caption=text, reply_markup=markup)
            else:
                await cb.message.delete()
                await cb.message.answer_photo(photo_id, caption=text, reply_markup=markup)
        else:
            if cb.message.photo:
                await cb.message.delete()
                await cb.message.answer(text, reply_markup=markup)
            else:
                await cb.message.edit_text(text, reply_markup=markup)
    except Exception as e:
        logging.warning(f"edit failed: {e}")
        if photo_id:
            await cb.message.answer_photo(photo_id, caption=text, reply_markup=markup)
        else:
            await cb.message.answer(text, reply_markup=markup)

# ══════════════════════════════════════════════
# TRADE TAHRIRLASH / O'CHIRISH
# ══════════════════════════════════════════════
@dp.callback_query(F.data.startswith("etrade_"))
async def cb_etrade(cb: types.CallbackQuery, state: FSMContext):
    tid = int(cb.data.split("_")[1])
    t = get_trade(tid)
    if not t or (t[1] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    await state.update_data(edit_trade_id=tid)
    await cb.message.answer("✏️ Yangi nom yozing:", reply_markup=cancel_kb())
    await state.set_state(TradeEdit.name); await cb.answer()

@dp.message(TradeEdit.name)
async def etrade_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(new_name=msg.text.strip())
    await msg.answer("📝 Yangi bio yozing:")
    await state.set_state(TradeEdit.bio)

@dp.message(TradeEdit.bio)
async def etrade_bio(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    d = await state.get_data()
    edit_trade(d["edit_trade_id"], d["new_name"], msg.text.strip())
    await state.clear(); await msg.answer("✅ Trade yangilandi!", reply_markup=main_kb())

@dp.callback_query(F.data.startswith("dtrade_"))
async def cb_dtrade(cb: types.CallbackQuery):
    tid = int(cb.data.split("_")[1])
    t = get_trade(tid)
    if not t or (t[1] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    delete_trade(tid)
    try:
        if cb.message.photo: await cb.message.edit_caption("🗑 E'lon o'chirildi.")
        else:                 await cb.message.edit_text("🗑 E'lon o'chirildi.")
    except: pass
    await cb.answer("✅ O'chirildi!")

# ══════════════════════════════════════════════
# SALE TAHRIRLASH / O'CHIRISH
# ══════════════════════════════════════════════
@dp.callback_query(F.data.startswith("esale_"))
async def cb_esale(cb: types.CallbackQuery, state: FSMContext):
    sid = int(cb.data.split("_")[1])
    s = get_sale(sid)
    if not s or (s[1] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    await state.update_data(edit_sale_id=sid)
    await cb.message.answer("✏️ Yangi nom yozing:", reply_markup=cancel_kb())
    await state.set_state(SaleEdit.name); await cb.answer()

@dp.message(SaleEdit.name)
async def esale_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(new_name=msg.text.strip())
    await msg.answer("💰 Yangi narx (raqam):")
    await state.set_state(SaleEdit.price)

@dp.message(SaleEdit.price)
async def esale_price(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    txt = msg.text.strip().replace(" ","")
    if not txt.isdigit():
        await msg.answer("❌ Faqat raqam:"); return
    d = await state.get_data()
    edit_sale(d["edit_sale_id"], d["new_name"], int(txt))
    await state.clear(); await msg.answer("✅ Sotuv yangilandi!", reply_markup=main_kb())

@dp.callback_query(F.data.startswith("dsale_"))
async def cb_dsale(cb: types.CallbackQuery):
    sid = int(cb.data.split("_")[1])
    s = get_sale(sid)
    if not s or (s[1] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True); return
    delete_sale(sid)
    try:
        if cb.message.photo: await cb.message.edit_caption("🗑 E'lon o'chirildi.")
        else:                 await cb.message.edit_text("🗑 E'lon o'chirildi.")
    except: pass
    await cb.answer("✅ O'chirildi!")

# ══════════════════════════════════════════════
# HISOB TO'LDIRISH
# ══════════════════════════════════════════════
@dp.message(F.text == "💰 Hisob to'ldirish")
async def cmd_deposit(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    b = InlineKeyboardBuilder()
    for amt in DEPOSIT_OPTIONS:
        b.button(text=f"{amt:,} so'm", callback_data=f"damt_{amt}")
    b.button(text="✏️ Boshqa miqdor", callback_data="damt_custom")
    b.adjust(2)
    await msg.answer("💰 **Hisob to'ldirish**\n\nQancha to'ldirmoqchisiz?", reply_markup=b.as_markup())

# Miqdor tanlash (inline)
@dp.callback_query(F.data.startswith("damt_"))
async def cb_damt(cb: types.CallbackQuery, state: FSMContext):
    if not await is_sub(cb.from_user.id):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True); return

    if cb.data == "damt_custom":
        await cb.message.answer("✏️ Miqdorni yozing (so'mda, min 1000):", reply_markup=cancel_kb())
        await state.set_state(Dep.custom_amount)
        await cb.answer(); return

    amount = int(cb.data.split("_")[1])
    await state.update_data(dep_amount=amount)
    await cb.message.delete()
    await _show_card(cb.message, cb.from_user.id, amount, state)
    await cb.answer()

@dp.message(Dep.custom_amount)
async def dep_custom(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    txt = msg.text.strip().replace(" ","").replace(",","")
    if not txt.isdigit() or int(txt) < 1000:
        await msg.answer("❌ Minimum 1000 so'm kiriting:"); return
    amount = int(txt)
    await state.update_data(dep_amount=amount)
    await _show_card(msg, msg.from_user.id, amount, state)

async def _show_card(target, uid, amount: int, state: FSMContext):
    """Karta ma'lumotlari + tugmalar chiqaradi, state ni dep_confirm ga o'tkazadi"""
    b = InlineKeyboardBuilder()
    b.button(text="✅ To'lov qildim", callback_data="dep_paid")
    b.button(text="❌ Bekor qilish",  callback_data="dep_cancel")
    b.adjust(1)

    text = (
        f"💳 **To'lov ma'lumotlari**\n\n"
        f"💰 Miqdor: **{amount:,} so'm**\n\n"
        f"🏦 Karta raqami:\n"
        f"`{CARD_NUMBER}`\n\n"
        f"👤 Karta egasi: **{CARD_OWNER}**\n\n"
        f"Karta raqamiga bosib nusxa oling, to'lovni amalga oshiring va "
        f"✅ To'lov qildim tugmasini bosing."
    )

    if hasattr(target, 'answer'):
        await target.answer(text, reply_markup=b.as_markup())
    else:
        await target.answer(text, reply_markup=b.as_markup())

# ── To'lov qildim ──
@dp.callback_query(F.data == "dep_paid")
async def cb_dep_paid(cb: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("dep_amount"):
        await cb.answer("❌ Xatolik! Qaytadan boshlang.", show_alert=True)
        await state.clear(); return
    await cb.message.answer(
        "📸 To'lov chekining rasmini yuboring (screenshot):",
        reply_markup=cancel_kb()
    )
    await state.set_state(Dep.check_photo)
    await cb.answer()

# ── Bekor qilish ──
@dp.callback_query(F.data == "dep_cancel")
async def cb_dep_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try: await cb.message.delete()
    except: pass
    await cb.message.answer("❌ Bekor qilindi.", reply_markup=main_kb())
    await cb.answer()

# ── Chek rasmi ──
@dp.message(Dep.check_photo, F.photo)
async def dep_check_photo(msg: types.Message, state: FSMContext):
    uid   = msg.from_user.id
    uname = msg.from_user.username or "user"
    u     = get_user(uid)
    d     = await state.get_data()
    amount = d.get("dep_amount", 0)

    did      = add_deposit(uid, uname, u[2] if u else "-", amount)
    photo_id = msg.photo[-1].file_id

    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"dok_{did}")
    b.button(text="❌ Rad etish",  callback_data=f"dno_{did}")
    b.adjust(2)

    try:
        await bot.send_photo(ADMIN_ID, photo_id,
            caption=(
                f"💰 **To'lov #{did}**\n\n"
                f"👤 @{uname} (`{uid}`)\n"
                f"🎮 Roblox: **{u[2] if u else '-'}**\n"
                f"💵 Miqdor: **{amount:,} so'm**\n"
                f"🕐 {now()}"
            ), reply_markup=b.as_markup())
    except Exception as e:
        logging.error(f"Admin ga yuborishda xato: {e}")

    await state.clear()
    await msg.answer(f"✅ Chek yuborildi! Admin tasdiqlashini kuting.\n📋 To'lov #{did}", reply_markup=main_kb())

@dp.message(Dep.check_photo)
async def dep_not_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("❌ Bekor qilindi.", reply_markup=main_kb()); return
    await msg.answer("❌ Rasm yuboring (chek screenshoti):")

# ── Admin: deposit tasdiqlash ──
@dp.callback_query(F.data.startswith("dok_"))
async def cb_dok(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌", show_alert=True); return
    did = int(cb.data.split("_")[1])
    dep = get_deposit(did)
    if not dep or dep[5] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    approve_deposit(did)
    try:
        await bot.send_message(dep[1], f"✅ To'lovingiz tasdiqlandi!\n💰 **{dep[4]:,} so'm** hisobingizga qo'shildi!", reply_markup=main_kb())
    except: pass
    try:
        await cb.message.edit_caption(cb.message.caption + f"\n\n✅ TASDIQLANDI ({now()})")
    except: pass
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("dno_"))
async def cb_dno(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌", show_alert=True); return
    did = int(cb.data.split("_")[1])
    dep = get_deposit(did)
    if not dep or dep[5] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    reject_deposit(did)
    try:
        await bot.send_message(dep[1], f"❌ To'lovingiz rad etildi.\n📋 To'lov #{did}\n\nSavollar uchun adminga murojaat qiling.", reply_markup=main_kb())
    except: pass
    try:
        await cb.message.edit_caption(cb.message.caption + f"\n\n❌ RAD ETILDI ({now()})")
    except: pass
    await cb.answer("❌ Rad etildi!")

# ══════════════════════════════════════════════
# ROBUX SOTIB OLISH
# ══════════════════════════════════════════════
@dp.message(F.text == "🛒 Robux sotib olish")
async def cmd_buy(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    uid = msg.from_user.id
    bal = get_balance(uid)

    lines = ""
    for r, p in ROBUX_PRICES:
        lines += f"{'🔥' if r==700 else '🪙'} {r} Robux — {p:,} so'm\n"

    b = InlineKeyboardBuilder()
    for r, p in ROBUX_PRICES:
        b.button(text=f"{r}Rbx — {p//1000}k", callback_data=f"buy_{r}")
    b.adjust(3)

    await msg.answer(
        f"🔥 **ROBUX NARXLAR**\n💰 Balansingiz: **{bal:,} so'm**\n\n{lines}\n👇 Miqdorni tanlang:",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if not await is_sub(uid):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True); return
    u = get_user(uid)
    if not u or not u[2]:
        await cb.answer("❌ Avval /start yozing!", show_alert=True); return

    robux = int(cb.data.split("_")[1])
    price = price_for(robux)
    bal   = get_balance(uid)

    if bal < price:
        await cb.answer(f"❌ Balans yetarli emas!\nKerak: {price:,} so'm\nBalans: {bal:,} so'm", show_alert=True); return

    sub_balance(uid, price)
    oid = add_order(uid, cb.from_user.username or "user", u[2], robux, price)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborildi (tasdiqlash)", callback_data=f"ook_{oid}")
    b.button(text="❌ Rad etish (qaytarish)",  callback_data=f"ono_{oid}")
    b.adjust(1)

    try:
        await bot.send_message(ADMIN_ID,
            f"🛒 **Robux buyurtma #{oid}**\n\n"
            f"👤 @{cb.from_user.username or '-'} (`{uid}`)\n"
            f"🎮 Roblox Nick: **{u[2]}**\n"
            f"🪙 Miqdor: **{robux} Robux**\n"
            f"💵 Narx: **{price:,} so'm**\n"
            f"🕐 {now()}",
            reply_markup=b.as_markup())
    except: pass

    await cb.message.answer(
        f"✅ Buyurtma qabul qilindi!\n\n🪙 **{robux} Robux**\n"
        f"💵 {price:,} so'm balansdan ayirildi.\n📋 Buyurtma #{oid}\n\n"
        f"Admin Roblox accountingizga robux yuboradi. Kuting!"
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("ook_"))
async def cb_ook(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    oid = int(cb.data.split("_")[1])
    o = get_order(oid)
    if not o or o[6] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    approve_order(oid)
    try: await bot.send_message(o[1], f"🎉 **{o[4]} Robux** Roblox accountingizga yuborildi!\n📋 Buyurtma #{oid}", reply_markup=main_kb())
    except: pass
    try: await cb.message.edit_text(cb.message.text + f"\n\n✅ TASDIQLANDI ({now()})")
    except: pass
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("ono_"))
async def cb_ono(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    oid = int(cb.data.split("_")[1])
    o = get_order(oid)
    if not o or o[6] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True); return
    reject_order(oid)
    try: await bot.send_message(o[1], f"❌ Buyurtma #{oid} rad etildi.\n💰 {o[5]:,} so'm qaytarildi.", reply_markup=main_kb())
    except: pass
    try: await cb.message.edit_text(cb.message.text + f"\n\n❌ RAD ETILDI + pul qaytarildi ({now()})")
    except: pass
    await cb.answer("❌ Rad etildi!")

# ══════════════════════════════════════════════
# TRADELAR (sahifalash)
# ══════════════════════════════════════════════
@dp.message(F.text == "🔄 Tradelar")
async def cmd_trades(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    items = active_trades()
    if not items:
        await msg.answer("🔄 Hozircha faol tradelar yo'q.\n\n➕ Trade qo'shish tugmasini bosing!"); return
    await _send_trade_page_new(msg, items, 0)

async def _send_trade_page_new(msg: types.Message, items, page):
    t = items[page]
    # id=0,user_id=1,username=2,roblox_nick=3,name=4,bio=5,photo_id=6,status=7,created_at=8
    caption = (
        f"🔄 **Trade #{t[0]}** [{page+1}/{len(items)}]\n\n"
        f"🎮 {t[3]} (@{t[2]})\n"
        f"📦 **{t[4]}**\n📝 {t[5]}\n📅 {t[8]}"
    )
    b = InlineKeyboardBuilder()
    if page > 0:             b.button(text="⬅️ Oldingi", callback_data=f"tp_{page-1}")
    if page < len(items)-1:  b.button(text="➡️ Keyingi", callback_data=f"tp_{page+1}")
    b.adjust(2)
    if t[6]:
        await msg.answer_photo(t[6], caption=caption, reply_markup=b.as_markup())
    else:
        await msg.answer(caption, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("tp_"))
async def cb_tp(cb: types.CallbackQuery):
    page  = int(cb.data.split("_")[1])
    items = active_trades()
    if not items:
        await cb.answer("Tradelar yo'q!", show_alert=True); return
    page = max(0, min(page, len(items)-1))
    t = items[page]
    caption = (
        f"🔄 **Trade #{t[0]}** [{page+1}/{len(items)}]\n\n"
        f"🎮 {t[3]} (@{t[2]})\n"
        f"📦 **{t[4]}**\n📝 {t[5]}\n📅 {t[8]}"
    )
    b = InlineKeyboardBuilder()
    if page > 0:             b.button(text="⬅️ Oldingi", callback_data=f"tp_{page-1}")
    if page < len(items)-1:  b.button(text="➡️ Keyingi", callback_data=f"tp_{page+1}")
    b.adjust(2)
    await _send_or_edit(cb, t[6], caption, b.as_markup())
    await cb.answer()

# ══════════════════════════════════════════════
# TRADE QO'SHISH
# ══════════════════════════════════════════════
@dp.message(F.text == "➕ Trade qo'shish")
async def cmd_trade_add(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    await msg.answer("📦 E'lon sarlavhasi yozing\n(masalan: Korblox x10 taklif qilaman):", reply_markup=cancel_kb())
    await state.set_state(TradeAdd.name)

@dp.message(TradeAdd.name)
async def ta_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(t_name=msg.text.strip())
    await msg.answer("📝 Bio yozing (nima taklif qilyapsiz, nima xohlaysiz):")
    await state.set_state(TradeAdd.bio)

@dp.message(TradeAdd.bio)
async def ta_bio(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(t_bio=msg.text.strip())
    await msg.answer("📸 Rasm yuboring yoki o'tkazib yuboring:", reply_markup=skip_cancel_kb())
    await state.set_state(TradeAdd.photo)

@dp.message(TradeAdd.photo, F.photo)
async def ta_photo(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    uid = msg.from_user.id; uname = msg.from_user.username or "user"; u = get_user(uid)
    photo_id = msg.photo[-1].file_id
    tid = add_trade(uid, uname, u[2], d["t_name"], d["t_bio"], photo_id)
    await state.clear()
    try:
        await bot.send_photo(ADMIN_ID, photo_id, caption=f"🔄 Yangi trade #{tid}\n👤 @{uname}\n📦 {d['t_name']}\n📝 {d['t_bio']}")
    except: pass
    await msg.answer(f"✅ Trade #{tid} e'lon qilindi!", reply_markup=main_kb())

@dp.message(TradeAdd.photo)
async def ta_no_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    d = await state.get_data()
    uid = msg.from_user.id; uname = msg.from_user.username or "user"; u = get_user(uid)
    tid = add_trade(uid, uname, u[2], d["t_name"], d["t_bio"], None)
    await state.clear()
    try:
        await bot.send_message(ADMIN_ID, f"🔄 Yangi trade #{tid}\n👤 @{uname}\n📦 {d['t_name']}\n📝 {d['t_bio']}")
    except: pass
    await msg.answer(f"✅ Trade #{tid} e'lon qilindi!", reply_markup=main_kb())

# ══════════════════════════════════════════════
# SOTUVLAR (sahifalash)
# ══════════════════════════════════════════════
@dp.message(F.text == "📊 Sotuvlar")
async def cmd_sales(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    items = active_sales()
    if not items:
        await msg.answer("📊 Hozircha sotuvdagi buyumlar yo'q.\n\n➕ Sotish qo'shish tugmasini bosing!"); return
    await _send_sale_page_new(msg, items, 0)

async def _send_sale_page_new(msg: types.Message, items, page):
    s = items[page]
    # id=0,user_id=1,username=2,roblox_nick=3,name=4,photo_id=5,currency=6,price=7,status=8,created_at=9
    caption = (
        f"🛍 **Sotuv #{s[0]}** [{page+1}/{len(items)}]\n\n"
        f"🎮 {s[3]} (@{s[2]})\n"
        f"📦 **{s[4]}**\n💰 {s[7]:,} {s[6]}\n📅 {s[9]}"
    )
    b = InlineKeyboardBuilder()
    if page > 0:             b.button(text="⬅️ Oldingi", callback_data=f"sp_{page-1}")
    if page < len(items)-1:  b.button(text="➡️ Keyingi", callback_data=f"sp_{page+1}")
    b.adjust(2)
    if s[5]:
        await msg.answer_photo(s[5], caption=caption, reply_markup=b.as_markup())
    else:
        await msg.answer(caption, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("sp_"))
async def cb_sp(cb: types.CallbackQuery):
    page  = int(cb.data.split("_")[1])
    items = active_sales()
    if not items:
        await cb.answer("Sotuvlar yo'q!", show_alert=True); return
    page = max(0, min(page, len(items)-1))
    s = items[page]
    caption = (
        f"🛍 **Sotuv #{s[0]}** [{page+1}/{len(items)}]\n\n"
        f"🎮 {s[3]} (@{s[2]})\n"
        f"📦 **{s[4]}**\n💰 {s[7]:,} {s[6]}\n📅 {s[9]}"
    )
    b = InlineKeyboardBuilder()
    if page > 0:             b.button(text="⬅️ Oldingi", callback_data=f"sp_{page-1}")
    if page < len(items)-1:  b.button(text="➡️ Keyingi", callback_data=f"sp_{page+1}")
    b.adjust(2)
    await _send_or_edit(cb, s[5], caption, b.as_markup())
    await cb.answer()

# ══════════════════════════════════════════════
# SOTISH QO'SHISH
# ══════════════════════════════════════════════
@dp.message(F.text == "➕ Sotish qo'shish")
async def cmd_sale_add(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    await msg.answer("📦 Nima sotmoqchisiz? Nom yozing:", reply_markup=cancel_kb())
    await state.set_state(SaleAdd.name)

@dp.message(SaleAdd.name)
async def sa_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(s_name=msg.text.strip())
    await msg.answer("📸 Rasm yuboring (ixtiyoriy):", reply_markup=skip_cancel_kb())
    await state.set_state(SaleAdd.photo)

@dp.message(SaleAdd.photo, F.photo)
async def sa_photo(msg: types.Message, state: FSMContext):
    await state.update_data(s_photo=msg.photo[-1].file_id)
    await _ask_currency(msg, state)

@dp.message(SaleAdd.photo)
async def sa_no_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(s_photo=None)
    await _ask_currency(msg, state)

async def _ask_currency(msg: types.Message, state: FSMContext):
    b = InlineKeyboardBuilder()
    b.button(text="💵 So'm (UZS)", callback_data="sc_som")
    b.button(text="🪙 Robux",      callback_data="sc_robux")
    b.adjust(2)
    await msg.answer("💱 Valyutani tanlang:", reply_markup=b.as_markup())
    await state.set_state(SaleAdd.currency)

@dp.callback_query(F.data.startswith("sc_"))
async def cb_sc(cb: types.CallbackQuery, state: FSMContext):
    cur = "so'm" if cb.data == "sc_som" else "Robux"
    await state.update_data(s_currency=cur)
    await cb.message.answer(f"💰 Narxni yozing ({cur} da):", reply_markup=cancel_kb())
    await state.set_state(SaleAdd.price)
    await cb.answer()

@dp.message(SaleAdd.price)
async def sa_price(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    txt = msg.text.strip().replace(" ","").replace(",","")
    if not txt.isdigit():
        await msg.answer("❌ Faqat raqam kiriting:"); return
    d = await state.get_data()
    uid = msg.from_user.id; uname = msg.from_user.username or "user"; u = get_user(uid)
    sid = add_sale(uid, uname, u[2], d["s_name"], d.get("s_photo"), d["s_currency"], int(txt))
    await state.clear()
    try:
        if d.get("s_photo"):
            await bot.send_photo(ADMIN_ID, d["s_photo"], caption=f"🛍 Yangi sotuv #{sid}\n👤 @{uname}\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}")
        else:
            await bot.send_message(ADMIN_ID, f"🛍 Yangi sotuv #{sid}\n👤 @{uname}\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}")
    except: pass
    await msg.answer(f"✅ Sotuv #{sid} e'lon qilindi!\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}", reply_markup=main_kb())

# ══════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════
@dp.message(F.text == "💬 Bizning chatimiz")
async def cmd_chat(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state): return
    b = InlineKeyboardBuilder()
    b.button(text="💬 Chatga kirish", url="https://t.me/roblox_uz")
    await msg.answer("💬 Rasmiy chatimizga xush kelibsiz!", reply_markup=b.as_markup())

# ══════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════
@dp.message(Command("admin"))
async def cmd_admin(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("❌ Ruxsat yo'q!"); return
    tr = active_trades(); sl = active_sales(); or_ = pending_orders()
    b = InlineKeyboardBuilder()
    b.button(text=f"📦 Kutayotgan buyurtmalar ({len(or_)})", callback_data="adm_ord")
    b.button(text=f"🔄 Barcha tradelar ({len(tr)})",         callback_data="adm_tr")
    b.button(text=f"🛍 Barcha sotuvlar ({len(sl)})",          callback_data="adm_sl")
    b.button(text="📢 Hammaga xabar",                         callback_data="adm_bc")
    b.adjust(1)
    await msg.answer(
        f"🛠 **Admin Panel**\n\n"
        f"👥 Foydalanuvchilar: **{users_count()}**\n"
        f"📦 Kutayotgan buyurtmalar: **{len(or_)}**\n"
        f"🔄 Faol tradelar: **{len(tr)}**\n"
        f"🛍 Faol sotuvlar: **{len(sl)}**",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "adm_ord")
async def adm_ord(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    orders = pending_orders()
    if not orders:
        await cb.answer("Kutayotgan buyurtmalar yo'q!", show_alert=True); return
    for o in orders[:10]:
        b = InlineKeyboardBuilder()
        b.button(text="✅ Yuborildi", callback_data=f"ook_{o[0]}")
        b.button(text="❌ Rad etish", callback_data=f"ono_{o[0]}")
        b.adjust(2)
        await cb.message.answer(
            f"🛒 **Buyurtma #{o[0]}**\n👤 @{o[2]}\n🎮 {o[3]}\n🪙 {o[4]} Robux — {o[5]:,} so'm\n🕐 {o[7]}",
            reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_tr")
async def adm_tr(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    items = active_trades()
    if not items:
        await cb.answer("Tradelar yo'q!", show_alert=True); return
    for t in items[:10]:
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"etrade_{t[0]}")
        b.button(text="🗑 O'chirish",  callback_data=f"dtrade_{t[0]}")
        b.adjust(2)
        caption = f"🔄 **#{t[0]}** {t[4]}\n🎮 {t[3]} (@{t[2]})\n📝 {t[5]}"
        if t[6]:
            await cb.message.answer_photo(t[6], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_sl")
async def adm_sl(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    items = active_sales()
    if not items:
        await cb.answer("Sotuvlar yo'q!", show_alert=True); return
    for s in items[:10]:
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"esale_{s[0]}")
        b.button(text="🗑 O'chirish",  callback_data=f"dsale_{s[0]}")
        b.adjust(2)
        caption = f"🛍 **#{s[0]}** {s[4]}\n🎮 {s[3]} (@{s[2]})\n💰 {s[7]:,} {s[6]}"
        if s[5]:
            await cb.message.answer_photo(s[5], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

# ── Broadcast ──
@dp.callback_query(F.data == "adm_bc")
async def adm_bc(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.message.answer("📸 Rasm yuboring yoki o'tkazib yuboring:", reply_markup=skip_cancel_kb())
    await state.set_state(Broadcast.photo); await cb.answer()

@dp.message(Broadcast.photo, F.photo)
async def bc_photo(msg: types.Message, state: FSMContext):
    await state.update_data(bc_photo=msg.photo[-1].file_id)
    await msg.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.photo)
async def bc_no_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    await state.update_data(bc_photo=None)
    await msg.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def bc_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi.", reply_markup=main_kb()); return
    d = await state.get_data()
    text = msg.text.strip(); photo = d.get("bc_photo")
    await state.clear()
    uids = all_user_ids()
    sent = 0
    for uid in uids:
        try:
            if photo: await bot.send_photo(uid, photo, caption=text)
            else:     await bot.send_message(uid, text)
            sent += 1
        except: pass
        await asyncio.sleep(0.05)
    await msg.answer(f"✅ Xabar {sent}/{len(uids)} ta foydalanuvchiga yuborildi!", reply_markup=main_kb())

# ── /addbalance ──
@dp.message(Command("addbalance"))
async def cmd_addbalance(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("❌ Ruxsat yo'q!"); return
    parts = msg.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.answer("❌ Format: /addbalance <user_id> <summa>"); return
    uid, amt = int(parts[1]), int(parts[2])
    add_balance(uid, amt)
    try: await bot.send_message(uid, f"💰 Hisobingizga **{amt:,} so'm** qo'shildi!", reply_markup=main_kb())
    except: pass
    await msg.answer(f"✅ {uid} ga {amt:,} so'm qo'shildi.")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
async def main():
    init_db()
    logging.info("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
ENDOFFILE
echo "Done"
