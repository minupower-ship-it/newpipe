# bot_core/utils.py
import datetime
import logging
from telegram.ext import ContextTypes
from config import CHANNEL_ID, ADMIN_USER_ID
from bot_core.db import get_near_expiry, get_expired_today, get_daily_stats, get_pool

logger = logging.getLogger(name)async def create_invite_link(bot):
    expire_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=int(expire_date.timestamp()),
        member_limit=1
    )
    return link.invite_link, expire_date.strftime('%b %d, %Y %H:%M UTC')async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    today = datetime.datetime.utcnow().strftime("%b %d")
    stats = await get_daily_stats(pool)
    near = await get_near_expiry(pool)
    expired = await get_expired_today(pool)message = f" Daily Report - {today}\n\n"
if near or expired:
    message += " Expiring Soon\n"
    for user_id, username, bot_name, days in near:
        message += f"• @{username} ({bot_name}) - {days} days left\n"
    for user_id, username, bot_name in expired:
        message += f"• @{username} ({bot_name}) - expires today\n"
    message += "\n"
else:
    message += " No expirations today\n\n"

message += f" Unique visitors: {stats['unique_users']}\n"
message += f" Revenue today: ${stats['total_revenue']:.2f}"

try:
    await context.bot.send_message(ADMIN_USER_ID, message)
except Exception as e:
    logger.error(f"Failed to send daily report: {e}")

