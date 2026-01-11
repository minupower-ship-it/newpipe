# bot_core/db.py
import asyncpg
import datetime
from config import DATABASE_URL

async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)async def init_db(pool):
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
        ''')    # 추가: daily_logs에 bot_name 컬럼 없으면 추가 (기존)
    await conn.execute('''
        ALTER TABLE daily_logs
        ADD COLUMN IF NOT EXISTS bot_name TEXT;
    ''')

    # 추가: members에 bot_name 컬럼 없으면 추가 (새로, DEFAULT로 NOT NULL 대응)
    await conn.execute('''
        ALTER TABLE members
        ADD COLUMN IF NOT EXISTS bot_name TEXT NOT NULL DEFAULT 'unknown';
    ''')async def add_member(pool, user_id, username, customer_id=None, subscription_id=None, is_lifetime=False, expiry=None, bot_name='unknown'):
    if expiry is None:
        expiry = None if is_lifetime else (datetime.datetime.utcnow() + datetime.timedelta(days=30))
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
        ''', user_id, username, customer_id, subscription_id, is_lifetime, expiry, bot_name)async def log_action(pool, user_id, action, amount=0, bot_name='unknown'):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO daily_logs (user_id, action, amount, bot_name)
            VALUES ($1, $2, $3, $4)
        ''', user_id, action, amount, bot_name)async def get_member_status(pool, user_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM members WHERE user_id = $1 AND active = TRUE', user_id)
    return dict(row) if row else Noneasync def get_near_expiry(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT user_id, username, (expiry::date - CURRENT_DATE) AS days_left
            FROM members
            WHERE active = TRUE AND NOT is_lifetime AND (expiry::date - CURRENT_DATE) IN (1, 3)
        ''')
    return [(r['user_id'], r['username'] or f"ID{r['user_id']}", r['days_left']) for r in rows]async def get_expired_today(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT user_id, username FROM members
            WHERE active = TRUE AND NOT is_lifetime AND expiry::date = CURRENT_DATE
        ''')
    return [(r['user_id'], r['username'] or f"ID{r['user_id']}") for r in rows]async def get_daily_stats(pool):
    today = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT 
                COUNT(DISTINCT user_id) AS unique_users,
                COALESCE(SUM(amount) FILTER (WHERE action LIKE 'payment_stripe%'), 0) AS total_revenue
            FROM daily_logs
            WHERE timestamp >= $1
        ''', today)
    return {'unique_users': row['unique_users'] or 0, 'total_revenue': float(row['total_revenue'] or 0)}

