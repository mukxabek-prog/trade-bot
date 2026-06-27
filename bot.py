import os
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ========================================================
# CONFIG
# ========================================================
BOT_TOKEN        = os.getenv("BOT_TOKEN")
ADMIN_ID         = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI        = os.getenv("MONGO_URI")
REQUIRED_CHANNEL = os.getenv("CHANNEL", "@bulldrop_n1")
CARD_NUMBER      = os.getenv("CARD_NUMBER", "9860 1234 5678 9012")
CARD_OWNER       = os.getenv("CARD_OWNER", "ADMIN NOMI")
CHAT_LINK        = os.getenv("CHAT_LINK", "https://t.me/roblox_uz")

# ========================================================
# MONGODB
# ========================================================
client = AsyncIOMotorClient(MONGO_URI)
mdb    = client["roblox_bot"]
users  = mdb["users"]
deposits = mdb["deposits"]
orders   = mdb["orders"]
trades   = mdb["trades"]
sales    = mdb["sales"]

async def init_indexes():
    await users.create_index("user_id", unique=True)
    await deposits.create_index("user_id")
    await orders.create_index("user_id")
    await trades.create_index([("user_id", 1), ("status", 1)])
    await sales.create_index([("user_id", 1), ("status", 1)])

# ========================================================
# BOT INITIALIZATION
# ========================================================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp  = Dispatcher(storage=MemoryStorage())

# ========================================================
# STATES
# ========================================================
class DepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()

class OrderStates(StatesGroup):
    waiting_for_link = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_balance = State()

class Broadcast(StatesGroup):
    photo = State()
    text = State()

