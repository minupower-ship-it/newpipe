# bots/tswrldbot.py
import asyncio
import datetime
import stripe
import asyncpg
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from base import create_invite_link
from db import init_db, add_member, log_action, get_member_status

import os

# 환경변수
BOT_TOKEN = os.getenv("TSWRLDBOT_TOKEN")
PRICE_LIFETIME = os.getenv("TSWRLDBOT_PRICE_LIFETIME")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 10000))

stripe.api_key = STRIPE_SECRET_KEY

flask_app = Flask(__name__)
application = None

# description + video
DESCRIPTION = """──────────────────────────────

🎬 Welcome to private collection

──────────────────────────────

• Handpicked premium content only.

• ★ Selected ★ OnlyFans Clips

• JANUARY 2026: ★ ACTIVE ★

──────────────────────────────

★ Price: $21

★ INSTANT ACCESS ★

──────────────────────────────

💡 After payment, please send proof for verification
"""

VIDEO_URL = "https://files.catbox.moe/lx7rj5.mp4"

# START command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start')

    keyboard = [
        [InlineKeyboardButton("Show Vault", callback_data='show_content')]
    ]
    await update.message.reply_text(
        "Welcome! Tap below to explore premium content.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# 버튼 처리
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'show_content':
        keyboard = [
            [InlineKeyboardButton("💳 Stripe Checkout", callback_data='pay_stripe')],
            [InlineKeyboardButton("💸 PayPal Payment", url="https://www.paypal.com/paypalme/minwookim384/21usd")],
            [InlineKeyboardButton("📤 Send Proof", url="https://t.me/mbrypie")]
        ]
        await query.message.reply_video(video=VIDEO_URL, caption=DESCRIPTION, reply_markup=InlineKeyboardMarkup(keyboard))
        await query.message.delete()

    elif query.data == 'pay_stripe':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': PRICE_LIFETIME, 'quantity': 1}],
            mode='payment',
            success_url="https://t.me/tswrldbot",
            cancel_url="https://t.me/tswrldbot",
            metadata={'user_id': user_id}
        )
        await query.edit_message_text(
            "Redirecting you to Stripe checkout...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay Now", url=session.url)]])
        )

# Stripe Webhook
@flask_app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return abort(400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        username = session.get('customer_details', {}).get('email') or f"user_{user_id}"

        asyncio.run(add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime=True))
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime', 21))

        invite_link, expire_time = asyncio.run(create_invite_link(application.bot))
        asyncio.run(application.bot.send_message(
            user_id,
            f"🎉 Lifetime Payment Successful!\n\n"
            f"Your private channel invite link (expires in 10 minutes):\n{invite_link}\n\n"
            f"Expires: {expire_time}\nEnjoy the premium content! 🔥"
        ))

    return '', 200

# MAIN
async def main():
    global application
    await init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    import threading
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=PORT), daemon=True).start()

    print("tswrldbot is running!")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())

