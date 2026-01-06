import asyncpg
import datetime
from config import DATABASE_URL

pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool

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
                bot_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # daily_logs 테이블 동일
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
            INSERT INTO members (...) VALUES (...)
            ON CONFLICT (user_id) DO UPDATE SET ...
            bot_name = EXCLUDED.bot_name  -- 추가
        ''', ..., bot_name)

async def log_action(user_id, action, amount=0, bot_name='unknown'):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('INSERT INTO daily_logs (user_id, action, amount, bot_name) VALUES ($1,$2,$3,$4)',
                           user_id, action, amount, bot_name)
