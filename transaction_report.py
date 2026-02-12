# transaction_report.py
import io
import datetime
import pytz
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from bot_core.db import get_pool
from config import ADMIN_USER_ID, STRIPE_SECRET_KEY
import stripe

async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("Admin only command.")
        return

    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT 
            dl.timestamp AS payment_time_utc,
            dl.amount AS amount,
            (CASE WHEN dl.action LIKE 'payment_stripe%' THEN 'Success' ELSE 'Unknown' END) AS success,
            (CASE 
                WHEN dl.action LIKE 'payment_stripe_renewal%' THEN 'Renewal' 
                ELSE 'New' 
            END) AS payment_type,
            m.email AS email,
            dl.user_id AS telegram_user_id,
            m.username AS telegram_username
        FROM daily_logs dl
        LEFT JOIN members m ON dl.user_id = m.user_id AND dl.bot_name = m.bot_name
        WHERE dl.action LIKE 'payment_stripe%'
        ORDER BY dl.timestamp DESC
    """)

    if not rows:
        await update.message.reply_text("No transaction data found.")
        return

    # DataFrame 생성
    df = pd.DataFrame(rows)

    # Edmonton 시간으로 변환 (America/Edmonton)
    edmonton_tz = pytz.timezone('America/Edmonton')
    df['payment_time_utc'] = df['payment_time_utc'].apply(lambda x: x.replace(tzinfo=pytz.utc) if x.tzinfo is None else x)
    df['payment_time_edmonton'] = df['payment_time_utc'].apply(lambda x: x.astimezone(edmonton_tz).strftime('%Y-%m-%d %H:%M:%S'))

    # 컬럼 재배치 및 email 'unknown' 처리 (unknown이면 빈 칸)
    df['email'] = df['email'].apply(lambda x: x if x and x != 'unknown' else '')
    df = df[['payment_time_edmonton', 'amount', 'success', 'payment_type', 'email', 'telegram_user_id', 'telegram_username']]

    # 엑셀 파일 메모리 생성
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transactions')

    output.seek(0)

    # Telegram으로 파일 전송
    await context.bot.send_document(
        chat_id=user_id,
        document=output,
        filename='transactions.xlsx',
        caption="Transaction report (Edmonton time, sorted by date DESC)"
    )

async def sync_stripe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("Admin only command.")
        return

    stripe.api_key = STRIPE_SECRET_KEY
    pool = await get_pool()
    synced_count = 0

    try:
        payments = stripe.PaymentIntent.list(limit=100, status="succeeded")
        for pi in payments.auto_paging_iter():
            user_id = int(pi.metadata.get('user_id', 0)) if pi.metadata.get('user_id') else None
            bot_name = pi.metadata.get('bot_name', 'unknown')
            plan = pi.metadata.get('plan', 'monthly')
            amount = pi.amount / 100.0

            if user_id and bot_name != 'unknown':
                await log_action(pool, user_id, f'payment_stripe_{plan}', amount, bot_name)
                synced_count += 1

        await update.message.reply_text(f"Synced {synced_count} payments from Stripe to DB.")
    except Exception as e:
        logger.error(f"Stripe sync error: {e}")
        await update.message.reply_text(f"Sync failed: {str(e)}")
