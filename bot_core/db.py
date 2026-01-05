import asyncpg
import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS daily_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            action TEXT,
            amount DECIMAL DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    await conn.close()

async def add_member(user_id, username, customer_id=None, subscription_id=None, is_lifetime=False, language='EN'):
    expiry = None if is_lifetime else (datetime.datetime.utcnow() + datetime.timedelta(days=30))
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        INSERT INTO members (user_id, username, stripe_customer_id, stripe_subscription_id, is_lifetime, expiry, active, language)
        VALUES ($1,$2,$3,$4,$5,$6,TRUE,$7)
        ON CONFLICT (user_id) DO UPDATE SET
            username=EXCLUDED.username,
            stripe_customer_id=COALESCE(EXCLUDED.stripe_customer_id, members.stripe_customer_id),
            stripe_subscription_id=COALESCE(EXCLUDED.stripe_subscription_id, members.stripe_subscription_id),
            is_lifetime=members.is_lifetime OR EXCLUDED.is_lifetime,
            expiry=EXCLUDED.expiry,
            active=TRUE,
            language=COALESCE(EXCLUDED.language, members.language)
    ''', user_id, username, customer_id, subscription_id, is_lifetime, expiry, language)
    await conn.close()

async def log_action(user_id, action, amount=0):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('INSERT INTO daily_logs (user_id, action, amount) VALUES ($1,$2,$3)', user_id, action, amount)
    await conn.close()

async def get_member_status(user_id):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow('SELECT username, stripe_customer_id, is_lifetime, expiry, created_at, language FROM members WHERE user_id=$1 AND active=TRUE', user_id)
    await conn.close()
    return row

