# bots/let_mebot.py
from bot_core.base_bot import BaseBot
from config import LETMEBOT_TOKEN, LETMEBOT_PRICE_MONTHLY, LETMEBOT_PRICE_LIFETIME, LETMEBOT_PORTAL_RETURN_URL, PAYPAL_LETME_MONTHLY, PAYPAL_LETME_LIFETIME

class LetMeBot(BaseBot):
    def __init__(self):
        super().__init__(
            bot_name='letmebot',
            token=LETMEBOT_TOKEN,
            price_monthly=LETMEBOT_PRICE_MONTHLY,
            price_lifetime=LETMEBOT_PRICE_LIFETIME,
            paypal_monthly=PAYPAL_LETME_MONTHLY,
            paypal_lifetime=PAYPAL_LETME_LIFETIME,
            has_monthly=True,
            has_lifetime=True,
            portal_return_url=LETMEBOT_PORTAL_RETURN_URL
        )
