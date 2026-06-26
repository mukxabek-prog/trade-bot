"""
Botning butun "xotirasi" shu yerda: foydalanuvchilar, ularning coin balansi,
inventari, market e'lonlari va trade so'rovlari.

PostgreSQL + asyncpg ishlatiladi (SQLite emas!), chunki Render'ning bepul
tarifidagi web-servislar fayl tizimi vaqtinchalik — servis uxlab qolsa yoki
qayta deploy bo'lsa, lokal fayllar (SQLite .db) o'chib ketadi. Postgres
alohida xizmat bo'lgani uchun ma'lumotlar saqlanib qoladi.
"""

import datetime
from typing import Optional

import asyncpg

import config

_pool: Optional[asyncpg.pool.Pool] = None


def get_pool() -> asyncpg.pool.Pool:
    if _pool is None:
        raise RuntimeError("Ma'lumotlar bazasi hali ishga tushmagan (init_db chaqirilmagan).")
    return _pool


async def init_db():
    global _pool
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL topilmadi! Render'da bepul Postgres yarating (yoki "
            "Neon/Supabase'dan oling) va DATABASE_URL muhit o'zgaruvchisiga "
            "ulang. README.md dagi 'Render'ga deploy qilish' bo'limini ko'ring."
        )

    _pool = await asyncpg.create_pool(dsn=config.DATABASE_URL, min_size=1, max_size=5)

    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance BIGINT NOT NULL DEFAULT 0,
                last_daily TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                inv_id SERIAL PRIMARY KEY,
                owner_id BIGINT NOT NULL,
                item_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                value BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available',
                market_price BIGINT
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                trade_id SERIAL PRIMARY KEY,
                seller_id BIGINT NOT NULL,
                buyer_id BIGINT NOT NULL,
                inv_id INTEGER NOT NULL,
                price BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT now()
            )
            """
        )


async def close_db():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------- USERS ----

async def get_user(user_id: int) -> Optional[dict]:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    return dict(row) if row else None


async def get_user_by_username(username: str) -> Optional[dict]:
    username = username.lstrip("@").lower()
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM users WHERE LOWER(username) = $1", username
    )
    return dict(row) if row else None


async def create_user_if_not_exists(user_id: int, username: str, full_name: str):
    existing = await get_user(user_id)
    pool = get_pool()
    if existing:
        await pool.execute(
            "UPDATE users SET username = $1, full_name = $2 WHERE user_id = $3",
            username, full_name, user_id,
        )
        return existing, False

    await pool.execute(
        """
        INSERT INTO users (user_id, username, full_name, balance)
        VALUES ($1, $2, $3, $4)
        """,
        user_id, username, full_name, config.STARTING_BALANCE,
    )
    new_user = await get_user(user_id)
    return new_user, True


async def change_balance(user_id: int, delta: int):
    pool = get_pool()
    await pool.execute(
        "UPDATE users SET balance = balance + $1 WHERE user_id = $2", delta, user_id
    )


async def set_last_daily(user_id: int):
    pool = get_pool()
    await pool.execute(
        "UPDATE users SET last_daily = $1 WHERE user_id = $2",
        datetime.datetime.utcnow(), user_id,
    )


async def get_leaderboard(limit: int = 10):
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT u.user_id, u.username, u.full_name, u.balance,
               COALESCE(SUM(i.value), 0) AS inv_value
        FROM users u
        LEFT JOIN inventory i ON i.owner_id = u.user_id
        GROUP BY u.user_id, u.username, u.full_name, u.balance
        ORDER BY (u.balance + COALESCE(SUM(i.value), 0)) DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


# ------------------------------------------------------------ INVENTORY ----

async def add_inventory_item(owner_id: int, item_name: str, rarity: str, value: int) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO inventory (owner_id, item_name, rarity, value, status)
        VALUES ($1, $2, $3, $4, 'available')
        RETURNING inv_id
        """,
        owner_id, item_name, rarity, value,
    )
    return row["inv_id"]


async def get_inventory(owner_id: int, only_available: bool = False):
    pool = get_pool()
    query = "SELECT * FROM inventory WHERE owner_id = $1"
    if only_available:
        query += " AND status = 'available'"
    query += " ORDER BY value DESC"
    rows = await pool.fetch(query, owner_id)
    return [dict(r) for r in rows]


async def get_inventory_item(inv_id: int) -> Optional[dict]:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM inventory WHERE inv_id = $1", inv_id)
    return dict(row) if row else None


async def set_status(inv_id: int, status: str, price: Optional[int] = None):
    pool = get_pool()
    await pool.execute(
        "UPDATE inventory SET status = $1, market_price = $2 WHERE inv_id = $3",
        status, price, inv_id,
    )


async def transfer_item(inv_id: int, new_owner_id: int):
    pool = get_pool()
    await pool.execute(
        "UPDATE inventory SET owner_id = $1, status = 'available', market_price = NULL "
        "WHERE inv_id = $2",
        new_owner_id, inv_id,
    )


async def delete_inventory_item(inv_id: int):
    pool = get_pool()
    await pool.execute("DELETE FROM inventory WHERE inv_id = $1", inv_id)


# ---------------------------------------------------------------- MARKET ----

async def get_market_listings(exclude_owner: Optional[int] = None, limit: int = 50):
    pool = get_pool()
    if exclude_owner is not None:
        rows = await pool.fetch(
            """
            SELECT i.*, u.username, u.full_name FROM inventory i
            JOIN users u ON u.user_id = i.owner_id
            WHERE i.status = 'market' AND i.owner_id != $1
            ORDER BY i.market_price ASC
            LIMIT $2
            """,
            exclude_owner, limit,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT i.*, u.username, u.full_name FROM inventory i
            JOIN users u ON u.user_id = i.owner_id
            WHERE i.status = 'market'
            ORDER BY i.market_price ASC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def get_listings_by_owner(owner_id: int):
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT * FROM inventory WHERE owner_id = $1 AND status = 'market' "
        "ORDER BY market_price ASC",
        owner_id,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- TRADES ----

async def create_trade(seller_id: int, buyer_id: int, inv_id: int, price: int) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO trades (seller_id, buyer_id, inv_id, price, status)
        VALUES ($1, $2, $3, $4, 'pending')
        RETURNING trade_id
        """,
        seller_id, buyer_id, inv_id, price,
    )
    return row["trade_id"]


async def get_trade(trade_id: int) -> Optional[dict]:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM trades WHERE trade_id = $1", trade_id)
    return dict(row) if row else None


async def update_trade_status(trade_id: int, status: str):
    pool = get_pool()
    await pool.execute(
        "UPDATE trades SET status = $1 WHERE trade_id = $2", status, trade_id
    )
