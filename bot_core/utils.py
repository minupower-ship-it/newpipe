# bot_core/utils.py
import datetime
import logging
from telegram.ext import ContextTypes
from config import CHANNEL_ID, ADMIN_USER_ID
from bot_core.db import get_near_expiry, get_expired_today, get_daily_stats, get_pool

logger = logging.getLogger(__name__)

async def create_invite_link(bot):
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=0,  # 무제한
    )
    return link.invite_link, "영구 (구독 유지 중)"

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
            if username.startswith('user_'):
                display_name = f"User {user_id}"
                link = f"tg://user?id={user_id}"
                message += f"• <a href='{link}'>{display_name}</a> ({bot_name}) - {days} days left\n"
            else:
                message += f"• @{username} ({bot_name}) - {days} days left\n"

        for user_id, username, bot_name in expired:
            if username.startswith('user_'):
                display_name = f"User {user_id}"
                link = f"tg://user?id={user_id}"
                message += f"• <a href='{link}'>{display_name}</a> ({bot_name}) - expires today\n"
            else:
                message += f"• @{username} ({bot_name}) - expires today\n"
        message += "\n"
    else:
        message += "✅ No expirations today\n\n"

    message += f"👥 Unique visitors: {stats['unique_users']}\n"
    message += f"💰 Revenue today: ${stats['total_revenue']:.2f}"

    try:
        await context.bot.send_message(ADMIN_USER_ID, message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send daily report: {e}")

# 자동 kick Job 삭제 (notify_pre_kick도 삭제)
# 필요 시 /paid로만 예약된 kick 유지하려면 아래 함수 유지
async def notify_pre_kick(context: ContextTypes.DEFAULT_TYPE):
    # /paid로 예약된 사용자만 알림 (필요 시 유지, 아니면 삭제)
    pass  # 현재는 Stripe 자동 kick 없애서 필요 없음

async def auto_kick_scheduled(context: ContextTypes.DEFAULT_TYPE):
    # 완전 삭제 (Stripe 자동 kick 없앰)
    pass
