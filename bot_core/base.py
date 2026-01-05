import asyncio
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import stripe
from bot_core.db import add_member, log_action
import os

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PRICE_ID_MONTHLY = os.getenv("PRICE_ID_MONTHLY")
PRICE_ID_LIFETIME = os.getenv("PRICE_ID_LIFETIME")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

stripe.api_key = STRIPE_SECRET_KEY

async def create_invite_link(bot):
    expire_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=expire_date,
        member_limit=1
    )
    return link.invite_link, expire_date.strftime('%b %d, %Y %H:%M UTC')

