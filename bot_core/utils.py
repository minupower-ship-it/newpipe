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
        # expire_date 없음 → 영구
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

async def notify_pre_kick(context: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)

    rows = await pool.fetch(
        'SELECT user_id, bot_name FROM members '
        'WHERE kick_scheduled_at BETWEEN $1 AND $2 AND active = TRUE',
        tomorrow_start, tomorrow_end
    )

    for row in rows:
        user_id = row['user_id']
        bot_name = row['bot_name']
        app_info = next((a for a in applications.values() if a["bot_instance"].bot_name == bot_name), None)
        if app_info:
            bot = app_info["app"].bot
            try:
                await bot.send_message(
                    user_id,
                    "⚠️ 您的订阅即将到期提醒\n\n"
                    "明天您的订阅将到期，系统将自动将您移出频道。\n"
                    "如需继续使用，请立即续费！\n"
                    "续费链接：/start 后选择 Plans"
                )
                logger.info(f"Pre-kick 알림 전송: {user_id} ({bot_name})")
            except Exception as e:
                logger.error(f"Pre-kick 알림 실패: {user_id} - {e}")

async def auto_kick_scheduled(context: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    now = datetime.datetime.utcnow()
    rows = await pool.fetch(
        'SELECT user_id, bot_name FROM members '
        'WHERE kick_scheduled_at <= $1 AND active = TRUE',
        now
    )

    for row in rows:
        user_id = row['user_id']
        bot_name = row['bot_name']
        app_info = next((a for a in applications.values() if a["bot_instance"].bot_name == bot_name), None)
        if app_info:
            bot = app_info["app"].bot
            try:
                await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                await pool.execute(
                    'UPDATE members SET active = FALSE, kick_scheduled_at = NULL WHERE user_id = $1 AND bot_name = $2',
                    user_id, bot_name
                )
                logger.info(f"자동 kick 완료: {user_id} ({bot_name})")
            except Exception as e:
                logger.error(f"Auto kick 실패: {user_id} - {e}")
