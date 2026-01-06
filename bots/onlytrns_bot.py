# bots/onlytrns_bot.py
# ... import ...

WELCOME_VIDEO_URL = "https://files.catbox.moe/8ku53d.mp4"

# 언어 함수 동일

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 동영상 전송 로직 포함

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_language(user_id)

    if query.data.startswith('lang_'):
        # 언어 변경 동일

    if query.data == 'pay_paypal':
        # PayPal 링크

    if query.data == 'pay_crypto':
        # Crypto 주소

    if query.data == 'pay_stripe':
        session = stripe.checkout.Session.create(
            # ...
            metadata={'user_id': user_id, 'bot_name': 'onlytrns'}  # 필수
        )
        # 메시지
