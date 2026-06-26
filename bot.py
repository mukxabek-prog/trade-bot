import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# LOGGING SOZLAMALARI
logging.basicConfig(level=logging.INFO)

# ENVIRONMENT VARIABLES
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# MAJBURIY KANAL USERNAME (Shu yerga kanalingizni `@` bilan yozing)
# DIQQAT: Bot ushbu kanalda ADMIN bo'lishi shart, aks holda odamlarni tekshira olmaydi!
REQUIRED_CHANNEL = "@roblox_uz" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI
async def is_user_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception as e:
        logging.error(f"Obunani tekshirishda xatolik: {e}")
        # Agar bot kanalda admin bo'lmasa yoki username noto'g'ri bo'lsa xato beradi
        return False

# INLINE OBUNA BO'LISH TUGMASI
def subscription_keyboard():
    builder = InlineKeyboardBuilder()
    channel_url = f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"
    builder.button(text="📢 Kanalga obuna bo'lish", url=channel_url)
    builder.button(text="✅ Obunani tasdiqlash", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()

# ASOSIY PASDAGI MENYU (REPLY KEYBOARD)
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
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

# /START BUYRUG'I
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    
    # Obunani tekshirish
    if not await is_user_subscribed(user_id):
        await message.answer(
            f"❌ Botdan foydalanish uchun homiy kanalimizga obuna bo'lishingiz shart!\n\n"
            f"Obuna bo'lib, keyin pastdagi **Tasdiqlash** tugmasini bosing.",
            reply_markup=subscription_keyboard()
        )
        return

    await message.answer(
        f"🌟 Assalomu alaykum!\n"
        f"👤 Biz sizni ko'rganimizdan juda ham xursandmiz, @{username}!\n\n"
        f"🤖 **Brainrot Trade Bot**ga xush kelibsiz. Quyidagi menyudan foydalaning:",
        reply_markup=main_reply_keyboard()
    )

# TASDIQLASH TUGMASI BOSILGANDA
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "Foydalanuvchi"
    
    if await is_user_subscribed(user_id):
        await callback.message.delete()
        await callback.message.answer(
            f"🎉 Obuna tasdiqlandi!\n\n"
            f"🌟 Assalomu alaykum! Biz sizni ko'rganimizdan juda ham xursandmiz, @{username}!\n"
            f"Bot ishga tushdi, menyulardan foydalanishingiz mumkin:",
            reply_markup=main_reply_keyboard()
        )
    else:
        await callback.answer("❌ Siz hali kanalga obuna bo'lmagansiz! Iltimos, oldin obuna bo'ling.", show_alert=True)

# ROBUX SOTIB OLISH BO'LIMI
@dp.message(F.text == "🛒 Robux sotib olish")
async def robux_buy(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Botdan foydalanish uchun avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
        
    prices_text = (
        "🔥 **ROBUX NARXLAR** 🔥\n\n"
        "🪙 40 ROBUX — 7 000 so'm\n"
        "🪙 80 ROBUX — 14 000 so'm\n"
        "🪙 120 ROBUX — 21 000 so'm\n"
        "🪙 160 ROBUX — 28 000 so'm\n"
        "🪙 200 ROBUX — 35 000 so'm\n"
        "🪙 240 ROBUX — 42 000 so'm\n"
        "🪙 280 ROBUX — 49 000 so'm\n"
        "🪙 320 ROBUX — 56 000 so'm\n"
        "🪙 360 ROBUX — 63 000 so'm\n\n"
        "🪙 400 ROBUX — 65 000 so'm\n"
        "🪙 440 ROBUX — 72 000 so'm\n"
        "🪙 480 ROBUX — 79 000 so'm\n"
        "🪙 520 ROBUX — 86 000 so'm\n"
        "🪙 560 ROBUX — 93 000 so'm\n"
        "🔥 700 ROBUX — 100 000 so'm 🔥\n"
        "🪙 740 ROBUX — 107 000 so'm\n"
        "🪙 780 ROBUX — 114 000 so'm\n"
        "🪙 820 ROBUX — 121 000 so'm\n"
        "🪙 860 ROBUX — 128 000 so'm\n\n"
        "🪙 1000 ROBUX — 132 000 so'm\n"
        "🪙 1500 ROBUX — 197 000 so'm\n"
        "🪙 2000 ROBUX — 265 000 so'm\n\n"
        "💳 Sotib olish uchun adminga murojaat qiling yoki hisobingizni to'ldiring!"
    )
    await message.answer(prices_text)

# BOSHQA BO'LIMLAR (OBUNA TEKSHIRUVI BILAN)
@dp.message(F.text == "👤 Profil")
async def view_profile(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer(f"👤 **Sizning profilingiz:**\n\n🆔 ID: `{message.from_user.id}`\n👤 Username: @{message.from_user.username or 'yoq'}\n💰 Balans: 0 Robux")

@dp.message(F.text == "💰 Hisob to'ldirish")
async def deposit_money(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer("💰 **Hisobni to'ldirish bo'limi** yaqin orada ishga tushadi.")

@dp.message(F.text == "🔄 Tradelar")
async def view_trades(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer("🔄 Faol tradelar ro'yxati bo'sh.")

@dp.message(F.text == "📊 Sotuvlar")
async def view_sales(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer("📊 Sotuvdagi buyumlar ro'yxati bo'sh.")

@dp.message(F.text == "➕ Trade qo'shish")
async def add_trade(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer("➕ Yangi trade e'lon qilish bo'limi.")

@dp.message(F.text == "➕ Sotish qo'shish")
async def add_sale(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer("➕ Sotuvga yangi narsa qo'shish bo'limi.")

@dp.message(F.text == "💬 Bizning chatimiz")
async def community_chat(message: types.Message):
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=subscription_keyboard())
        return
    await message.answer("💬 Bizning rasmiy chatimiz guruh linki tez kunda joylanadi.")

# ADMIN PANEL
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("🛠 Admin paneliga xush kelibsiz, xo'jayin!")
    else:
        await message.answer("❌ Bu buyruq faqat admin uchun.")

async def main():
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
