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

CRYPTO_ADDRESS = "TERhALhVLZRqnS3mZGhE1XgxyLnKHfgBLi"
CRYPTO_QR_PATH = "static/crypto_qr.png"  # 프로젝트에 저장한 QR 코드 경로

PAYPAL_LINKS = {
    "monthly": "https://www.paypal.com/paypalme/minwookim384/20usd",
    "lifetime": "https://www.paypal.com/paypalme/minwookim384/50usd",
    "tswrld": "https://www.paypal.com/paypalme/minwookim384/25usd"
}

# --- 기존 start, language 선택, main menu 등 생략 ---
# show_main_menu / get_user_language / set_user_language 등 그대로 유지

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

# --- Stripe webhook / main / Flask 앱 등 그대로 유지 ---
