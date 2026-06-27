import os
import asyncio
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════
BOT_TOKEN        = os.getenv("BOT_TOKEN")
ADMIN_ID         = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI        = os.getenv("MONGO_URI")
REQUIRED_CHANNEL = os.getenv("CHANNEL", "@bulldrop_n1")
CARD_NUMBER      = os.getenv("CARD_NUMBER", "9860 1234 5678 9012")
CARD_OWNER       = os.getenv("CARD_OWNER", "ADMIN NOMI")
CHAT_LINK        = os.getenv("CHAT_LINK", "https://t.me/roblox_uz")

# ═══════════════════════════════════════════════════════
# MONGODB
# ═══════════════════════════════════════════════════════
mongo_client = AsyncIOMotorClient(MONGO_URI)
mdb          = mongo_client["roblox_bot"]
users        = mdb["users"]
deposits     = mdb["deposits"]
orders       = mdb["orders"]
trades       = mdb["trades"]
sales        = mdb["sales"]

async def init_indexes():
    await users.create_index("user_id", unique=True)
    await deposits.create_index("user_id")
    await orders.create_index("user_id")
    await trades.create_index([("user_id", 1), ("status", 1)])
    await sales.create_index([("user_id", 1), ("status", 1)])

# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════
def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def short_id(oid):
    return str(oid)[-6:].upper()

async def get_user(uid):
    return await users.find_one({"user_id": uid})

async def upsert_user(uid, uname):
    upd = {
        "$set": {"username": uname, "last_seen": now()},
        "$setOnInsert": {"user_id": uid, "balance": 0, "total_deposited": 0, "joined": now()}
    }
    await users.update_one({"user_id": uid}, upd, upsert=True)

async def get_balance(uid):
    u = await users.find_one({"user_id": uid}, {"balance": 1})
    return u["balance"] if u else 0

async def add_balance(uid, amt):
    await users.update_one({"user_id": uid}, {"$inc": {"balance": amt, "total_deposited": amt}})

async def sub_balance(uid, amt):
    await users.update_one({"user_id": uid}, {"$inc": {"balance": -amt}})

async def users_count():
    return await users.count_documents({})

async def all_user_ids():
    return [u["user_id"] async for u in users.find({}, {"user_id": 1})]

# deposits
async def add_deposit(uid, uname, nick, amount, photo_id):
    r = await deposits.insert_one({
        "user_id": uid, "username": uname, "roblox_nick": nick,
        "amount": amount, "photo_id": photo_id, "status": "pending", "created_at": now()
    })
    return r.inserted_id

async def get_deposit(did):
    return await deposits.find_one({"_id": ObjectId(str(did))})

async def approve_deposit(did):
    dep = await deposits.find_one({"_id": ObjectId(str(did))})
    if dep:
        await deposits.update_one({"_id": ObjectId(str(did))}, {"$set": {"status": "approved"}})
        await users.update_one({"user_id": dep["user_id"]}, {"$inc": {"balance": dep["amount"], "total_deposited": dep["amount"]}})

async def reject_deposit(did):
    await deposits.update_one({"_id": ObjectId(str(did))}, {"$set": {"status": "rejected"}})

# orders
async def add_order(uid, uname, nick, robux, price):
    r = await orders.insert_one({
        "user_id": uid, "username": uname, "roblox_nick": nick,
        "robux_amount": robux, "price_sum": price, "status": "pending", "created_at": now()
    })
    return r.inserted_id

async def get_order(oid):
    return await orders.find_one({"_id": ObjectId(str(oid))})

async def approve_order(oid):
    await orders.update_one({"_id": ObjectId(str(oid))}, {"$set": {"status": "approved"}})

async def reject_order(oid):
    o = await orders.find_one({"_id": ObjectId(str(oid))})
    if o and o["status"] == "pending":
        await orders.update_one({"_id": ObjectId(str(oid))}, {"$set": {"status": "rejected"}})
        await users.update_one({"user_id": o["user_id"]}, {"$inc": {"balance": o["price_sum"]}})

async def pending_orders():
    return [o async for o in orders.find({"status": "pending"}).sort("_id", -1).limit(10)]

# trades
async def add_trade(uid, uname, nick, name, bio, photo_id):
    r = await trades.insert_one({
        "user_id": uid, "username": uname, "roblox_nick": nick,
        "name": name, "bio": bio, "photo_id": photo_id,
        "status": "active", "created_at": now()
    })
    return r.inserted_id

async def get_trade(tid):
    return await trades.find_one({"_id": ObjectId(str(tid))})

async def active_trades():
    return [t async for t in trades.find({"status": "active"}).sort("_id", -1)]

async def my_trades(uid):
    return [t async for t in trades.find({"user_id": uid, "status": "active"}).sort("_id", -1)]

async def edit_trade(tid, name, bio):
    await trades.update_one({"_id": ObjectId(str(tid))}, {"$set": {"name": name, "bio": bio}})

