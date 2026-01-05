# bots/onlytrns_bot.py
import asyncio
import datetime
import stripe
import asyncpg
from flask import Flask, request, abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import *
from bot_core.db import init_db, add_member, log_action, get_member_status
from bot_core.keyboards import main_menu_keyboard, plans_keyboard, payment_keyboard
from bot_core.texts import get_text

stripe.api_key = STRIPE_SECRET_KEY
flask_app = Flask(__name__)
application = None

# 보낼 동영상 URL
WELCOME_VIDEO_URL = "https://files.catbox.moe/8ku53d.mp4"

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start')
    lang = await get_user_language(user_id)
    if not lang or lang == "EN" and lang is None:  # lang이 None일 수 있으니 안전하게
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
    """
    동영상을 먼저 보내고, 그 다음에 메인 메뉴를 보여주는 공통 함수
    update_or_query는 Update.message 또는 CallbackQuery일 수 있음
    """
    # chat_id 추출 (message든 callback_query든 동일)
    if hasattr(update_or_query, 'message'):
        chat_id = update_or_query.message.chat_id
    else:  # CallbackQuery
        chat_id = update_or_query.callback_query.message.chat_id

    # 동영상 보내기
    await context.bot.send_video(
        chat_id=chat_id,
        video=WELCOME_VIDEO_URL,
        parse_mode='Markdown'
    )

    # 그 후 메인 메뉴 표시
    today = datetime.datetime.utcnow().strftime("%b %d")
    text = get_text("onlytrns", lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
    reply_markup = main_menu_keyboard(lang)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    """
    기존 show_main_menu는 이제 내부에서만 사용 → 동영상 없이 메뉴 교체만 할 때 사용
    (예: 버튼 클릭 후 메뉴 갱신)
    """
    today = datetime.datetime.utcnow().strftime("%b %d")
    text = get_text("onlytrns", lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
    reply_markup = main_menu_keyboard(lang)

    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_language(user_id)

    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1].upper()
        await set_user_language(user_id, new_lang)
        await query.edit_message_text(f"✅ Language changed to {new_lang}!")
        # 언어 선택 후 동영상 + 메인 메뉴 보내기
        await send_welcome_video_and_menu(query, context, new_lang)
        return

    if query.data == 'plans':
        keyboard = plans_keyboard(lang, monthly=False, lifetime=True)
        await query.edit_message_text("🔥 Choose Your Membership Plan 🔥", parse_mode='Markdown', reply_markup=keyboard)

    elif query.data == 'select_lifetime':
        keyboard = payment_keyboard(lang, is_lifetime=True)
        await query.edit_message_text("💳 Select Payment Method for Lifetime ($25)", parse_mode='Markdown', reply_markup=keyboard)

    elif query.data.startswith('pay_stripe_'):
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': ONLYTRNS_PRICE_LIFETIME, 'quantity': 1}],
            mode='payment',
            success_url=PORTAL_RETURN_URL,
            cancel_url=PORTAL_RETURN_URL,
            metadata={'user_id': user_id}
        )
        await query.edit_message_text(
            "🔒 Redirecting to secure Stripe checkout...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=session.url)]])
        )

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
        asyncio.run(add_member(user_id, username, session.get('customer'), None, True))
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime', 25))
        # TODO: invite link 보내기

    return '', 200

async def main():
    global application
    await init_db()
    application = Application.builder().token(ONLYTRNS_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    import threading
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    print("ONLYTRNS BOT running...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
