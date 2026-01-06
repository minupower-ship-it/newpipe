# bot_core/db.py
import asyncpg
import datetime
from config import DATABASE_URL

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS members (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                is_lifetime BOOLEAN DEFAULT FALSE,
                expiry TIMESTAMP,
                active BOOLEAN DEFAULT TRUE,
                language TEXT DEFAULT 'EN',
                bot_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS daily_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                action TEXT,
                amount DECIMAL DEFAULT 0,
                bot_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

async def add_member(user_id, username, customer_id=None, subscription_id=None, is_lifetime=False, bot_name='unknown'):
    expiry = None if is_lifetime else (datetime.datetime.utcnow() + datetime.timedelta(days=30))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO members (
                user_id, username, stripe_customer_id, stripe_subscription_id,
                is_lifetime, expiry, active, language, bot_name
            ) VALUES ($1, $2, $3, $4, $5, $6, TRUE, 'EN', $7)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                stripe_customer_id = COALESCE(EXCLUDED.stripe_customer_id, members.stripe_customer_id),
                stripe_subscription_id = COALESCE(EXCLUDED.stripe_subscription_id, members.stripe_subscription_id),
                is_lifetime = members.is_lifetime OR EXCLUDED.is_lifetime,
                expiry = EXCLUDED.expiry,
                active = TRUE,
                bot_name = EXCLUDED.bot_name
        ''', user_id, username, customer_id, subscription_id, is_lifetime, expiry, bot_name)

async def log_action(user_id, action, amount=0, bot_name='unknown'):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO daily_logs (user_id, action, amount, bot_name)
            VALUES ($1, $2, $3, $4)
        ''', user_id, action, amount, bot_name)

async def get_member_status(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT * FROM members WHERE user_id = $1 AND active = TRUE
        ''', user_id)
    return dict(row) if row else None