async def delete_trade(tid):
    await trades.update_one({"_id": ObjectId(str(tid))}, {"$set": {"status": "deleted"}})

# sales
async def add_sale(uid, uname, nick, name, photo_id, currency, price):
    r = await sales.insert_one({
        "user_id": uid, "username": uname, "roblox_nick": nick,
        "name": name, "photo_id": photo_id, "currency": currency,
        "price": price, "status": "active", "created_at": now()
    })
    return r.inserted_id

async def get_sale(sid):
    return await sales.find_one({"_id": ObjectId(str(sid))})

async def active_sales():
    return [s async for s in sales.find({"status": "active"}).sort("_id", -1)]

async def my_sales(uid):
    return [s async for s in sales.find({"user_id": uid, "status": "active"}).sort("_id", -1)]

async def edit_sale(sid, name, price):
    await sales.update_one({"_id": ObjectId(str(sid))}, {"$set": {"name": name, "price": price}})

async def delete_sale(sid):
    await sales.update_one({"_id": ObjectId(str(sid))}, {"$set": {"status": "deleted"}})

# ═══════════════════════════════════════════════════════
# NARXLAR
# ═══════════════════════════════════════════════════════
ROBUX_PRICES = [
    (40, 7000), (80, 14000), (120, 21000), (160, 28000), (200, 35000),
    (240, 42000), (280, 49000), (320, 56000), (360, 63000), (400, 65000),
    (440, 72000), (480, 79000), (520, 86000), (560, 93000), (700, 100000),
    (740, 107000), (780, 114000), (820, 121000), (860, 128000),
    (1000, 132000), (1500, 197000), (2000, 265000),
]

def price_for(robux):
    for r, p in ROBUX_PRICES:
        if r == robux:
            return p
    return None

DEPOSIT_OPTIONS = [5000, 10000, 15000, 20000, 30000, 50000, 100000]

# ═══════════════════════════════════════════════════════
# STATES
# ═══════════════════════════════════════════════════════
class Dep(StatesGroup):
    custom_amount = State()
    check_photo   = State()

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

class AdminCmd(StatesGroup):
    add_balance = State()

# ═══════════════════════════════════════════════════════
# BOT + DP
# ═══════════════════════════════════════════════════════
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp  = Dispatcher(storage=MemoryStorage())

# ═══════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════
def sub_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")
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
    b.button(text="💬 Chat")
    b.adjust(2, 2, 2, 2)
    return b.as_markup(resize_keyboard=True)

def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="❌ Bekor qilish")
    return b.as_markup(resize_keyboard=True)

def skip_cancel_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="⏭ O'tkazib yuborish")
    b.button(text="❌ Bekor qilish")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)

# ═══════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════
async def is_sub(uid: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=uid)
        return m.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.error(f"Sub check xato: {e}")
        return False

async def check_access(msg: types.Message, state: FSMContext) -> bool:
    uid = msg.from_user.id
    if not await is_sub(uid):
        await msg.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb())
        return False
    return True

async def _send_or_edit(cb: types.CallbackQuery, photo_id, text, markup):
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
        logging.warning(f"edit xato: {e}")
        try:
            if photo_id:
                await cb.message.answer_photo(photo_id, caption=text, reply_markup=markup)
            else:
                await cb.message.answer(text, reply_markup=markup)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════
# /START + OBUNA
# ═══════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    if not await is_sub(uid):
        await msg.answer("👋 Salom! Botdan foydalanish uchun avval kanalimizga obuna bo'ling!", reply_markup=sub_kb())
        return
    await upsert_user(uid, msg.from_user.username or "user")
    u   = await get_user(uid)
    bal = u.get("balance", 0) if u else 0
    await msg.answer(
        f"🌟 *Assalomu alaykum, {msg.from_user.first_name}!*\n\n"
        f"💰 Balans: *{bal:,} so'm*\n\n"
        f"👇 Quyidagi menyudan foydalaning:",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not await is_sub(uid):
        await cb.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)
        return
    try:
        await cb.message.delete()
    except Exception:
        pass
    await upsert_user(uid, cb.from_user.username or "user")
    await cb.message.answer("✅ Xush kelibsiz!", reply_markup=main_kb())
    await cb.answer()

