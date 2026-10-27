            bot.send_message(chat_id, "\n".join(lines))
        bot.send_message(chat_id, "Admin menyusi:", reply_markup=admin_back_menu())
    elif data == "admin_products":
        if not is_admin(user_id):
            bot.send_message(chat_id, "⛔ Ruxsat yo'q.")
            return
        lines = ["🛍 <b>Mahsulotlar</b>"]
        for pid, p in PRODUCTS.items():
            lines.append(f"{pid}. {escape(p['name'])} — {money(p['price'])}")
        lines.append("\nMahsulot qo'shish/narxini o'zgartirish uchun bot.py dagi PRODUCTS ro'yxatini tahrirlang.")
        bot.send_message(chat_id, "\n".join(lines), reply_markup=admin_back_menu())
    else:
        bot.send_message(chat_id, "Tushunarsiz tugma. /menu ni bosing.")


def admin_back_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Admin panel", callback_data="admin"))
    markup.add(types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="home"))
    return markup


@bot.message_handler(func=lambda message: message.from_user.id in checkout_waiting, content_types=["text"])
def receive_checkout(message):
    global next_order_id
    user_id = message.from_user.id
    if message.text.strip().lower() == "/menu":
        checkout_waiting.discard(user_id)
        send_home(message.chat.id, user_id)
        return

    cart = carts.get(user_id, {})
    if not cart:
        checkout_waiting.discard(user_id)
        bot.send_message(message.chat.id, "Savatingiz bo'sh. /menu orqali qayta boshlang.")
        return

    contact = message.text.strip()
    if len(contact) < 5:
        bot.reply_to(message, "Iltimos, ism va telefon raqamingizni to'liqroq yuboring.")
        return

    item_lines = []
    total = 0
    for product_id, quantity in cart.items():
        product = PRODUCTS.get(product_id)
        if product and quantity > 0:
            subtotal = product["price"] * quantity
            total += subtotal
            item_lines.append(f"{product['name']} × {quantity} ({money(subtotal)})")

    if total <= 0:
        bot.send_message(message.chat.id, "Savatdagi mahsulotlar topilmadi. /menu ni bosing.")
        checkout_waiting.discard(user_id)
        return

    order = {
        "id": next_order_id,
        "user_id": user_id,
        "customer": message.from_user.full_name or "Mijoz",
        "contact": contact,
        "items": "; ".join(item_lines),
        "total": total,
        "status": "Yangi",
    }
    orders.append(order)
    next_order_id += 1
    carts[user_id] = {}
    checkout_waiting.discard(user_id)

    bot.send_message(
        message.chat.id,
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"Buyurtma raqami: <b>#{order['id']}</b>\n"
        f"💳 Jami: <b>{money(total)}</b>\n\n"
        "Admin siz bilan bog'lanadi.",
        reply_markup=main_menu(user_id)
    )

    if ADMIN_ID and ADMIN_ID != 123456789:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🔔 <b>Yangi buyurtma #{order['id']}</b>\n\n"
                f"👤 {escape(order['customer'])}\n"
                f"🆔 <code>{user_id}</code>\n"
                f"📞 {escape(contact)}\n"
                f"🧾 {escape(order['items'])}\n"
                f"💳 <b>{money(total)}</b>"
            )
        except Exception:
            pass


@bot.message_handler(func=lambda message: True, content_types=["text"])
def fallback(message):
    bot.send_message(message.chat.id, "Menyuni ochish uchun /menu ni bosing.", reply_markup=main_menu(message.from_user.id))


if __name__ == "__main__":
    if BOT_TOKEN == "BOT_TOKENINGIZNI_SHU_YERGA_QOYING":
        print("XATO: bot.py ichidagi BOT_TOKEN qiymatiga BotFather tokenini kiriting.")
    else:
        print("Do'kon boti ishga tushdi. To'xtatish uchun Ctrl+C bosing.")
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
