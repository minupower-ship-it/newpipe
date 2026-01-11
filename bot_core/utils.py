# bot_core/utils.py
import datetime
import logging
from telegram.ext import ContextTypes
from config import CHANNEL_ID, ADMIN_USER_ID
from bot_core.db import get_near_expiry, get_expired_today, get_daily_stats, get_pool

logger = logging.getLogger(__name__)

async def create_invite_link(bot):
    # 구독 플랜(Weekly/Monthly/Lifetime)은 모두 영구 초대 링크 (expire_date 없음, member_limit 무제한)
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=0,  # 0 = 무제한
        # expire_date=None → 만료 날짜 없음 (영구)
    )
    return link.invite_link, "영구 (구독 유지 중인 동안 유효)"

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    today = datetime.datetime.utcnow().strftime("%b %d")
    stats = await get_daily_stats(pool)
    near = await get_near_expiry(pool)
    expired = await get_expired_today(pool)

    message = f"📊 Daily Report - {today}\n\n"
    if near or expired:
        message += "🚨 Expiring Soon\n"
        for user_id, username, bot_name, days in near:
            message += f"• @{username} ({bot_name}) - {days} days left\n"
        for user_id, username, bot_name in expired:
            message += f"• @{username} ({bot_name}) - expires today\n"
        message += "\n"
    else:
        message += "✅ No expirations today\n\n"

    message += f"👥 Unique visitors: {stats['unique_users']}\n"
    message += f"💰 Revenue today: ${stats['total_revenue']:.2f}"

    try:
        await context.bot.send_message(ADMIN_USER_ID, message)
    except Exception as e:
        logger.error(f"Failed to send daily report: {e}")
