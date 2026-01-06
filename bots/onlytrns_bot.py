# bots/onlytrns_bot.py
from bot_core.base_bot import BaseBot
from config import ONLYTRNS_TOKEN, ONLYTRNS_PRICE_LIFETIME, ONLYTRNS_PORTAL_RETURN_URL, PAYPAL_ONLYTRNS, WELCOME_VIDEO_ONLYTRNS

class OnlyTrnsBot(BaseBot):
    def __init__(self):
        super().__init__(
            bot_name='onlytrns',
            token=ONLYTRNS_TOKEN,
            price_lifetime=ONLYTRNS_PRICE_LIFETIME,
            welcome_video=WELCOME_VIDEO_ONLYTRNS,
            paypal_lifetime=PAYPAL_ONLYTRNS,
            has_monthly=False,
            has_lifetime=True,
            portal_return_url=ONLYTRNS_PORTAL_RETURN_URL
        )
