# bots/let_mebot.py
import asyncio
import datetime
import stripe
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import *
from bot_core.db import log_action
from bot_core.keyboards import main_menu_keyboard, plans_keyboard, payment_keyboard
from bot_core.texts import get_text

PORTAL_RETURN_URL = os.environ.get("LETMEBOT_PORTAL_RETURN_URL", "https://t.me/yourbot")

# 사용자 언어 처리
async def get_user_language(user_id):
    from bot_core.db import get_member_status
    status = await get_member_status(user_id)
    return status['language'] if status and status.get('language') else "EN"

async def set_user_language(user_id, lang):
    from bot_core.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO members (user_id, language) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET language = $2",
            user_id, lang
        )

# /start 명령어
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start', bot_name='letmebot')
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

async def show_main_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE, lang: str):
    chat_id = update_or_query.message.chat_id if hasattr(update_or_query, 'message') else update_or_query.callback_query.message.chat_id
    today = datetime.datetime.utcnow().strftime("%b %d")
    text = get_text("letmebot", lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
    reply_markup = main_menu_keyboard(lang)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

# 버튼 핸들러
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

    # Plans
    if query.data == 'plans':
        keyboard = plans_keyboard(lang, monthly=True, lifetime=True)
        await query.edit_message_text("🔥 Choose Your Membership Plan 🔥", parse_mode='Markdown', reply_markup=keyboard)
        return

    if query.data == 'select_monthly':
        keyboard = payment_keyboard(lang, is_lifetime=False)
        await query.edit_message_text("💳 Select Payment Method for Monthly ($20)", parse_mode='Markdown', reply_markup=keyboard)
        return

    if query.data == 'select_lifetime':
        keyboard = payment_keyboard(lang, is_lifetime=True)
        await query.edit_message_text("💳 Select Payment Method for Lifetime ($50)", parse_mode='Markdown', reply_markup=keyboard)
        return

    # PayPal
    if query.data == 'pay_paypal_monthly':
        await query.edit_message_text(
            "💲 Pay via PayPal (Monthly $20)",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay Now", url="https://www.paypal.com/paypalme/minwookim384/20usd")]])
        )
    elif query.data == 'pay_paypal_lifetime':
        await query.edit_message_text(
            "💲 Pay via PayPal (Lifetime $50)",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay Now", url="https://www.paypal.com/paypalme/minwookim384/50usd")]])
        )

    # Crypto
    elif query.data.startswith('pay_crypto'):
        text = "💎 Pay via Crypto\n\nAddress: `TERhALhVLZRqnS3mZGhE1XgxyLnKHfgBLi`"
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("QR Code", url="https://files.catbox.moe/aqlyct.jpg")]])
        )

    # Stripe
    elif query.data.startswith('pay_stripe_'):
        plan_type = query.data.split('_')[2]
        price_id = LETMEBOT_PRICE_MONTHLY if plan_type == 'monthly' else LETMEBOT_PRICE_LIFETIME
        mode = 'subscription' if plan_type == 'monthly' else 'payment'

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode=mode,
            success_url=PORTAL_RETURN_URL,
            cancel_url=PORTAL_RETURN_URL,
            metadata={'user_id': str(user_id), 'bot_name': 'letmebot'}
        )
        await query.edit_message_text(
            "🔒 Redirecting to secure Stripe checkout...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=session.url)]])
        )
