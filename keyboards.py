"""
Steal a Brainrot Trade Bot
==========================
Roblox "Steal a Brainrot" o'yini mavzusidagi virtual trade/market bot.
Hech qanday real pul yoki Robux bilan ishlamaydi — hammasi botning ichki
"coin" valyutasida, shunchaki o'yin-kulgi va do'stlar bilan trade qilish uchun.

Buyruqlar:
    /start      - ro'yxatdan o'tish, boshlang'ich coin olish
    /help       - yordam
    /balance    - balansni ko'rish
    /shop       - do'kondan brainrot sotib olish (har safar random 6 ta item)
    /inventory  - sizdagi brainrotlar ro'yxati
    /sell       - o'zingizdagi itemni umumiy marketga qo'yish
    /market     - boshqalar qo'ygan itemlarni ko'rish va sotib olish
    /mylistings - sizning market e'lonlaringiz (bekor qilish mumkin)
    /trade      - boshqa foydalanuvchiga to'g'ridan-to'g'ri taklif yuborish
    /daily      - kunlik bonus coin
    /top        - eng boy o'yinchilar reytingi
"""

import asyncio
import datetime
import logging
import random

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery

import config
import db
import data
import keyboards as kb

logging.basicConfig(level=logging.INFO)
router = Router()


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def pick_shop_items(n: int) -> list[dict]:
    """Rarity og'irligiga qarab random n ta item tanlaydi (konveyer effekti)."""
    rarities = list(data.RARITY_SPAWN_WEIGHT.keys())
    weights = list(data.RARITY_SPAWN_WEIGHT.values())
    chosen = []
    for _ in range(n):
        rarity = random.choices(rarities, weights=weights, k=1)[0]
        pool = data.items_by_rarity(rarity)
        if pool:
            chosen.append(random.choice(pool))
    return chosen


# ---------------------------------------------------------------- /start ----

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    record, is_new = await db.create_user_if_not_exists(
        user.id, user.username or "", user.full_name or ""
    )
    if is_new:
        text = (
            f"👋 Salom, {user.full_name}!\n\n"
            f"🧠 <b>Steal a Brainrot Trade Bot</b>ga xush kelibsiz!\n"
            f"Bu yerda siz brainrotlarni sotib olishingiz, sotishingiz va "
            f"boshqa o'yinchilar bilan trade qilishingiz mumkin.\n\n"
            f"🎁 Sizga boshlang'ich sovg'a: <b>{fmt(config.STARTING_BALANCE)} coin</b>\n\n"
            f"Buyruqlar ro'yxati uchun /help yozing."
        )
    else:
        text = f"Qaytib kelganingizdan xursandmiz, {user.full_name}! /help orqali buyruqlarni ko'ring."
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "🧠 <b>Steal a Brainrot Trade Bot — buyruqlar</b>\n\n"
        "💰 /balance — balansingiz\n"
        "🎰 /shop — do'kondan brainrot sotib olish (har chaqirilganda yangi 6 ta tovar)\n"
        "🎒 /inventory — sizdagi brainrotlar\n"
        "🏷 /sell &lt;inv_id&gt; &lt;narx&gt; — itemni umumiy marketga qo'yish\n"
        "🛒 /market — boshqalar sotuvga qo'ygan itemlar\n"
        "📋 /mylistings — sizning marketdagi e'lonlaringiz\n"
        "🤝 /trade &lt;@username&gt; &lt;inv_id&gt; &lt;narx&gt; — to'g'ridan-to'g'ri trade taklifi\n"
        "🎁 /daily — kunlik bonus coin\n"
        "🏆 /top — eng boy o'yinchilar\n\n"
        "<i>Eslatma: bu yerdagi coin va itemlar to'liq virtual, real pul/Robux "
        "bilan bog'liq emas — faqat shu bot ichida o'ynash uchun.</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start buyrug'ini bosing.")
        return
    await message.answer(f"💰 Balansingiz: <b>{fmt(user['balance'])} coin</b>", parse_mode="HTML")


# ----------------------------------------------------------------- /shop ----

