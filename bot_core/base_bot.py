# bot_core/base_bot.py (pay_stripe_ 부분만 변경, 나머지 그대로)

if query.data.startswith('pay_stripe_'):
    plan = query.data.split('_')[2]
    price_id = self.price_weekly if plan == 'weekly' else self.price_monthly if plan == 'monthly' else self.price_lifetime
    mode = 'subscription' if plan in ['weekly', 'monthly'] else 'payment'
    try:
        # metadata에 username 추가 (Telegram username 가져오기)
        username = query.from_user.username or f"user_{query.from_user.id}"
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode=mode,
            success_url=self.portal_return_url,
            cancel_url=self.portal_return_url,
            metadata={
                'user_id': query.from_user.id,
                'bot_name': self.bot_name,
                'plan': plan,
                'username': username  # ← 여기 추가!
            }
        )
        buttons = [
            [InlineKeyboardButton("💳 Pay Now", url=session.url)],
            [InlineKeyboardButton("Help", url="https://t.me/mbrypie")]
        ]
        await query.edit_message_text(
            f"🔒 Redirecting to secure Stripe checkout ({plan.capitalize()})...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Stripe session creation failed for {self.bot_name}: {e}")
        await query.edit_message_text("❌ Payment error. Please try again or contact support.")
    return
