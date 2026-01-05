# bots/onlytrns_bot.py
import asyncio
import datetime
from datetime import timezone
import stripe
import asyncpg
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from base import create_invite_link
from db import init_db, add_member, log_action, get_member_status
from keyboards import main_keyboard

import os

# 환경변수
BOT_TOKEN = os.getenv("ONLYTRNS_TOKEN")
PRICE_LIFETIME = os.getenv("ONLYTRNS_PRICE_LIFETIME")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 10000))

stripe.api_key = STRIPE_SECRET_KEY

flask_app = Flask(__name__)
application = None

# description + video
DESCRIPTION = """──────────────────────────────

Welcome to Private Collection

──────────────────────────────

• Only high quality handpicked content.

• Premium ★nlyFans Videos

• DECEMBER 2025: ★ ACTIVE ★

──────────────────────────────

★ Price: $25

★ INSTANT ACCESS ★

──────────────────────────────

💡 After payment, please send proof
"""

VIDEO_URL = "https://files.catbox.moe/8ku53d.mp4"

# 다국어는 필요 없어서 EN만 사용

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start')

    keyboard = [
        [InlineKeyboardButton("Show Collection", callback_data='show_content')]
    ]

    await update.message.reply_text(
        "Welcome! Tap below to see the premium content.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'show_content':
        keyboard = [
            [InlineKeyboardButton("💳 Stripe Payment", callback_data='pay_stripe')],
            [InlineKeyboardButton("💸 PayPal Payment", url="https://www.paypal.com/paypalme/minwookim384/25usd")],
            [InlineKeyboardButton("📤 Send Proof", url="https://t.me/mbrypie")]
        ]
        await query.message.reply_video(video=VIDEO_URL, caption=DESCRIPTION, reply_markup=InlineKeyboardMarkup(keyboard))
        await query.message.delete()

    elif query.data == 'pay_stripe':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': PRICE_LIFETIME, 'quantity': 1}],
            mode='payment',
            success_url="https://t.me/onlytrns_bot",
            cancel_url="https://t.me/onlytrns_bot",
            metadata={'user_id': user_id}
        )
        await query.edit_message_text(
            "Redirecting to Stripe checkout...",
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
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime', 25))

        # 자동 초대 링크 생성
        invite_link, expire_time = asyncio.run(create_invite_link(application.bot))
        asyncio.run(application.bot.send_message(
            user_id,
            f"🎉 Lifetime Payment Successful!\n\n"
            f"Your private channel invite link (expires in 10 minutes):\n{invite_link}\n\n"
            f"Expires: {expire_time}\nEnjoy the premium content! 🔥"
        ))

    return '', 200

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

    print("onlytrns_bot is running!")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())

