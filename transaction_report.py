# transaction_report.py (전체 파일 교체 추천)
import io
import datetime
import pytz
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from bot_core.db import get_pool, log_action
from config import ADMIN_USER_ID, STRIPE_SECRET_KEY
import stripe
import logging

logger = logging.getLogger(__name__)

async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("Admin only command.")
        return

    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT 
            dl.timestamp,
            dl.amount,
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

    # DataFrame 생성 + 컬럼 수동 지정
    columns = ['timestamp', 'amount', 'success', 'payment_type', 'email', 'telegram_user_id', 'telegram_username']
    df = pd.DataFrame(rows, columns=columns)

    logger.info(f"Columns in DataFrame: {df.columns.tolist()}")

    # timestamp 컬럼 고정
    time_col = 'timestamp'
    if time_col not in df.columns:
        logger.error("Timestamp column not found.")
        await update.message.reply_text("내부 오류: 날짜 컬럼 없음.")
        return

    # 시간대 변환
    edmonton_tz = pytz.timezone('America/Edmonton')
    df[time_col] = df[time_col].apply(
        lambda x: x.replace(tzinfo=pytz.utc) if x and getattr(x, 'tzinfo', None) is None else x
    )
    df['payment_time_edmonton'] = df[time_col].apply(
        lambda x: x.astimezone(edmonton_tz).strftime('%Y-%m-%d %H:%M:%S') if x else 'N/A'
    )

    df['email'] = df['email'].apply(lambda x: x if x and x != 'unknown' else '')

    final_columns = ['payment_time_edmonton', 'amount', 'success', 'payment_type', 'email', 'telegram_user_id', 'telegram_username']
    available_columns = [col for col in final_columns if col in df.columns]
    df = df[available_columns]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transactions')

    output.seek(0)

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
            user_id_str = pi.metadata.get('user_id')
            if not user_id_str:
                continue
            user_id = int(user_id_str)
            bot_name = pi.metadata.get('bot_name', 'unknown')
            plan = pi.metadata.get('plan', 'monthly')
            amount = pi.amount / 100.0

            if bot_name != 'unknown':
                await log_action(pool, user_id, f'payment_stripe_{plan}', amount, bot_name)
                synced_count += 1

        await update.message.reply_text(f"Stripe에서 {synced_count}건의 결제 내역을 DB에 동기화했습니다.")
    except Exception as e:
        logger.error(f"Stripe sync error: {e}")
        await update.message.reply_text(f"동기화 실패: {str(e)}")
