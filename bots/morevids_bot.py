# bots/morevids_bot.py
from bot_core.base_bot import BaseBot
from config import MOREVIDS_TOKEN, MOREVIDS_PRICE_MONTHLY, MOREVIDS_PRICE_LIFETIME, MOREVIDS_PORTAL_RETURN_URL, PAYPAL_MOREVIDS_MONTHLY, PAYPAL_MOREVIDS_LIFETIME, WELCOME_VIDEO_MOREVIDS

class MoreVidsBot(BaseBot):
    def __init__(self):
        super().__init__(
            bot_name='morevids',
            token=MOREVIDS_TOKEN,
            price_monthly=MOREVIDS_PRICE_MONTHLY,
            price_lifetime=MOREVIDS_PRICE_LIFETIME,
            welcome_video=WELCOME_VIDEO_MOREVIDS,
            paypal_monthly=PAYPAL_MOREVIDS_MONTHLY,
            paypal_lifetime=PAYPAL_MOREVIDS_LIFETIME,
            has_monthly=True,
            has_lifetime=True,
            portal_return_url=MOREVIDS_PORTAL_RETURN_URL
        )
