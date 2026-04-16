# bots/pleasurecult_bot.py
from bot_core.base_bot import BaseBot
from config import (
    PLEASURECULT_TOKEN,
    LUST4TRANS_PRICE_WEEKLY,
    LUST4TRANS_PRICE_MONTHLY,
    LUST4TRANS_PRICE_LIFETIME,
    PLEASURECULT_PORTAL_RETURN_URL,
    WELCOME_VIDEO_TSWRLD,
)

class PleasureCultBot(BaseBot):
    def __init__(self):
        super().__init__(
            bot_name='pleasurecult',
            token=PLEASURECULT_TOKEN,
            price_weekly=LUST4TRANS_PRICE_WEEKLY,
            price_monthly=LUST4TRANS_PRICE_MONTHLY,
            price_lifetime=LUST4TRANS_PRICE_LIFETIME,
            welcome_video=WELCOME_VIDEO_TSWRLD,
            paypal_weekly=None,
            paypal_monthly=None,
            paypal_lifetime=None,
            has_weekly=True,
            has_monthly=True,
            has_lifetime=True,
            portal_return_url=PLEASURECULT_PORTAL_RETURN_URL
        )
