import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncpg

# LOGGING SOZLAMALARI
logging.basicConfig(level=logging.INFO)

# ENVIRONMENT VARIABLES (Renderdan olinadi)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool = None

# DATABASE BILAN BOG'LANISH
async def init_db():
    global pool
    if DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            # Foydalanuvchilar jadvalini yaratish (agar yo'ql bo'lsa)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    balance INT DEFAULT 0
                )
            ''')
            logging.info("Ma'lumotlar bazasi muvaffaqiyatli ulandi va jadvallar tekshirildi.")
    else:
        logging.error("DATABASE_URL topilmadi! Muhit o'zgaruvchilarini tekshiring.")

# ASOSIY KLAVIATURA (KEYBOARDS)
def main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Profil / Balans", callback_data="my_profile")
    builder.button(text="🛒 Savdo qilish", callback_data="start_trade")
    builder.button(text="ℹ️ Yordam", callback_data="help_info")
    builder.adjust(1)
    return builder.as_markup()

# BOT BUYRUQLARI (HANDLERS)
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    
    # Foydalanuvchini bazaga qo'shish
    if pool:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, username, balance)
                VALUES ($1, $2, 0)
                ON CONFLICT (user_id) DO NOTHING
            ''', user_id, username)

    await message.answer(
        f"👋 Salom, {message.from_user.full_name}!\n"
        f"🤖 **Brainrot Trade Bot**ga xush kelibsiz. Bu yerda siz xavfsiz savdo qilishingiz mumkin.",
        reply_markup=main_keyboard()
    )

@dp.callback_query(F.data == "my_profile")
async def profile_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    balance = 0
    
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT balance FROM users WHERE user_id = $1', user_id)
            if row:
                balance = row['balance']
                
    await callback.message.edit_text(
        f"👤 **Sizning profilingiz:**\n"
        f"🆔 ID: `{user_id}`\n"
        f"💰 Balans: {balance} XP",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "start_trade")
async def trade_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🛒 Savdo bo'limi tez kunda ishga tushadi!",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "help_info")
async def help_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ **Yordam:**\nMuammo yuzaga kelsa, adminga murojaat qiling.",
        reply_markup=main_keyboard()
    )
    await callback.answer()

# ADMIN BUYRUQLARI
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("🛠 Admin paneliga xush kelibsiz, xo'jayin!")
    else:
        await message.answer("❌ Bu buyruq faqat adminlar uchun.")

# POLLING START
async def main():
    await init_db()
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
