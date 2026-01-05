import asyncio
import datetime
from datetime import timezone
import stripe
import asyncpg
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from bot_core.base import t, get_user_language, set_user_language, create_invite_link, send_daily_report
from bot_core.db import init_db, add_member, log_action, get_member_status
from bot_core.keyboards import MAIN_MENU_KEYBOARD, PLAN_KEYBOARD

import os

LETMEBOT_TOKEN = os.getenv("LETMEBOT_TOKEN")
PRICE_ID_MONTHLY = os.getenv("LETMEBOT_PRICE_MONTHLY")
PRICE_ID_LIFETIME = os.getenv("LETMEBOT_PRICE_LIFETIME")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 10000))

stripe.api_key = STRIPE_SECRET_KEY

flask_app = Flask(__name__)
application = None

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
    today = datetime.datetime.now(timezone.utc).strftime("%b %d")
    text = t("welcome", lang) + t("date_line", lang, date=today)
    
    reply_markup = InlineKeyboardMarkup(MAIN_MENU_KEYBOARD(lang))
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_language(user_id) or "EN"

    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1].upper()
        await set_user_language(user_id, new_lang)
        await query.edit_message_text(f"✅ Language changed to {new_lang}!")
        await show_main_menu(query, context, new_lang)
        return

    # 플랜 선택
    if query.data == 'plans':
        keyboard = InlineKeyboardMarkup(PLAN_KEYBOARD(lang))
        await query.edit_message_text(t("select_plan", lang), parse_mode='Markdown', reply_markup=keyboard)

    elif query.data.startswith('select_'):
        plan_type = query.data.split('_')[1]
        is_lifetime = plan_type == 'lifetime'
        plan_name = "Lifetime ($50)" if is_lifetime else "Monthly ($20)"
        price_id = PRICE_ID_LIFETIME if is_lifetime else PRICE_ID_MONTHLY

        keyboard = [
            [InlineKeyboardButton(t("stripe", lang), callback_data=f'pay_stripe_{plan_type}')],
            [InlineKeyboardButton(t("paypal", lang), callback_data=f'pay_paypal_{plan_type}')],
            [InlineKeyboardButton(t("crypto", lang), callback_data=f'pay_crypto_{plan_type}')],
            [InlineKeyboardButton(t("back", lang), callback_data='plans')]
        ]
        await query.edit_message_text(
            t("payment_method", lang, plan=plan_name),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Stripe 결제
    elif query.data.startswith('pay_stripe_'):
        plan_type = query.data.split('_')[2]
        price_id = PRICE_ID_LIFETIME if plan_type == 'lifetime' else PRICE_ID_MONTHLY
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription' if plan_type == 'monthly' else 'payment',
            success_url="https://t.me/your_bot_username",
            cancel_url="https://t.me/your_bot_username",
            metadata={'user_id': user_id}
        )
        await query.edit_message_text(
            t("stripe_redirect", lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("pay_now", lang), url=session.url)]])
        )

    # PayPal & Crypto 처리
    elif query.data.startswith('pay_paypal_') or query.data.startswith('pay_crypto_'):
        # 유저에게 링크/QR 보내고 proof 버튼
        await query.message.reply_text("💡 Send proof after payment to get access.")
        await query.message.delete()

    # 구독 상태 확인
    elif query.data == 'status':
        row = await get_member_status(user_id)
        if not row:
            await query.edit_message_text(
                t("no_sub", lang),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("plans_btn", lang), callback_data='plans')]])
            )
        else:
            plan_text = "Lifetime 💎" if row['is_lifetime'] else "Monthly 🔄"
            payment_date = row['created_at'].strftime('%b %d, %Y')
            expire_text = "Permanent access" if row['is_lifetime'] else row['expiry'].strftime('%b %d, %Y')
            msg = f"{t('status_title', lang)}\n\n{t('plan', lang)}: {plan_text}\n{t('payment_date', lang)}: {payment_date}\n{t('expires', lang)}: {expire_text}\n\n{t('manage_sub', lang)}"
            await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data='back_to_main')]]))

    # Help
    elif query.data == 'help':
        await query.edit_message_text(t("help_text", lang), parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data='back_to_main')]]))

    elif query.data == 'back_to_main':
        await show_main_menu(query, context, lang)

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
        price_id = session['line_items']['data'][0]['price']['id']
        is_lifetime = price_id == PRICE_ID_LIFETIME
        amount = 50 if is_lifetime else 20

        asyncio.run(add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime))
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime' if is_lifetime else 'payment_stripe_monthly', amount))

        # 초대 링크 생성
        invite_link, expire_time = asyncio.run(create_invite_link(application.bot))
        plan = "Lifetime 💎" if is_lifetime else "Monthly 🔄"
        asyncio.run(application.bot.send_message(
            user_id,
            f"🎉 {plan} Payment Successful!\n\nYour private channel invite link (expires in 10 minutes):\n{invite_link}\n\nExpires: {expire_time}\nEnjoy the premium content! 🔥"
        ))
    return '', 200

# 메인 실행
async def main():
    global application
    await init_db()
    application = Application.builder().token(LETMEBOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.job_queue.run_daily(send_daily_report, time=datetime.time(9, 0))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Flask Webhook
    import threading
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    print("LETMEBOT is running!")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