@router.message(Command("shop"))
async def cmd_shop(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start buyrug'ini bosing.")
        return
    items = pick_shop_items(config.SHOP_SLOTS)
    text = (
        "🎰 <b>Bugungi do'kon (konveyer)</b>\n"
        "Quyidagilardan birini tanlang — har /shop chaqirilganda tovarlar yangilanadi:\n\n"
        f"💰 Balansingiz: {fmt(user['balance'])} coin"
    )
    await message.answer(text, reply_markup=kb.shop_keyboard(items), parse_mode="HTML")


@router.callback_query(F.data.startswith("buyshop:"))
async def cb_buy_shop(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    item = data.get_item(item_id)
    if not item:
        await callback.answer("Bu tovar topilmadi.", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Avval /start bosing.", show_alert=True)
        return

    if user["balance"] < item["price"]:
        await callback.answer(
            f"❌ Coin yetarli emas! Kerak: {fmt(item['price'])}, sizda: {fmt(user['balance'])}",
            show_alert=True,
        )
        return

    await db.change_balance(user["user_id"], -item["price"])
    await db.add_inventory_item(user["user_id"], item["name"], item["rarity"], item["price"])

    emoji = data.RARITY_EMOJI.get(item["rarity"], "")
    await callback.answer(f"✅ Sotib olindi: {item['name']}!", show_alert=True)
    await callback.message.answer(
        f"🎉 Siz <b>{emoji} {item['name']}</b> ({item['rarity']})ni "
        f"<b>{fmt(item['price'])} coin</b>ga sotib oldingiz!\n"
        f"/inventory orqali ko'rishingiz mumkin.",
        parse_mode="HTML",
    )


# ------------------------------------------------------------- /inventory ----

@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    items = await db.get_inventory(message.from_user.id)
    if not items:
        await message.answer("🎒 Inventaringiz bo'sh. /shop orqali brainrot sotib oling!")
        return

    lines = ["🎒 <b>Sizning brainrotlaringiz:</b>\n"]
    for it in items:
        emoji = data.RARITY_EMOJI.get(it["rarity"], "•")
        status_label = ""
        if it["status"] == "market":
            status_label = f" — 🏷 marketda ({fmt(it['market_price'])} coin)"
        elif it["status"] == "trade_pending":
            status_label = " — 🤝 trade kutilmoqda"
        lines.append(
            f"#{it['inv_id']} {emoji} {it['item_name']} ({it['rarity']}, {fmt(it['value'])} coin){status_label}"
        )
    lines.append(
        "\nSotish uchun: <code>/sell ID narx</code>\n"
        "Trade qilish uchun: <code>/trade @username ID narx</code>"
    )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ------------------------------------------------------------------ /sell ----

@router.message(Command("sell"))
async def cmd_sell(message: Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Foydalanish: <code>/sell inv_id narx</code>\n"
            "Misol: <code>/sell 5 800</code>\n"
            "ID ni /inventory orqali topasiz.",
            parse_mode="HTML",
        )
        return

    try:
        inv_id = int(parts[1])
        price = int(parts[2])
    except ValueError:
        await message.answer("ID va narx butun son bo'lishi kerak.")
        return

    if price <= 0:
        await message.answer("Narx 0 dan katta bo'lishi kerak.")
        return

    item = await db.get_inventory_item(inv_id)
    if not item or item["owner_id"] != message.from_user.id:
        await message.answer("Bu ID sizga tegishli emas yoki topilmadi.")
        return

    if item["status"] != "available":
        await message.answer("Bu item allaqachon marketda yoki trade jarayonida.")
        return

    await db.set_status(inv_id, "market", price)
    emoji = data.RARITY_EMOJI.get(item["rarity"], "")
    await message.answer(
        f"✅ {emoji} <b>{item['item_name']}</b> <b>{fmt(price)} coin</b>ga marketga qo'yildi!\n"
        f"Bekor qilish uchun /mylistings dan foydalaning.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------- /market ----

@router.message(Command("market"))
async def cmd_market(message: Message):
    listings = await db.get_market_listings(
        exclude_owner=message.from_user.id, limit=config.MARKET_PAGE_SIZE
    )
    if not listings:
        await message.answer("🛒 Hozircha marketda hech narsa yo'q. Birinchi bo'lib /sell qiling!")
        return

    text = "🛒 <b>Marketdagi brainrotlar</b> (sotib olish uchun tugmani bosing):"
    await message.answer(
        text, reply_markup=kb.market_keyboard(listings, message.from_user.id), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buymarket:"))
async def cb_buy_market(callback: CallbackQuery):
    inv_id = int(callback.data.split(":")[1])
    item = await db.get_inventory_item(inv_id)

    if not item or item["status"] != "market":
        await callback.answer("Bu e'lon endi mavjud emas.", show_alert=True)
        return

    if item["owner_id"] == callback.from_user.id:
        await callback.answer("O'zingizning itemingizni sotib ololmaysiz 🙂", show_alert=True)
        return

    buyer = await db.get_user(callback.from_user.id)
    if not buyer or buyer["balance"] < item["market_price"]:
        await callback.answer("Coin yetarli emas.", show_alert=True)
        return

    seller_id = item["owner_id"]
    price = item["market_price"]

    await db.change_balance(buyer["user_id"], -price)
    await db.change_balance(seller_id, price)
    await db.transfer_item(inv_id, buyer["user_id"])

    emoji = data.RARITY_EMOJI.get(item["rarity"], "")
    await callback.answer("✅ Xarid muvaffaqiyatli!", show_alert=True)
    await callback.message.answer(
        f"🤝 <b>{buyer['full_name'] or buyer['username']}</b> sotib oldi: "
        f"{emoji} {item['item_name']} — {fmt(price)} coin",
        parse_mode="HTML",
    )

    try:
        await callback.bot.send_message(
            seller_id,
            f"💸 Sizning <b>{emoji} {item['item_name']}</b> itemingiz "
            f"<b>{fmt(price)} coin</b>ga sotildi!",
            parse_mode="HTML",
        )
    except Exception:
        pass  # sotuvchi botni bloklagan bo'lishi mumkin


@router.message(Command("mylistings"))
async def cmd_mylistings(message: Message):
    listings = await db.get_listings_by_owner(message.from_user.id)
    if not listings:
        await message.answer("Sizning marketda e'loningiz yo'q.")
        return
    await message.answer(
        "📋 <b>Sizning e'lonlaringiz:</b>",
        reply_markup=kb.my_listings_keyboard(listings),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cancellisting:"))
async def cb_cancel_listing(callback: CallbackQuery):
    inv_id = int(callback.data.split(":")[1])
    item = await db.get_inventory_item(inv_id)
    if not item or item["owner_id"] != callback.from_user.id or item["status"] != "market":
        await callback.answer("Bu e'lon topilmadi.", show_alert=True)
        return
    await db.set_status(inv_id, "available")
    await callback.answer("E'lon bekor qilindi.", show_alert=True)
    await callback.message.answer(f"❌ {item['item_name']} e'loni bekor qilindi.")


# ----------------------------------------------------------------- /trade ----

@router.message(Command("trade"))
async def cmd_trade(message: Message):
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer(
            "Foydalanish: <code>/trade @username inv_id narx</code>\n"
            "Misol: <code>/trade @ali_b 7 500</code>\n\n"
            "⚠️ Eslatma: qarshi tomon avval botga /start bosgan bo'lishi kerak, "
            "aks holda Telegram unga xabar yuborishga ruxsat bermaydi.",
            parse_mode="HTML",
        )
        return

    target_username = parts[1]
    try:
        inv_id = int(parts[2])
        price = int(parts[3])
    except ValueError:
        await message.answer("inv_id va narx butun son bo'lishi kerak.")
        return

    if price <= 0:
        await message.answer("Narx 0 dan katta bo'lishi kerak.")
        return

    item = await db.get_inventory_item(inv_id)
    if not item or item["owner_id"] != message.from_user.id:
        await message.answer("Bu ID sizga tegishli emas yoki topilmadi.")
        return
    if item["status"] != "available":
        await message.answer("Bu item hozir marketda yoki boshqa trade jarayonida.")
        return

    target = await db.get_user_by_username(target_username)
    if not target:
        await message.answer(
            "Bu foydalanuvchi topilmadi. U avval botga /start bosgan bo'lishi kerak."
        )
        return
    if target["user_id"] == message.from_user.id:
        await message.answer("O'zingizga trade taklif qila olmaysiz 🙂")
        return

    await db.set_status(inv_id, "trade_pending", price)
    trade_id = await db.create_trade(message.from_user.id, target["user_id"], inv_id, price)

    emoji = data.RARITY_EMOJI.get(item["rarity"], "")
    sender = message.from_user

    try:
        await message.bot.send_message(
            target["user_id"],
            f"🤝 <b>{sender.full_name}</b> (@{sender.username or sender.id}) sizga trade "
            f"taklif qildi:\n\n{emoji} <b>{item['item_name']}</b> ({item['rarity']})\n"
            f"💰 Narx: <b>{fmt(price)} coin</b>\n\n"
            f"Qabul qilsangiz, balansingizdan {fmt(price)} coin yechiladi va item sizga o'tadi.",
            reply_markup=kb.trade_offer_keyboard(trade_id),
            parse_mode="HTML",
        )
        await message.answer("✅ Taklif yuborildi! Javobini kutib turing.")
    except Exception:
        await db.set_status(inv_id, "available")
        await db.update_trade_status(trade_id, "failed")
        await message.answer(
            "❌ Taklifni yuborib bo'lmadi — ehtimol bu foydalanuvchi botni bloklagan "
            "yoki hali botga /start bosmagan."
        )


@router.callback_query(F.data.startswith("tradeacc:"))
async def cb_trade_accept(callback: CallbackQuery):
    trade_id = int(callback.data.split(":")[1])
    trade = await db.get_trade(trade_id)

    if not trade or trade["status"] != "pending":
        await callback.answer("Bu taklif endi amal qilmaydi.", show_alert=True)
        return
    if trade["buyer_id"] != callback.from_user.id:
        await callback.answer("Bu taklif sizga tegishli emas.", show_alert=True)
        return

    buyer = await db.get_user(trade["buyer_id"])
    item = await db.get_inventory_item(trade["inv_id"])

    if not item or item["status"] != "trade_pending":
        await callback.answer("Bu item endi mavjud emas.", show_alert=True)
        return

    if buyer["balance"] < trade["price"]:
        await callback.answer("Coin yetarli emas!", show_alert=True)
        return

    await db.change_balance(buyer["user_id"], -trade["price"])
    await db.change_balance(trade["seller_id"], trade["price"])
    await db.transfer_item(trade["inv_id"], buyer["user_id"])
    await db.update_trade_status(trade_id, "accepted")

    emoji = data.RARITY_EMOJI.get(item["rarity"], "")
    await callback.answer("✅ Trade qabul qilindi!", show_alert=True)
    await callback.message.edit_text(
        f"✅ Trade qabul qilindi!\n{emoji} {item['item_name']} — {fmt(trade['price'])} coin",
        parse_mode="HTML",
    )

    try:
        await callback.bot.send_message(
            trade["seller_id"],
            f"🎉 Sizning trade taklifingiz qabul qilindi! "
            f"{emoji} <b>{item['item_name']}</b> uchun <b>{fmt(trade['price'])} coin</b> "
            f"hisobingizga tushdi.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("tradedec:"))
async def cb_trade_decline(callback: CallbackQuery):
    trade_id = int(callback.data.split(":")[1])
    trade = await db.get_trade(trade_id)

    if not trade or trade["status"] != "pending":
        await callback.answer("Bu taklif endi amal qilmaydi.", show_alert=True)
        return
    if trade["buyer_id"] != callback.from_user.id:
        await callback.answer("Bu taklif sizga tegishli emas.", show_alert=True)
        return

    await db.set_status(trade["inv_id"], "available")
    await db.update_trade_status(trade_id, "declined")

    await callback.answer("Taklif rad etildi.", show_alert=True)
    await callback.message.edit_text("❌ Trade taklifi rad etildi.")

    try:
        await callback.bot.send_message(
            trade["seller_id"], "❌ Sizning trade taklifingiz rad etildi."
        )
    except Exception:
        pass


# ----------------------------------------------------------------- /daily ----

@router.message(Command("daily"))
async def cmd_daily(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start bosing.")
        return

    if user["last_daily"]:
        last = user["last_daily"]  # asyncpg buni datetime obyekti qilib qaytaradi
        delta = datetime.datetime.utcnow() - last
        hours_left = config.DAILY_COOLDOWN_HOURS - delta.total_seconds() / 3600
        if hours_left > 0:
            h = int(hours_left)
            m = int((hours_left - h) * 60)
            await message.answer(f"⏳ Keyingi bonusgacha: {h} soat {m} daqiqa.")
            return

    bonus = random.randint(config.DAILY_BONUS_MIN, config.DAILY_BONUS_MAX)
    await db.change_balance(user["user_id"], bonus)
    await db.set_last_daily(user["user_id"])
    await message.answer(f"🎁 Kunlik bonus: <b>+{fmt(bonus)} coin</b>!", parse_mode="HTML")


# ------------------------------------------------------------------- /top ----

@router.message(Command("top"))
async def cmd_top(message: Message):
    leaderboard = await db.get_leaderboard(10)
    if not leaderboard:
        await message.answer("Hali hech kim yo'q.")
        return

    lines = ["🏆 <b>Eng boy o'yinchilar (coin + inventar qiymati):</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(leaderboard):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = u["username"] or u["full_name"] or str(u["user_id"])
        total = u["balance"] + u["inv_value"]
        lines.append(f"{medal} {name} — {fmt(total)} coin")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ------------------------------------------------------------------- MAIN ----

async def main():
    await db.init_db()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
