import asyncio
import html
import logging
import os
import sqlite3
import time
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.getenv("CHANNEL", "@BLOXFRUIT_UZBEKISTAN_SHOP")        # majburiy obuna
POST_CHANNEL = os.getenv("POST_CHANNEL", "@roblox_accunt_savdo")    # e'lonlar kanali
GARANT = os.getenv("GARANT", "@kazen_rbx")
CHANNEL_URL = f"https://t.me/{CHANNEL.lstrip('@')}"
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Limitdan ozod adminlar (Telegram ID, vergul bilan): ADMIN_IDS=123,456
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

COOLDOWN_DAYS = 7
MAX_ACTIVE = 3
MAX_PHOTOS = 5

GAMES = [
    ("🧠", "Steal a Brainrot"),
    ("🍎", "Blox Fruit"),
    ("🌊", "Escape Tsunami"),
    ("🥚", "Steal an Egg"),
]

POST_BTN = "📝 Akkaunt e'lon berish"
MY_BTN = "🗂 E'lonlarim"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ---------- Baza (SQLite) ----------
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute(
    """CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        msg_ids TEXT NOT NULL,
        game TEXT,
        nick TEXT,
        created_at INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    )"""
)
db.commit()


def db_add_post(user_id: int, msg_ids: list[int], game: str, nick: str) -> None:
    db.execute(
        "INSERT INTO posts (user_id, msg_ids, game, nick, created_at) VALUES (?,?,?,?,?)",
        (user_id, ",".join(map(str, msg_ids)), game, nick, int(time.time())),
    )
    db.commit()


def db_active_posts(user_id: int):
    return db.execute(
        "SELECT id, msg_ids, game, nick, created_at FROM posts "
        "WHERE user_id=? AND active=1 ORDER BY id DESC",
        (user_id,),
    ).fetchall()


def db_last_post_time(user_id: int) -> int:
    row = db.execute("SELECT MAX(created_at) FROM posts WHERE user_id=?", (user_id,)).fetchone()
    return row[0] or 0


def db_get_post(post_id: int):
    return db.execute(
        "SELECT id, user_id, msg_ids, active FROM posts WHERE id=?", (post_id,)
    ).fetchone()


def db_deactivate(post_id: int) -> None:
    db.execute("UPDATE posts SET active=0 WHERE id=?", (post_id,))
    db.commit()


def check_limits(user_id: int) -> tuple[bool, str]:
    """E'lon berish mumkinmi? (True, '') yoki (False, sabab)"""
    if user_id in ADMIN_IDS:
        return True, ""

    last = db_last_post_time(user_id)
    wait = last + COOLDOWN_DAYS * 86400 - int(time.time())
    if wait > 0:
        d, h = wait // 86400, (wait % 86400) // 3600
        return False, (
            f"⏳ E'lonni har {COOLDOWN_DAYS} kunda faqat 1 marta berish mumkin.\n\n"
            f"Keyingi e'lon: <b>{d} kun {h} soatdan</b> keyin."
        )

    if len(db_active_posts(user_id)) >= MAX_ACTIVE:
        return False, (
            f"⚠️ Kanalda sizning {MAX_ACTIVE} ta faol e'loningiz bor (maksimal).\n\n"
            f"Yangi e'lon berish uchun «{MY_BTN}» orqali eskisini o'chiring."
        )
    return True, ""


# ---------- Holatlar ----------
class Post(StatesGroup):
    game = State()
    nick = State()
    trade_ask = State()
    trade_what = State()
    photos = State()
    info = State()
    confirm = State()


# ---------- Tugmalar (primary=ko'k,
