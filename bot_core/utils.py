from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_USER_ID, CHANNEL_ID
from bot_core.db import get_near_expiry, get_expired_today, get_daily_stats
import datetime

# -------------------
# 초대 링크 생성
# -------------------
async def create_invite_link(bot):
    """
    Telegram 채널 단일 사용 초대 링크 생성 (10분 만료)
    """
    expire_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=expire_date,
        member_limit=1
    )
    return link.invite_link, expire_date.strftime('%b %d, %Y %H:%M UTC')


# -------------------
# 일일 리포트 전송
# -------------------
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """
    매일 오전 9시 관리자에게 오늘 방문자 / 결제 / 만료 임박 회원 등 보고
    """
    today = datetime.datetime.utcnow().strftime("%b %d")
    stats = await get_daily_stats()
    near = await get_near_expiry()
    expired = await get_expired_today()

    message = f"📊 Daily Report - {today}\n\n"

    # 만료 임박 / 오늘 만료 회원
    if near or expired:
        message += "🚨 Expiring Soon\n"
        for _, u, d in near:
            message += f"• @{u} - {d} days left\n"
        for _, u in expired:
            message += f"• @{u} - expires today\n"
        message += "\n"
    else:
        message += "✅ No expirations today\n\n"

    # 통계
    message += f"👥 Unique visitors: {stats['unique_users']}\n"
    message += f"💰 Revenue today: ${stats['total_revenue']:.2f}"

    # 관리자에게 전송
    await context.bot.send_message(ADMIN_USER_ID, message)
