# bots/morevids_bot.py
import os
import asyncio
import datetime
import stripe
from flask import abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import *
from bot_core.db import init_db, add_member, log_action, get_member_status
from bot_core.keyboards import main_menu_keyboard, plans_keyboard, payment_keyboard
from bot_core.texts import get_text

PORTAL_RETURN_URL = os.environ.get("MOREVIDS_PORTAL_RETURN_URL", "https://t.me/morevids_bot")

PAYPAL_MONTHLY_LINK = "https://www.paypal.com/paypalme/minwookim384/20usd"
PAYPAL_LIFETIME_LINK = "https://www.paypal.com/paypalme/minwookim384/50usd"
CRYPTO_ADDRESS = "TERhALhVLZRqnS3mZGhE1XgxyLnKHfgBLi"
CRYPTO_QR = "https://files.catbox.moe/aqlyct.jpg"

WELCOME_VIDEO_URL = "https://files.catbox.moe/dt49t2.mp4"

async def get_user_language(user_id):
    row = await get_member_status(user_id)
    return row['language'] if row and row['language'] else None

async def set_user_language(user_id, lang):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO members (user_id, language) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET language=$2',
            user_id, lang
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start', bot_name='morevids')
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
        await send_welcome_video_and_menu(update, context, lang)

async def send_welcome_video_and_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE, lang: str):
    chat_id = update_or_query.message.chat_id if hasattr(update_or_query, 'message') else update_or_query.callback_query.message.chat_id

    await context.bot.send_video(chat_id=chat_id, video=WELCOME_VIDEO_URL)

    today = datetime.datetime.utcnow().strftime("%b %d")
    text = get_text("morevids", lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
    reply_markup = main_menu_keyboard(lang)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_language(user_id)

    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1].upper()
        await set_user_language(user_id, new_lang)
        await query.edit_message_text(f"✅ Language changed to {new_lang}!")
        await send_welcome_video_and_menu(query, context, new_lang)
        return

    if query.data == 'plans':
        keyboard = plans_keyboard(lang, monthly=True, lifetime=True)
        await query.edit_message_text("🔥 Choose Your Membership Plan 🔥", parse_mode='Markdown', reply_markup=keyboard)
        return

    if query.data == 'select_monthly':
        keyboard = payment_keyboard(lang, is_lifetime=False)
        await query.edit_message_text(
            "💳 Select Payment Method for Monthly ($20)",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return

    if query.data == 'select_lifetime':
        keyboard = payment_keyboard(lang, is_lifetime=True)
        await query.edit_message_text(
            "💳 Select Payment Method for Lifetime ($50)",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return

    if query.data == 'pay_paypal_monthly':
        await query.edit_message_text(
            "💲 Pay via PayPal (Monthly $20)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay Now", url=PAYPAL_MONTHLY_LINK)]]),
            parse_mode='Markdown'
        )
    elif query.data == 'pay_paypal_lifetime':
        await query.edit_message_text(
            "💲 Pay via PayPal (Lifetime $50)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay Now", url=PAYPAL_LIFETIME_LINK)]]),
            parse_mode='Markdown'
        )
    elif query.data == 'pay_crypto':
        text = f"💎 Pay via Crypto\n\nAddress: `{CRYPTO_ADDRESS}`"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("QR Code", url=CRYPTO_QR)]]),
            parse_mode='Markdown'
        )
    elif query.data == 'pay_stripe_monthly':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': MOREVIDS_PRICE_MONTHLY, 'quantity': 1}],
            mode='subscription',
            success_url=PORTAL_RETURN_URL,
            cancel_url=PORTAL_RETURN_URL,
            metadata={'user_id': user_id, 'bot_name': 'morevids'}
        )
        await query.edit_message_text(
            "🔒 Redirecting to secure Stripe checkout (Monthly)...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=session.url)]])
        )
    elif query.data == 'pay_stripe_lifetime':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': MOREVIDS_PRICE_LIFETIME, 'quantity': 1}],
            mode='payment',
            success_url=PORTAL_RETURN_URL,
            cancel_url=PORTAL_RETURN_URL,
            metadata={'user_id': user_id, 'bot_name': 'morevids'}
        )
        await query.edit_message_text(
            "🔒 Redirecting to secure Stripe checkout (Lifetime)...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=session.url)]])
        )