# ========================================================
# KEYBOARDS (aiogram 3.x uchun to'g'rilangan variant)
# ========================================================
def main_menu_kb():
    kb = [
        [types.KeyboardButton(text="🛒 Sotib olish"), types.KeyboardButton(text="💰 Balans to'ldirish")],
        [types.KeyboardButton(text="👤 Profil"), types.KeyboardButton(text="📊 Statistika")],
        [types.KeyboardButton(text="📞 Qo'llab-quvvatlash"), types.KeyboardButton(text="💬 Guruhimiz")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu_kb():
    kb = [
        [types.KeyboardButton(text="📢 Xabar yuborish"), types.KeyboardButton(text="✍️ Balans o'zgartirish")],
        [types.KeyboardButton(text="🗂 Buyurtmalarni ko'rish"), types.KeyboardButton(text="🔙 Asosiy menyu")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_kb():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)

# ========================================================
# AUX FUNCTIONS
# ========================================================
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Kanal tekshirishda xatolik: {e}")
        return True

async def all_user_ids():
    cur = users.find({}, {"user_id": 1})
    res = []
    async for d in cur:
        res.append(d["user_id"])
    return res

# ========================================================
# HANDLERS
# ========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    await users.update_one(
        {"user_id": user_id},
        {"$set": {"username": username}, "$setOnInsert": {"balance": 0.0, "total_deposited": 0.0}},
        upsert=True
    )
    
    if not await check_subscription(user_id):
        kb = [[types.InlineKeyboardButton(text="Kanallarga a'zo bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")],
              [types.InlineKeyboardButton(text="Tekshirish", callback_data="check_sub")]]
        await message.answer("Botdan foydalanish uchun kanalimizga a'zo bo'ling!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        return

    await message.answer("Xush kelibsiz! MuhammadFlow tomonidan tayyorlangan Roblox savdo botiga xush kelibsiz.", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.answer("Rahmat! Botdan foydalanishingiz mumkin.", reply_markup=main_menu_kb())
        await callback.answer()
    else:
        await callback.answer("Siz hali a'zo bo'lmadingiz!", show_alert=True)

@dp.message(F.text == "👤 Profil")
async def menu_profile(message: types.Message):
    u = await users.find_one({"user_id": message.from_user.id})
    if not u: return
    text = f"👤 *Sizning profilingiz:*\n\n🆔 ID: `{u['user_id']}`\n💰 Balans: *{u['balance']} so'm*\n📈 Jami kiritilgan: *{u['total_deposited']} so'm*"
    await message.answer(text)

@dp.message(F.text == "💰 Balans to'ldirish")
async def menu_deposit(message: types.Message, state: FSMContext):
    await message.answer("Qancha to'ldirmoqchisiz (so'mda)? Faqat raqam kiriting:", reply_markup=cancel_kb())
    await state.set_state(DepositStates.waiting_for_amount)

@dp.message(DepositStates.waiting_for_amount)
async def deposit_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())
        return
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat musbat raqam kiriting:")
        return
    amount = float(message.text)
    await state.update_data(amount=amount)
    
    text = f"To'lov miqdori: *{amount} so'm*\n\n💳 Karta: `{CARD_NUMBER}`\n👤 Ega: *{CARD_OWNER}*\n\nTo'lovni amalga oshirib, chekni (rasm shaklida) shu yerga yuboring."
    await message.answer(text, reply_markup=cancel_kb())
    await state.set_state(DepositStates.waiting_for_receipt)

@dp.message(DepositStates.waiting_for_receipt)
async def deposit_receipt(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())
        return
        
    if not message.photo:
        await message.answer("Iltimos, chek rasmini yuboring yoki bekor qiling:")
        return

    data = await state.get_data()
    amount = data['amount']
    photo_id = message.photo[-1].file_id
    
    dep_id = await deposits.insert_one({
        "user_id": message.from_user.id,
        "username": message.from_user.username or "NoUsername",
        "amount": amount,
        "photo_id": photo_id,
        "status": "pending"
    })
    
    await message.answer("Chek qabul qilindi. Admin tekshiruvidan so'ng balansizga o'tkaziladi. ⏳", reply_markup=main_menu_kb())
    
    kb = [
        [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"ap_{dep_id.inserted_id}")],
        [types.InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rj_{dep_id.inserted_id}")]
    ]
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=f"🔔 *Yangi to'lov cheki!*\n\nFoydalanuvchi: `{message.from_user.id}` (@{message.from_user.username})\nSumma: *{amount} so'm*",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.clear()

@dp.callback_query(F.data.startswith("ap_"))
async def admin_approve(callback: types.CallbackQuery):
    dep_id = ObjectId(callback.data.split("_")[1])
    dep = await deposits.find_one({"_id": dep_id, "status": "pending"})
    if not dep:
        await callback.answer("Bu chek allaqachon ko'rib chiqilgan.")
        return
        
    await deposits.update_one({"_id": dep_id}, {"$set": {"status": "approved"}})
    await users.update_one({"user_id": dep['user_id']}, {"$inc": {"balance": dep['amount'], "total_deposited": dep['amount']}})
    
    try:
        await bot.send_message(chat_id=dep['user_id'], text=f"✅ To'lovingiz tasdiqlandi! Balansingizga *{dep['amount']} so'm* qo'shildi.")
    except: pass
    
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 *Tasdiqlandi!*")
    await callback.answer()

@dp.callback_query(F.data.startswith("rj_"))
async def admin_reject(callback: types.CallbackQuery):
    dep_id = ObjectId(callback.data.split("_")[1])
    dep = await deposits.find_one({"_id": dep_id, "status": "pending"})
    if not dep:
        await callback.answer("Bu chek allaqachon ko'rib chiqilgan.")
        return
        
    await deposits.update_one({"_id": dep_id}, {"$set": {"status": "rejected"}})
    try:
        await bot.send_message(chat_id=dep['user_id'], text="❌ To'lovingiz rad etildi. Chek noto'g'ri yoki xato yuborilgan.")
    except: pass
    
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🔴 *Rad etildi!*")
    await callback.answer()

@dp.message(F.text == "📊 Statistika")
async def menu_stats(message: types.Message):
    total = await users.count_documents({})
    await message.answer(f"📊 *Bot statistikasi:*\n\nJami foydalanuvchilar: *{total}* ta")

@dp.message(F.text == "📞 Qo'llab-quvvatlash")
async def menu_support(message: types.Message):
    await message.answer(f"Murojaat va savollar uchun adminga yozishingiz mumkin.")

@dp.message(F.text == "💬 Guruhimiz")
async def menu_chat(message: types.Message):
    await message.answer(f"Bizning Roblox hamjamiyat guruhimiz: [Guruhga o'tish]({CHAT_LINK})", disable_web_page_preview=True)

# ========================================================
# ADMIN PANEL
# ========================================================
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Admin panelga xush kelibsiz!", reply_markup=admin_menu_kb())

@dp.message(F.text == "🔙 Asosiy menyu")
async def admin_back(message: types.Message):
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_kb())

@dp.message(F.text == "📢 Xabar yuborish")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("📸 Reklama rasmini yuboring (agar rasm bo'lmasa, har qanday matn yuboring):", reply_markup=cancel_kb())
    await state.set_state(Broadcast.photo)

@dp.message(Broadcast.photo)
async def bc_photo(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": 
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return
    if msg.photo:
        await state.update_data(bc_photo=msg.photo[-1].file_id)
    else:
        await state.update_data(bc_photo=None)
    await msg.answer("📝 Xabar matnini yozing:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def bc_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": 
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return
    d = await state.get_data()
    text = msg.text.strip()
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
        except: pass
        await asyncio.sleep(0.05)
    await msg.answer(f"✅ Xabar *{sent}/{len(uids)}* ta foydalanuvchiga yuborildi!", reply_markup=admin_menu_kb())

# ========================================================
# STARTUP ENTRY
# ========================================================
async def main():
    await init_indexes()
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