# ═══════════════════════════════════════════════════════
# PROFIL
# ═══════════════════════════════════════════════════════
@dp.message(F.text == "👤 Profil")
async def cmd_profile(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    uid = msg.from_user.id
    u   = await get_user(uid)
    tr  = await my_trades(uid)
    sl  = await my_sales(uid)
    b   = InlineKeyboardBuilder()
    if tr:
        b.button(text=f"🔄 Mening tradelarim ({len(tr)})", callback_data="my_trades_0")
    if sl:
        b.button(text=f"🛍 Mening sotuvlarim ({len(sl)})", callback_data="my_sales_0")
    b.adjust(1)
    await msg.answer(
        f"👤 *Profilingiz*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"💰 Balans: *{u.get('balance', 0):,} so'm*\n"
        f"📈 Jami kiritilgan: *{u.get('total_deposited', 0):,} so'm*\n"
        f"📅 Ro'yxat: {u.get('joined', '-')}\n\n"
        f"🔄 Faol tradelarim: {len(tr)}\n"
        f"🛍 Faol sotuvlarim: {len(sl)}",
        reply_markup=b.as_markup() if (tr or sl) else None
    )

@dp.callback_query(F.data.startswith("my_trades_"))
async def cb_my_trades(cb: types.CallbackQuery):
    uid  = cb.from_user.id
    page = int(cb.data.split("_")[2])
    items = await my_trades(uid)
    if not items:
        await cb.answer("Faol trade e'lonlaringiz yo'q!", show_alert=True)
        return
    page = max(0, min(page, len(items) - 1))
    t    = items[page]
    caption = f"🔄 *{t['name']}* [{page+1}/{len(items)}]\n📝 {t['bio']}\n📅 {t['created_at']}"
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="⬅️", callback_data=f"my_trades_{page-1}")
    if page < len(items) - 1:
        b.button(text="➡️", callback_data=f"my_trades_{page+1}")
    b.button(text="✏️ Tahrirlash", callback_data=f"etrade_{t['_id']}")
    b.button(text="🗑 O'chirish",  callback_data=f"dtrade_{t['_id']}")
    b.adjust(2, 2)
    await _send_or_edit(cb, t.get("photo_id"), caption, b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("my_sales_"))
async def cb_my_sales(cb: types.CallbackQuery):
    uid  = cb.from_user.id
    page = int(cb.data.split("_")[2])
    items = await my_sales(uid)
    if not items:
        await cb.answer("Faol sotuv e'lonlaringiz yo'q!", show_alert=True)
        return
    page = max(0, min(page, len(items) - 1))
    s    = items[page]
    caption = f"🛍 *{s['name']}* [{page+1}/{len(items)}]\n💰 {s['price']:,} {s['currency']}\n📅 {s['created_at']}"
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="⬅️", callback_data=f"my_sales_{page-1}")
    if page < len(items) - 1:
        b.button(text="➡️", callback_data=f"my_sales_{page+1}")
    b.button(text="✏️ Tahrirlash", callback_data=f"esale_{s['_id']}")
    b.button(text="🗑 O'chirish",  callback_data=f"dsale_{s['_id']}")
    b.adjust(2, 2)
    await _send_or_edit(cb, s.get("photo_id"), caption, b.as_markup())
    await cb.answer()

