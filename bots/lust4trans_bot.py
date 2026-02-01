# bots/lust4trans_bot.py
from bot_core.base_bot import BaseBot
from config import (
    LUST4TRANS_TOKEN,
    LUST4TRANS_PRICE_WEEKLY,
    LUST4TRANS_PRICE_MONTHLY,
    LUST4TRANS_PRICE_LIFETIME,
    LUST4TRANS_PORTAL_RETURN_URL,
    PAYPAL_LUST4TRANS_WEEKLY,
    PAYPAL_LUST4TRANS_MONTHLY,
    PAYPAL_LUST4TRANS_LIFETIME,
    WELCOME_VIDEO_LUST4TRANS
)

class Lust4transBot(BaseBot):
    def __init__(self):
        super().__init__(
            bot_name='lust4trans',
            token=LUST4TRANS_TOKEN,
            price_weekly=LUST4TRANS_PRICE_WEEKLY,
            price_monthly=LUST4TRANS_PRICE_MONTHLY,
            price_lifetime=LUST4TRANS_PRICE_LIFETIME,
            welcome_video=WELCOME_VIDEO_LUST4TRANS,
            paypal_weekly=PAYPAL_LUST4TRANS_WEEKLY,
            paypal_monthly=PAYPAL_LUST4TRANS_MONTHLY,
            paypal_lifetime=PAYPAL_LUST4TRANS_LIFETIME,
            has_weekly=True,
            has_monthly=True,
            has_lifetime=True,
            portal_return_url=LUST4TRANS_PORTAL_RETURN_URL
        )
