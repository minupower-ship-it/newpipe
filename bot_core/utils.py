# bot_core/utils.py
import datetime
from config import CHANNEL_ID, ADMIN_USER_ID
from bot_core.db import get_near_expiry, get_expired_today, get_daily_stats

async def create_invite_link(bot):
    expire_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=int(expire_date.timestamp()),
        member_limit=1
    )
    return link.invite_link, expire_date.strftime('%b %d, %Y %H:%M UTC')

async def send_daily_report(context):
    today = datetime.datetime.utcnow().strftime("%b %d")
    stats = await get_daily_stats()
    near = await get_near_expiry()
    expired = await get_expired_today()

    message = f"📊 Daily Report - {today}\n\n"
    if near or expired:
        message += "🚨 Expiring Soon\n"
        for user_id, username, days in near:
            message += f"• @{username or user_id} - {days} days left\n"
        for user_id, username in expired:
            message += f"• @{username or user_id} - expires today\n"
        message += "\n"
    else:
        message += "✅ No expirations today\n\n"

    message += f"👥 Unique visitors: {stats['unique_users']}\n"
    message += f"💰 Revenue today: ${stats.get('total_revenue', 0):.2f}"

    await context.bot.send_message(ADMIN_USER_ID, message)