# ═══════════════════════════════════════════════════════
# HISOB TO'LDIRISH
# ═══════════════════════════════════════════════════════
@dp.message(F.text == "💰 Hisob to'ldirish")
async def cmd_deposit(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    b = InlineKeyboardBuilder()
    for amt in DEPOSIT_OPTIONS:
        b.button(text=f"{amt:,} so'm", callback_data=f"damt_{amt}")
    b.button(text="✏️ Boshqa miqdor", callback_data="damt_custom")
    b.adjust(2)
    await msg.answer("💰 *Hisob to'ldirish*\n\nQancha to'ldirmoqchisiz?", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("damt_"))
async def cb_damt(cb: types.CallbackQuery, state: FSMContext):
    if not await is_sub(cb.from_user.id):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        return
    if cb.data == "damt_custom":
        await cb.message.answer("✏️ Miqdorni yozing (so'mda, min 1000):", reply_markup=cancel_kb())
        await state.set_state(Dep.custom_amount)
        await cb.answer()
        return
    amount = int(cb.data.split("_")[1])
    await state.update_data(dep_amount=amount)
    await _show_card(cb.message, amount)
    await cb.answer()

@dp.message(Dep.custom_amount)
async def dep_custom(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    txt = msg.text.strip().replace(" ", "").replace(",", "")
    if not txt.isdigit() or int(txt) < 1000:
        await msg.answer("❌ Minimum 1000 so'm kiriting:")
        return
    amount = int(txt)
    await state.update_data(dep_amount=amount)
    await _show_card(msg, amount)

async def _show_card(target, amount: int):
    b = InlineKeyboardBuilder()
    b.button(text="✅ To'lov qildim", callback_data="dep_paid")
    b.button(text="❌ Bekor qilish",  callback_data="dep_cancel")
    b.adjust(1)
    text = (
        f"💳 *To'lov ma'lumotlari*\n\n"
        f"💰 Miqdor: *{amount:,} so'm*\n\n"
        f"🏦 Karta raqami:\n`{CARD_NUMBER}`\n\n"
        f"👤 Karta egasi: *{CARD_OWNER}*\n\n"
        f"📌 Karta raqamiga bosib nusxa oling, to'lovni amalga oshiring va ✅ To'lov qildim tugmasini bosing."
    )
    await target.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "dep_paid")
async def cb_dep_paid(cb: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("dep_amount"):
        await cb.answer("❌ Xatolik! Qaytadan boshlang.", show_alert=True)
        await state.clear()
        return
    await cb.message.answer("📸 To'lov chekining rasmini yuboring (screenshot):", reply_markup=cancel_kb())
    await state.set_state(Dep.check_photo)
    await cb.answer()

@dp.callback_query(F.data == "dep_cancel")
async def cb_dep_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer("❌ Bekor qilindi.", reply_markup=main_kb())
    await cb.answer()

@dp.message(Dep.check_photo, F.photo)
async def dep_check_photo(msg: types.Message, state: FSMContext):
    uid      = msg.from_user.id
    uname    = msg.from_user.username or "user"
    u        = await get_user(uid)
    d        = await state.get_data()
    amount   = d.get("dep_amount", 0)
    photo_id = msg.photo[-1].file_id
    did      = await add_deposit(uid, uname, "", amount, photo_id)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"dok_{did}")
    b.button(text="❌ Rad etish",  callback_data=f"dno_{did}")
    b.adjust(2)
    try:
        await bot.send_photo(
            ADMIN_ID, photo_id,
            caption=(
                f"💰 *To'lov #{short_id(did)}*\n\n"
                f"👤 @{uname} (`{uid}`)\n"
                f"💵 Miqdor: *{amount:,} so'm*\n🕐 {now()}"
            ),
            reply_markup=b.as_markup()
        )
    except Exception as e:
        logging.error(f"Admin ga xato: {e}")
    await state.clear()
    await msg.answer(f"✅ Chek yuborildi! Admin tasdiqlashini kuting.\n📋 To'lov #{short_id(did)}", reply_markup=main_kb())

@dp.message(Dep.check_photo)
async def dep_not_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi.", reply_markup=main_kb())
        return
    await msg.answer("❌ Rasm yuboring (chek screenshoti):")

@dp.callback_query(F.data.startswith("dok_"))
async def cb_dok(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌", show_alert=True)
        return
    did = cb.data.split("_")[1]
    dep = await get_deposit(did)
    if not dep or dep["status"] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True)
        return
    await approve_deposit(did)
    try:
        await bot.send_message(dep["user_id"], f"✅ To'lovingiz tasdiqlandi!\n💰 *{dep['amount']:,} so'm* hisobingizga qo'shildi!", reply_markup=main_kb())
    except Exception:
        pass
    try:
        await cb.message.edit_caption(cb.message.caption + f"\n\n✅ TASDIQLANDI ({now()})")
    except Exception:
        pass
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("dno_"))
async def cb_dno(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("❌", show_alert=True)
        return
    did = cb.data.split("_")[1]
    dep = await get_deposit(did)
    if not dep or dep["status"] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True)
        return
    await reject_deposit(did)
    try:
        await bot.send_message(dep["user_id"], f"❌ To'lovingiz rad etildi.\n📋 #{short_id(ObjectId(str(did)))}\n\nAdmin bilan bog'laning.", reply_markup=main_kb())
    except Exception:
        pass
    try:
        await cb.message.edit_caption(cb.message.caption + f"\n\n❌ RAD ETILDI ({now()})")
    except Exception:
        pass
    await cb.answer("❌ Rad etildi!")

