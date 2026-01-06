# bots/let_mebot.py
import asyncio
import datetime
from datetime import timezone
import stripe
import asyncpg
from flask import Flask, request, abort
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import *
from bot_core.db import init_db, add_member, log_action, get_member_status
from bot_core.keyboards import main_menu_keyboard, plans_keyboard, payment_keyboard
from bot_core.texts import get_text

stripe.api_key = STRIPE_SECRET_KEY

flask_app = Flask(__name__)
application = None

# Crypto
CRYPTO_ADDRESS = "TERhALhVLZRqnS3mZGhE1XgxyLnKHfgBLi"
CRYPTO_QR_PATH = "static/crypto_qr.png"  # QR 코드 이미지 경로

# PayPal 링크
PAYPAL_LINKS = {
    "monthly": "https://www.paypal.com/paypalme/minwookim384/20usd",
    "lifetime": "https://www.paypal.com/paypalme/minwookim384/50usd",
    "tswrld": "https://www.paypal.com/paypalme/minwookim384/25usd"
}

# --- 사용자 언어 DB ---
async def get_user_language(user_id):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow('SELECT language FROM members WHERE user_id = $1', user_id)
    await conn.close()
    return row['language'] if row and row['language'] else "EN"

async def set_user_language(user_id, lang):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        'INSERT INTO members (user_id, language) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET language=$2',
        user_id, lang
    )
    await conn.close()

# --- 시작 / 메뉴 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start')
    lang = await get_user_language(user_id)

    if not lang:
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
            [InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')],
            [InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]
        ]
        await update.message.reply_text(
            "🌍 Please select your preferred language:\n\n"
            "🇬🇧 English\n"
            "🇸🇦 العربية\n"
            "🇪🇸 Español",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await show_main_menu(update, context, lang)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    today = datetime.datetime.utcnow().strftime("%b %d")
    text = get_text("letmebot", lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
    reply_markup = main_menu_keyboard(lang)
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# --- 버튼 처리 ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_language(user_id)

    # 언어 선택
    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1].upper()
        await set_user_language(user_id, new_lang)
        await query.edit_message_text(f"✅ Language changed to {new_lang}!")
        await show_main_menu(query, context, new_lang)
        return

    # Plans 버튼
    if query.data == 'plans':
        keyboard = plans_keyboard(lang, monthly=True, lifetime=True)
        await query.edit_message_text("🔥 Choose Your Membership Plan 🔥", parse_mode='Markdown', reply_markup=keyboard)

    # Stripe 결제
    elif query.data.startswith('pay_stripe_'):
        plan_type = query.data.split('_')[2]
        price_id = LETMEBOT_PRICE_MONTHLY if plan_type == 'monthly' else LETMEBOT_PRICE_LIFETIME

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription' if plan_type == 'monthly' else 'payment',
            success_url=PORTAL_RETURN_URL,
            cancel_url=PORTAL_RETURN_URL,
            metadata={'user_id': user_id}
        )
        await query.edit_message_text(
            "🔒 Redirecting to secure Stripe checkout...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=session.url)]])
        )

    # PayPal 결제
    elif query.data.startswith('pay_paypal_'):
        plan_type = query.data.split('_')[2]
        link = PAYPAL_LINKS.get(plan_type)
        await query.edit_message_text(
            f"💲 Pay via PayPal ({plan_type.capitalize()})",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay Now", url=link)]]),
            parse_mode='Markdown'
        )

    # Crypto 결제
    elif query.data == 'pay_crypto':
        await query.message.reply_text(f"💰 Send crypto payment to this address:\n`{CRYPTO_ADDRESS}`", parse_mode='Markdown')
        await query.message.reply_photo(InputFile(CRYPTO_QR_PATH))

# --- Stripe Webhook ---
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
        price_id = session['line_items']['data'][0]['price']['id']
        is_lifetime = price_id == LETMEBOT_PRICE_LIFETIME
        amount = 50 if is_lifetime else 20

        asyncio.run(add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime))
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime' if is_lifetime else 'payment_stripe_monthly', amount))

        # TODO: invite_link 생성 후 메시지 전송

    return '', 200

# --- Main 실행 ---
async def main():
    global application
    await init_db()
    application = Application.builder().token(LETMEBOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    import threading
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    print("LETMEBOT running...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
