# bots/tswrldbot.py
from bot_core.base_bot import BaseBot
from config import TSWRLDBOT_TOKEN, TSWRLDBOT_PRICE_LIFETIME, TSWRLDBOT_PORTAL_RETURN_URL, PAYPAL_TSWRLD, WELCOME_VIDEO_TSWRLD

class TsWrldBot(BaseBot):
    def __init__(self):
        super().__init__(
            bot_name='tswrld',
            token=TSWRLDBOT_TOKEN,
            price_lifetime=TSWRLDBOT_PRICE_LIFETIME,
            welcome_video=WELCOME_VIDEO_TSWRLD,
            paypal_lifetime=PAYPAL_TSWRLD,
            has_monthly=False,
            has_lifetime=True,
            portal_return_url=TSWRLDBOT_PORTAL_RETURN_URL
        )