# ═══════════════════════════════════════════════════════
# ROBUX SOTIB OLISH
# ═══════════════════════════════════════════════════════
@dp.message(F.text == "🛒 Robux sotib olish")
async def cmd_buy(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    uid = msg.from_user.id
    bal = await get_balance(uid)
    lines = "\n".join([f"{'🔥' if r == 700 else '🪙'} {r} Robux — {p:,} so'm" for r, p in ROBUX_PRICES])
    b = InlineKeyboardBuilder()
    for r, p in ROBUX_PRICES:
        b.button(text=f"{r}Rbx — {p // 1000}k", callback_data=f"buy_{r}")
    b.adjust(3)
    await msg.answer(
        f"🔥 *ROBUX NARXLAR*\n💰 Balansingiz: *{bal:,} so'm*\n\n{lines}\n\n👇 Miqdorni tanlang:",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if not await is_sub(uid):
        await cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        return
    u = await get_user(uid)
    if not u:
        await cb.answer("❌ Avval /start yozing!", show_alert=True)
        return
    robux = int(cb.data.split("_")[1])
    price = price_for(robux)
    if price is None:
        await cb.answer("❌ Noto'g'ri miqdor!", show_alert=True)
        return
    bal = await get_balance(uid)
    if bal < price:
        await cb.answer(f"❌ Balans yetarli emas!\nKerak: {price:,} so'm\nBalans: {bal:,} so'm", show_alert=True)
        return
    await sub_balance(uid, price)
    oid = await add_order(uid, cb.from_user.username or "user", "", robux, price)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborildi", callback_data=f"ook_{oid}")
    b.button(text="❌ Rad etish", callback_data=f"ono_{oid}")
    b.adjust(2)
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🛒 *Robux buyurtma #{short_id(oid)}*\n\n"
            f"👤 @{cb.from_user.username or '-'} (`{uid}`)\n"
            f"🪙 Miqdor: *{robux} Robux*\n💵 Narx: *{price:,} so'm*\n🕐 {now()}",
            reply_markup=b.as_markup()
        )
    except Exception:
        pass
    await cb.message.answer(
        f"✅ Buyurtma qabul qilindi!\n\n🪙 *{robux} Robux*\n"
        f"💵 {price:,} so'm balansdan ayirildi.\n📋 Buyurtma #{short_id(oid)}\n\n"
        f"⏳ Admin Roblox accountingizga robux yuboradi. Kuting!",
        reply_markup=main_kb()
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("ook_"))
async def cb_ook(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    oid = cb.data.split("_")[1]
    o   = await get_order(oid)
    if not o or o["status"] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True)
        return
    await approve_order(oid)
    try:
        await bot.send_message(o["user_id"], f"🎉 *{o['robux_amount']} Robux* Roblox accountingizga yuborildi!\n📋 Buyurtma #{short_id(ObjectId(str(oid)))}", reply_markup=main_kb())
    except Exception:
        pass
    try:
        await cb.message.edit_text(cb.message.text + f"\n\n✅ TASDIQLANDI ({now()})")
    except Exception:
        pass
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("ono_"))
async def cb_ono(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    oid = cb.data.split("_")[1]
    o   = await get_order(oid)
    if not o or o["status"] != "pending":
        await cb.answer("Allaqachon ko'rilgan!", show_alert=True)
        return
    await reject_order(oid)
    try:
        await bot.send_message(o["user_id"], f"❌ Buyurtma #{short_id(ObjectId(str(oid)))} rad etildi.\n💰 {o['price_sum']:,} so'm qaytarildi.", reply_markup=main_kb())
    except Exception:
        pass
    try:
        await cb.message.edit_text(cb.message.text + f"\n\n❌ RAD ETILDI + pul qaytarildi ({now()})")
    except Exception:
        pass
    await cb.answer("❌ Rad etildi!")

# ═══════════════════════════════════════════════════════
# TRADELAR
# ═══════════════════════════════════════════════════════
@dp.message(F.text == "🔄 Tradelar")
async def cmd_trades(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    items = await active_trades()
    if not items:
        await msg.answer("🔄 Hozircha faol tradelar yo'q.\n\n➕ *Trade qo'shish* tugmasini bosing!")
        return
    await _send_trade_page(msg, items, 0, is_cb=False)

async def _send_trade_page(target, items, page, is_cb=True):
    t       = items[page]
    caption = (
        f"🔄 *Trade #{short_id(t['_id'])}* [{page+1}/{len(items)}]\n\n"
        f"👤 @{t.get('username', '-')}\n"
        f"📦 *{t['name']}*\n📝 {t['bio']}\n📅 {t['created_at']}"
    )
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="⬅️ Oldingi", callback_data=f"tp_{page-1}")
    if page < len(items) - 1:
        b.button(text="➡️ Keyingi", callback_data=f"tp_{page+1}")
    uname = t.get("username", "")
    if uname:
        b.button(text="💬 Murojaat", url=f"https://t.me/{uname}")
    b.adjust(2, 1)
    if is_cb:
        await _send_or_edit(target, t.get("photo_id"), caption, b.as_markup())
    else:
        if t.get("photo_id"):
            await target.answer_photo(t["photo_id"], caption=caption, reply_markup=b.as_markup())
        else:
            await target.answer(caption, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("tp_"))
async def cb_tp(cb: types.CallbackQuery):
    page  = int(cb.data.split("_")[1])
    items = await active_trades()
    if not items:
        await cb.answer("Tradelar yo'q!", show_alert=True)
        return
    page = max(0, min(page, len(items) - 1))
    await _send_trade_page(cb, items, page)
    await cb.answer()

@dp.message(F.text == "➕ Trade qo'shish")
async def cmd_trade_add(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    await msg.answer("📦 Trade sarlavhasi yozing\n(masalan: *Korblox x10 taklif qilaman*):", reply_markup=cancel_kb())
    await state.set_state(TradeAdd.name)

@dp.message(TradeAdd.name)
async def ta_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    if len(msg.text.strip()) < 5:
        await msg.answer("❌ Sarlavha kamida 5 ta belgi bo'lsin:")
        return
    await state.update_data(t_name=msg.text.strip())
    await msg.answer("📝 Bio yozing (nima taklif qilyapsiz, nima xohlaysiz):", reply_markup=cancel_kb())
    await state.set_state(TradeAdd.bio)

@dp.message(TradeAdd.bio)
async def ta_bio(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    await state.update_data(t_bio=msg.text.strip())
    await msg.answer("📸 Rasm yuboring (ixtiyoriy):", reply_markup=skip_cancel_kb())
    await state.set_state(TradeAdd.photo)

@dp.message(TradeAdd.photo, F.photo)
async def ta_photo(msg: types.Message, state: FSMContext):
    d        = await state.get_data()
    uid      = msg.from_user.id
    uname    = msg.from_user.username or "user"
    u        = await get_user(uid)
    photo_id = msg.photo[-1].file_id
    tid = await add_trade(uid, uname, "", d["t_name"], d["t_bio"], photo_id)
    await state.clear()
    try:
        await bot.send_photo(ADMIN_ID, photo_id, caption=f"🔄 Yangi trade #{short_id(tid)}\n👤 @{uname}\n📦 {d['t_name']}\n📝 {d['t_bio']}")
    except Exception:
        pass
    await msg.answer(f"✅ Trade e'lon qilindi! *#{short_id(tid)}*", reply_markup=main_kb())

@dp.message(TradeAdd.photo)
async def ta_no_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    d     = await state.get_data()
    uid   = msg.from_user.id
    uname = msg.from_user.username or "user"
    tid   = await add_trade(uid, uname, "", d["t_name"], d["t_bio"], None)
    await state.clear()
    try:
        await bot.send_message(ADMIN_ID, f"🔄 Yangi trade #{short_id(tid)}\n👤 @{uname}\n📦 {d['t_name']}\n📝 {d['t_bio']}")
    except Exception:
        pass
    await msg.answer(f"✅ Trade e'lon qilindi! *#{short_id(tid)}*", reply_markup=main_kb())

@dp.callback_query(F.data.startswith("etrade_"))
async def cb_etrade(cb: types.CallbackQuery, state: FSMContext):
    tid = cb.data.split("_")[1]
    t   = await get_trade(tid)
    if not t or (t["user_id"] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True)
        return
    await state.update_data(edit_trade_id=tid)
    await cb.message.answer("✏️ Yangi nom yozing:", reply_markup=cancel_kb())
    await state.set_state(TradeEdit.name)
    await cb.answer()

@dp.message(TradeEdit.name)
async def etrade_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    await state.update_data(new_name=msg.text.strip())
    await msg.answer("📝 Yangi bio yozing:", reply_markup=cancel_kb())
    await state.set_state(TradeEdit.bio)

@dp.message(TradeEdit.bio)
async def etrade_bio(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    d = await state.get_data()
    await edit_trade(d["edit_trade_id"], d["new_name"], msg.text.strip())
    await state.clear()
    await msg.answer("✅ Trade yangilandi!", reply_markup=main_kb())

@dp.callback_query(F.data.startswith("dtrade_"))
async def cb_dtrade(cb: types.CallbackQuery):
    tid = cb.data.split("_")[1]
    t   = await get_trade(tid)
    if not t or (t["user_id"] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True)
        return
    await delete_trade(tid)
    try:
        if cb.message.photo:
            await cb.message.edit_caption("🗑 E'lon o'chirildi.")
        else:
            await cb.message.edit_text("🗑 E'lon o'chirildi.")
    except Exception:
        pass
    await cb.answer("✅ O'chirildi!")

# ═══════════════════════════════════════════════════════
# SOTUVLAR
# ═══════════════════════════════════════════════════════
@dp.message(F.text == "📊 Sotuvlar")
async def cmd_sales(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    items = await active_sales()
    if not items:
        await msg.answer("📊 Hozircha sotuvdagi buyumlar yo'q.\n\n➕ *Sotish qo'shish* tugmasini bosing!")
        return
    await _send_sale_page(msg, items, 0, is_cb=False)

async def _send_sale_page(target, items, page, is_cb=True):
    s       = items[page]
    caption = (
        f"🛍 *Sotuv #{short_id(s['_id'])}* [{page+1}/{len(items)}]\n\n"
        f"👤 @{s.get('username', '-')}\n"
        f"📦 *{s['name']}*\n💰 {s['price']:,} {s['currency']}\n📅 {s['created_at']}"
    )
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="⬅️ Oldingi", callback_data=f"sp_{page-1}")
    if page < len(items) - 1:
        b.button(text="➡️ Keyingi", callback_data=f"sp_{page+1}")
    uname = s.get("username", "")
    if uname:
        b.button(text="💬 Murojaat", url=f"https://t.me/{uname}")
    b.adjust(2, 1)
    if is_cb:
        await _send_or_edit(target, s.get("photo_id"), caption, b.as_markup())
    else:
        if s.get("photo_id"):
            await target.answer_photo(s["photo_id"], caption=caption, reply_markup=b.as_markup())
        else:
            await target.answer(caption, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("sp_"))
async def cb_sp(cb: types.CallbackQuery):
    page  = int(cb.data.split("_")[1])
    items = await active_sales()
    if not items:
        await cb.answer("Sotuvlar yo'q!", show_alert=True)
        return
    page = max(0, min(page, len(items) - 1))
    await _send_sale_page(cb, items, page)
    await cb.answer()

@dp.message(F.text == "➕ Sotish qo'shish")
async def cmd_sale_add(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    await msg.answer("📦 Nima sotmoqchisiz? Nom yozing:", reply_markup=cancel_kb())
    await state.set_state(SaleAdd.name)

@dp.message(SaleAdd.name)
async def sa_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
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
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
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
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    txt = msg.text.strip().replace(" ", "").replace(",", "")
    if not txt.isdigit():
        await msg.answer("❌ Faqat raqam kiriting:")
        return
    d     = await state.get_data()
    uid   = msg.from_user.id
    uname = msg.from_user.username or "user"
    sid   = await add_sale(uid, uname, "", d["s_name"], d.get("s_photo"), d["s_currency"], int(txt))
    await state.clear()
    try:
        cap = f"🛍 Yangi sotuv #{short_id(sid)}\n👤 @{uname}\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}"
        if d.get("s_photo"):
            await bot.send_photo(ADMIN_ID, d["s_photo"], caption=cap)
        else:
            await bot.send_message(ADMIN_ID, cap)
    except Exception:
        pass
    await msg.answer(
        f"✅ Sotuv e'lon qilindi! *#{short_id(sid)}*\n📦 {d['s_name']}\n💰 {int(txt):,} {d['s_currency']}",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data.startswith("esale_"))
async def cb_esale(cb: types.CallbackQuery, state: FSMContext):
    sid = cb.data.split("_")[1]
    s   = await get_sale(sid)
    if not s or (s["user_id"] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True)
        return
    await state.update_data(edit_sale_id=sid)
    await cb.message.answer("✏️ Yangi nom yozing:", reply_markup=cancel_kb())
    await state.set_state(SaleEdit.name)
    await cb.answer()

@dp.message(SaleEdit.name)
async def esale_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    await state.update_data(new_name=msg.text.strip())
    await msg.answer("💰 Yangi narx (raqam):", reply_markup=cancel_kb())
    await state.set_state(SaleEdit.price)

@dp.message(SaleEdit.price)
async def esale_price(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    txt = msg.text.strip().replace(" ", "")
    if not txt.isdigit():
        await msg.answer("❌ Faqat raqam:")
        return
    d = await state.get_data()
    await edit_sale(d["edit_sale_id"], d["new_name"], int(txt))
    await state.clear()
    await msg.answer("✅ Sotuv yangilandi!", reply_markup=main_kb())

@dp.callback_query(F.data.startswith("dsale_"))
async def cb_dsale(cb: types.CallbackQuery):
    sid = cb.data.split("_")[1]
    s   = await get_sale(sid)
    if not s or (s["user_id"] != cb.from_user.id and cb.from_user.id != ADMIN_ID):
        await cb.answer("Ruxsat yo'q!", show_alert=True)
        return
    await delete_sale(sid)
    try:
        if cb.message.photo:
            await cb.message.edit_caption("🗑 E'lon o'chirildi.")
        else:
            await cb.message.edit_text("🗑 E'lon o'chirildi.")
    except Exception:
        pass
    await cb.answer("✅ O'chirildi!")

# ═══════════════════════════════════════════════════════
# CHAT
# ═══════════════════════════════════════════════════════
@dp.message(F.text == "💬 Chat")
async def cmd_chat(msg: types.Message, state: FSMContext):
    if not await check_access(msg, state):
        return
    b = InlineKeyboardBuilder()
    b.button(text="💬 Chatga kirish", url=CHAT_LINK)
    await msg.answer("💬 Rasmiy chatimizga xush kelibsiz!", reply_markup=b.as_markup())

# ═══════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════
@dp.message(Command("admin"))
async def cmd_admin(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("❌ Ruxsat yo'q!")
        return
    tr   = await active_trades()
    sl   = await active_sales()
    or_  = await pending_orders()
    cnt  = await users_count()
    b    = InlineKeyboardBuilder()
    b.button(text=f"📦 Buyurtmalar ({len(or_)})", callback_data="adm_ord")
    b.button(text=f"🔄 Tradelar ({len(tr)})",     callback_data="adm_tr")
    b.button(text=f"🛍 Sotuvlar ({len(sl)})",      callback_data="adm_sl")
    b.button(text="📢 Broadcast",                  callback_data="adm_bc")
    b.button(text="➕ Balans qo'shish",            callback_data="adm_addbal")
    b.adjust(2, 2, 1)
    await msg.answer(
        f"🛠 *Admin Panel*\n\n👥 Foydalanuvchilar: *{cnt}*\n"
        f"📦 Kutayotgan buyurtmalar: *{len(or_)}*\n"
        f"🔄 Faol tradelar: *{len(tr)}*\n🛍 Faol sotuvlar: *{len(sl)}*",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "adm_ord")
async def adm_ord(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    ol = await pending_orders()
    if not ol:
        await cb.answer("Kutayotgan buyurtmalar yo'q!", show_alert=True)
        return
    for o in ol:
        b = InlineKeyboardBuilder()
        b.button(text="✅ Yuborildi", callback_data=f"ook_{o['_id']}")
        b.button(text="❌ Rad etish", callback_data=f"ono_{o['_id']}")
        b.adjust(2)
        await cb.message.answer(
            f"🛒 *Buyurtma #{short_id(o['_id'])}*\n👤 @{o['username']}\n"
            f"🪙 {o['robux_amount']} Robux — {o['price_sum']:,} so'm\n🕐 {o['created_at']}",
            reply_markup=b.as_markup()
        )
    await cb.answer()

@dp.callback_query(F.data == "adm_tr")
async def adm_tr(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    items = await active_trades()
    if not items:
        await cb.answer("Tradelar yo'q!", show_alert=True)
        return
    for t in items[:10]:
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"etrade_{t['_id']}")
        b.button(text="🗑 O'chirish",  callback_data=f"dtrade_{t['_id']}")
        b.adjust(2)
        caption = f"🔄 *#{short_id(t['_id'])}* {t['name']}\n👤 @{t.get('username','-')}\n📝 {t['bio']}"
        if t.get("photo_id"):
            await cb.message.answer_photo(t["photo_id"], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_sl")
async def adm_sl(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    items = await active_sales()
    if not items:
        await cb.answer("Sotuvlar yo'q!", show_alert=True)
        return
    for s in items[:10]:
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Tahrirlash", callback_data=f"esale_{s['_id']}")
        b.button(text="🗑 O'chirish",  callback_data=f"dsale_{s['_id']}")
        b.adjust(2)
        caption = f"🛍 *#{short_id(s['_id'])}* {s['name']}\n👤 @{s.get('username','-')}\n💰 {s['price']:,} {s['currency']}"
        if s.get("photo_id"):
            await cb.message.answer_photo(s["photo_id"], caption=caption, reply_markup=b.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "adm_addbal")
async def adm_addbal(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.message.answer("➕ Format: `<user_id> <summa>`\nMasalan: `123456789 50000`", reply_markup=cancel_kb())
    await state.set_state(AdminCmd.add_balance)
    await cb.answer()

@dp.message(AdminCmd.add_balance)
async def admin_addbalance(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await msg.answer("❌ Format: `<user_id> <summa>`")
        return
    uid, amt = int(parts[0]), int(parts[1])
    await users.update_one({"user_id": uid}, {"$inc": {"balance": amt}})
    try:
        await bot.send_message(uid, f"💰 Hisobingizga *{amt:,} so'm* qo'shildi!", reply_markup=main_kb())
    except Exception:
        pass
    await state.clear()
    await msg.answer(f"✅ {uid} ga {amt:,} so'm qo'shildi.", reply_markup=main_kb())

@dp.message(Command("addbalance"))
async def cmd_addbalance(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("❌ Ruxsat yo'q!")
        return
    parts = msg.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.answer("❌ Format: /addbalance <user_id> <summa>")
        return
    uid, amt = int(parts[1]), int(parts[2])
    await users.update_one({"user_id": uid}, {"$inc": {"balance": amt}})
    try:
        await bot.send_message(uid, f"💰 Hisobingizga *{amt:,} so'm* qo'shildi!", reply_markup=main_kb())
    except Exception:
        pass
    await msg.answer(f"✅ {uid} ga {amt:,} so'm qo'shildi.")

@dp.callback_query(F.data == "adm_bc")
async def adm_bc(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.message.answer("📸 Rasm yuboring yoki o'tkazib yuboring:", reply_markup=skip_cancel_kb())
    await state.set_state(Broadcast.photo)
    await cb.answer()

@dp.message(Broadcast.photo, F.photo)
async def bc_photo(msg: types.Message, state: FSMContext):
    await state.update_data(bc_photo=msg.photo[-1].file_id)
    await msg.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.photo)
async def bc_no_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    await state.update_data(bc_photo=None)
    await msg.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def bc_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
        return
    d     = await state.get_data()
    text  = msg.text.strip()
    photo = d.get("bc_photo")
    await state.clear()
    uids = await all_user_ids()
    sent = 0
    for uid in uids:
        try:
            if photo:
                await bot.send_photo(uid, photo, caption=text)
            else:
                await bot.send_message(uid, text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await msg.answer(f"✅ Xabar *{sent}/{len(uids)}* ta foydalanuvchiga yuborildi!", reply_markup=main_kb())

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
async def main():
    await init_indexes()
    logging.info("✅ Bot ishga tushdi!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
