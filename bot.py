import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
import asyncpg

# LOGGING SOZLAMALARI
logging.basicConfig(level=logging.INFO)

# ENVIRONMENT VARIABLES (Render'dan olinadi)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("8325726426")
DATABASE_URL = os.getenv("DATABASE_URL")

# MAJBURIY KANAL SOZLAMASI (Kanal usernamesini shu yerga yozing)
# DIQQAT: Bot ushbu kanalda muloqot (admin) huquqiga ega bo'lishi shart!
REQUIRED_CHANNEL = "@kanal_username"  # O'zingizning kanal usernamesini yozing (masalan: @my_channel)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool = None

# DATABASE BILAN BOG'LANISH
async def init_db():
    global pool
    if DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    balance INT DEFAULT 0
                )
            ''')
            logging.info("Ma'lumotlar bazasi muvaffaqiyatli ulandi.")
    else:
        logging.error("DATABASE_URL topilmadi!")

# MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except TelegramBadRequest:
        # Agar kanal topilmasa yoki bot u yerda admin bo'lmasa, vaqtincha True qaytaradi
        logging.warning(f"Kanal topilmadi yoki bot admin emas: {REQUIRED_CHANNEL}")
        return True
    except Exception as e:
        logging.error(f"Obunani tekshirishda xatolik: {e}")
        return True

# INLINE KANALGA OBUNA BO'LISH TUGMASI
def subscription_keyboard():
    builder = InlineKeyboardBuilder()
    # Foydalanuvchi kanalga o'tishi uchun havola (link)
    channel_url = f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"
    builder.button(text="📢 Kanalga obuna bo'lish", url=channel_url)
    builder.button(text="✅ Obunani tekshirish", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()

# ASOSIY PASDAGI MENYU (REPLY KEYBOARD - 8 TA BO'LIM)
def main_reply_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🛒 Robux sotib olish")
    builder.button(text="👤 Profil")
    builder.button(text="💰 Hisob to'ldirish")
    builder.button(text="🔄 Tradelar")
    builder.button(text="📊 Sotuvlar")
    builder.button(text="➕ Trade qo'shish")
    builder.button(text="➕ Sotish qo'shish")
    builder.button(text="💬 Bizning chatimiz")
    builder.adjust(2, 2, 2, 2) # Tugmalarni qatorma-qator 2 tadan chiroyli joylashtiradi
    return builder.as_markup(resize_keyboard=True)

# /START BUYRUG'I
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    
    # Bazaga qo'shish
    if pool:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, username, balance)
                VALUES ($1, $2, 0)
                ON CONFLICT (user_id) DO NOTHING
            ''', user_id, username)

    # Obunani tekshirish
    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await message.answer(
            f"❌ Botdan foydalanishdan oldin homiy kanalimizga obuna bo'lishingiz majburiy!\n\n"
            f"Obuna bo'lib, keyin 'Tekshirish' tugmasini bosing.",
            reply_markup=subscription_keyboard()
        )
        return

    await message.answer(
        f"🌟 Assalomu alaykum!\n"
        f"👤 Biz sizni ko'rganimizdan juda ham xursandmiz, @{username}!\n\n"
        f"🤖 **Brainrot Trade Bot** sizga xizmat ko'rsatishga tayyor. Quyidagi menyudan foydalaning:",
        reply_markup=main_reply_keyboard()
    )

# INLINE OBUNANI TASDIQLASH TUGMASI BOSILGANDA
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "Foydalanuvchi"
    is_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        await callback.message.delete() # Obuna bo'ling degan xabarni o'chirish
        await callback.message.answer(
            f"🎉 Tabriklaymiz, obuna muvaffaqiyatli tasdiqlandi!\n\n"
            f"🌟 Assalomu alaykum! Biz sizni ko'rganimizdan juda ham xursandmiz, @{username}!\n"
            f"Quyidagi menyulardan foydalanishingiz mumkin:",
            reply_markup=main_reply_keyboard()
        )
    else:
        await callback.answer("❌ Siz hali ham kanalga obuna bo'lmagansiz!", show_alert=True)

# --- PASDAGI 8 TA MENYU TUGMALARI UCHUN HANDLERLAR ---

@dp.message(F.text == "🛒 Robux sotib olish")
async def robux_buy(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("🛒 **Robux sotib olish bo'limi:**\nBu yerda tez kunda arzon narxlarda robux sotib olish yo'lga qo'yiladi!")

@dp.message(F.text == "👤 Profil")
async def view_profile(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    user_id = message.from_user.id
    balance = 0
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT balance FROM users WHERE user_id = $1', user_id)
            if row: balance = row['balance']
            
    await message.answer(
        f"👤 **Sizning profilingiz:**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Username: @{message.from_user.username or 'yoq'}\n"
        f"💰 Balans: {balance} Robux"
    )

@dp.message(F.text == "💰 Hisob to'ldirish")
async def deposit_money(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("💰 **Hisobni to'ldirish:**\nTo'lov tizimlari orqali bot hisobingizni avtomat to'ldirish bo'limi.")

@dp.message(F.text == "🔄 Tradelar")
async def view_trades(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("🔄 **Mavjud Tradelar ro'yxati:**\nBu yerda barcha foydalanuvchilar qo'shgan faol tradelar ko'rinadi.")

@dp.message(F.text == "📊 Sotuvlar")
async def view_sales(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("📊 **Sotuvdagi narsalar:**\nSotuvga qo'yilgan barcha akkauntlar va narsalar ro'yxati.")

@dp.message(F.text == "➕ Trade qo'shish")
async def add_trade(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("➕ **Yangi Trade yaratish:**\nO'z tradingizni e'lon qiling.")

@dp.message(F.text == "➕ Sotish qo'shish")
async def add_sale(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("➕ **Sotuvga narsa qo'shish:**\nSotmoqchi bo'lgan narsangiz haqida ma'lumot kiriting.")

@dp.message(F.text == "💬 Bizning chatimiz")
async def community_chat(message: types.Message):
    if not await check_subscription(message.from_user.id): return
    await message.answer("💬 **Guruhimiz / Chatimiz:**\nFoydalanuvchilar bilan suhbatlashish uchun chat linki shu yerda bo'ladi.")

# ADMIN PANEL
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("🛠 Admin paneliga xush kelibsiz, xo'jayin!")
    else:
        await message.answer("❌ Bu buyruq faqat admin uchun.")

# BOTNI ISHGA TUSHIRISH
async def main():
    await init_db()
    logging.info("Bot pastki menyular bilan muvaffaqiyatli ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
