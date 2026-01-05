# bots/morevids_bot.py
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
BOT_TOKEN = os.getenv("MOREVIDS_TOKEN")
PRICE_MONTHLY = os.getenv("MOREVIDS_PRICE_MONTHLY")
PRICE_LIFETIME = os.getenv("MOREVIDS_PRICE_LIFETIME")
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

• Handpicked adult content daily.

• Premium OnlyFans clips curated for you.

• JANUARY 2026: ★ ACTIVE ★

──────────────────────────────

★ Price: Monthly $20 / Lifetime $50

★ INSTANT ACCESS ★

──────────────────────────────

💡 After payment, please send proof for verification
"""

VIDEO_URL = "https://files.catbox.moe/dt49t2.mp4"

# START command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start')

    keyboard = [
        [InlineKeyboardButton("Explore Premium Content", callback_data='show_content')]
    ]
    await update.message.reply_text(
        "Welcome! Tap below to see exclusive videos and subscription options.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# 버튼 처리
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'show_content':
        keyboard = [
            [InlineKeyboardButton("💳 Stripe Monthly", callback_data='pay_stripe_monthly')],
            [InlineKeyboardButton("💎 Stripe Lifetime", callback_data='pay_stripe_lifetime')],
            [InlineKeyboardButton("💸 PayPal Payment", url="https://www.paypal.com/paypalme/minwookim384/20usd")],
            [InlineKeyboardButton("₿ Crypto Payment", url="https://t.me/mbrypie")],
            [InlineKeyboardButton("📤 Send Proof", url="https://t.me/mbrypie")]
        ]
        await query.message.reply_video(video=VIDEO_URL, caption=DESCRIPTION, reply_markup=InlineKeyboardMarkup(keyboard))
        await query.message.delete()

    elif query.data.startswith('pay_stripe_'):
        plan_type = query.data.split('_')[-1]
        price_id = PRICE_MONTHLY if plan_type == 'monthly' else PRICE_LIFETIME

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription' if plan_type == 'monthly' else 'payment',
            success_url="https://t.me/morevids_bot",
            cancel_url="https://t.me/morevids_bot",
            metadata={'user_id': user_id}
        )
        await query.edit_message_text(
            f"Redirecting to Stripe for {plan_type.capitalize()} payment...",
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

        # plan 결정
        price_id = session['line_items']['data'][0]['price']['id']
        is_lifetime = (price_id == PRICE_LIFETIME)
        amount = 50 if is_lifetime else 20

        asyncio.run(add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime))
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime' if is_lifetime else 'payment_stripe_monthly', amount))

        invite_link, expire_time = asyncio.run(create_invite_link(application.bot))
        plan_name = "Lifetime 💎" if is_lifetime else "Monthly 🔄"

        asyncio.run(application.bot.send_message(
            user_id,
            f"🎉 {plan_name} Payment Successful!\n\n"
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

    print("morevids_bot is running!")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())

