# transaction_report.py
import io
import datetime
import pytz
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from bot_core.db import get_pool
from config import ADMIN_USER_ID
import stripe  # sync_stripe_command에서 사용
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

    # DataFrame 생성
    try:
        df = pd.DataFrame(rows)
        logger.info(f"DataFrame columns: {df.columns.tolist()}")
    except Exception as e:
        logger.error(f"DataFrame creation failed: {e}")
        await update.message.reply_text("Error loading data. Check logs.")
        return

    # timestamp 컬럼 안전하게 찾기 (alias 실패 대비)
    time_col = None
    for col in df.columns:
        if 'timestamp' in col.lower() or 'time' in col.lower():
            time_col = col
            break

    if not time_col:
        logger.error("No timestamp column found in query result")
        await update.message.reply_text("Internal error: timestamp column missing.")
        return

    # Edmonton 시간 변환 (tz-aware 처리)
    edmonton_tz = pytz.timezone('America/Edmonton')
    df[time_col] = df[time_col].apply(lambda x: x.replace(tzinfo=pytz.utc) if x and x.tzinfo is None else x)
    df['payment_time_edmonton'] = df[time_col].apply(
        lambda x: x.astimezone(edmonton_tz).strftime('%Y-%m-%d %H:%M:%S') if x else 'N/A'
    )

    # 컬럼 재배치 및 email 처리
    df['email'] = df['email'].apply(lambda x: x if x and x != 'unknown' else '')
    df = df[['payment_time_edmonton', 'amount', 'success', 'payment_type', 'email', 'telegram_user_id', 'telegram_username']]

    # 엑셀 생성
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transactions')

    output.seek(0)

    # 파일 전송
    await context.bot.send_document(
        chat_id=user_id,
        document=output,
        filename='transactions.xlsx',
        caption="Transaction report (Edmonton time, sorted by date DESC)"
    )
