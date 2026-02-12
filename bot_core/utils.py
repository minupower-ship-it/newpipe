# bot_core/utils.py
import datetime
import logging
from telegram.ext import ContextTypes
from config import CHANNEL_ID, ADMIN_USER_ID
from bot_core.db import get_pool, get_near_expiry, get_expired_today, get_daily_stats

logger = logging.getLogger(__name__)

async def create_invite_link(bot):
    expire_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    expire_timestamp = int(expire_date.timestamp())

    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=expire_timestamp,
        member_limit=1
    )
    expiry_str = expire_date.strftime('%Y-%m-%d %H:%M UTC') + " (5 minutes)"
    return link.invite_link, expiry_str

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    today = datetime.datetime.utcnow().strftime("%b %d")
    stats = await get_daily_stats(pool)
    near = await get_near_expiry(pool)
    expired = await get_expired_today(pool)

    message = f"📊 Daily Report - {today}\n\n"
    if near or expired:
        message += "🚨 Expiring Soon\n"
        for user_id, username, bot_name, days, email in near:
            email_display = f" (Email: {email})" if email and email != 'unknown' else ''
            if username.startswith('user_'):
                display_name = f"User {user_id}"
                link = f"tg://user?id={user_id}"
                message += f"• <a href='{link}'>{display_name}</a> ({bot_name}){email_display} - {days} days left\n"
            else:
                message += f"• @{username} ({bot_name}){email_display} - {days} days left\n"

        for user_id, username, bot_name, email in expired:
            email_display = f" (Email: {email})" if email and email != 'unknown' else ''
            if username.startswith('user_'):
                display_name = f"User {user_id}"
                link = f"tg://user?id={user_id}"
                message += f"• <a href='{link}'>{display_name}</a> ({bot_name}){email_display} - expires today\n"
            else:
                message += f"• @{username} ({bot_name}){email_display} - expires today\n"
        message += "\n"
    else:
        message += "✅ No expirations today\n\n"

    message += f"👥 Unique visitors: {stats['unique_users']}\n"
    message += f"💰 Revenue today: ${stats['total_revenue']:.2f}"

    try:
        await context.bot.send_message(ADMIN_USER_ID, message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send daily report: {e}")
