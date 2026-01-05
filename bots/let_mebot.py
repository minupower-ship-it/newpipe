# bots/let_mebot.py
import os
import asyncio
import datetime
import threading
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from bot_core.base import t, get_user_language, create_stripe_session
from bot_core.keyboards import language_selection_keyboard, main_menu_keyboard, plan_selection_keyboard, payment_method_keyboard
from bot_core.db import init_db, add_member, log_action, get_member_status
from bot_core.db import create_invite_link, send_daily_report  # 채널 초대 / 일일 보고

# 환경변수
BOT_TOKEN = os.getenv("LETMEBOT_TOKEN")
PRICE_ID_MONTHLY = os.getenv("LETMEBOT_PRICE_MONTHLY")
PRICE_ID_LIFETIME = os.getenv("LETMEBOT_PRICE_LIFETIME")
PORT = int(os.getenv("PORT", 10000))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))  # 관리자 ID
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))        # 채널 ID
SUCCESS_URL = f"https://t.me/{os.getenv('BOT_USERNAME', 'yourbot')}"
CANCEL_URL = SUCCESS_URL

flask_app = Flask(__name__)
application = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await log_action(user_id, 'start')

    lang = await get_user_language(user_id)

    if not lang:
        await update.message.reply_text(
            "🌍 Please select your preferred language:\n\n"
            "🇬🇧 English\n🇸🇦 العربية\n🇪🇸 Español",
            reply_markup=language_selection_keyboard()
        )
    else:
        await show_main_menu(update, context, lang)


async def show_main_menu(update, context, lang: str):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%b %d")
    text = t("welcome", lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
    reply_markup = main_menu_keyboard({
        "plans_btn": "📦 View Plans",
        "status_btn": "📊 My Subscription",
        "help_btn": "❓ Help & Support"
    })
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_language(user_id) or "EN"

    # 언어 선택
    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1].upper()
        await add_member(user_id, query.from_user.username, language=new_lang)  # DB에 저장
        await query.edit_message_text(f"✅ Language changed to {new_lang}!")
        await show_main_menu(query, context, new_lang)
        return

    # 메인 메뉴 버튼
    if query.data == 'plans':
        await query.edit_message_text(
            t("select_plan", lang),
            parse_mode='Markdown',
            reply_markup=plan_selection_keyboard({
                "monthly": "🔄 Monthly — $20/month",
                "lifetime": "💎 Lifetime — $50",
                "back": "⬅️ Back"
            })
        )

    # 플랜 선택
    elif query.data in ['select_monthly', 'select_lifetime']:
        is_lifetime = query.data == 'select_lifetime'
        plan_name = "Lifetime ($50)" if is_lifetime else "Monthly ($20)"
        await query.edit_message_text(
            t("payment_method", lang, plan=plan_name),
            parse_mode='Markdown',
            reply_markup=payment_method_keyboard({
                "pay_now": "💳 Pay with Stripe",
                "back": "⬅️ Back"
            }, is_lifetime)
        )

    # Stripe 결제
    elif query.data.startswith('pay_stripe_'):
        plan_type = query.data.split('_')[2]
        price_id = PRICE_ID_MONTHLY if plan_type == "monthly" else PRICE_ID_LIFETIME
        is_lifetime = plan_type == "lifetime"

        session = await create_stripe_session(user_id, price_id, mode="subscription" if not is_lifetime else "payment",
                                             success_url=SUCCESS_URL, cancel_url=CANCEL_URL)
        await query.edit_message_text(
            t("stripe_redirect", lang) if hasattr(t, "stripe_redirect") else "Redirecting to Stripe...",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("pay_now", lang), url=session.url)]])
        )

    # 상태 확인
    elif query.data == 'status':
        row = await get_member_status(user_id)
        if not row:
            await query.edit_message_text(
                t("no_sub", lang),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 View Plans", callback_data='plans')]])
            )
        else:
            plan_text = "Lifetime 💎" if row['is_lifetime'] else "Monthly 🔄"
            payment_date = row['created_at'].strftime('%b %d, %Y')
            expire_text = "Permanent access" if row['is_lifetime'] else row['expiry'].strftime('%b %d, %Y')

            message = (
                f"{t('status_title', lang)}\n\n"
                f"{t('plan', lang)}: {plan_text}\n"
                f"{t('payment_date', lang)}: {payment_date}\n"
                f"{t('expires', lang)}: {expire_text}\n"
            )
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data='back_to_main')]]))

    # 도움말
    elif query.data == 'help':
        await query.edit_message_text(
            t("help_text", lang) if hasattr(t, "help_text") else "Help & Support",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data='back_to_main')]])
        )

    # 메인 메뉴로 돌아가기
    elif query.data == 'back_to_main':
        await show_main_menu(query, context, lang)


@flask_app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    from bot_core.base import stripe  # 로컬 import
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET"))
    except Exception:
        return abort(400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        price_id = session['line_items']['data'][0]['price']['id']
        is_lifetime = price_id == PRICE_ID_LIFETIME
        amount = 50 if is_lifetime else 20

        asyncio.run(add_member(user_id, session.get('customer_details', {}).get('email') or f"user_{user_id}", session.get('customer'), session.get('subscription'), is_lifetime))
        asyncio.run(log_action(user_id, 'payment_stripe_lifetime' if is_lifetime else 'payment_stripe_monthly', amount))

        invite_link, expire_time = asyncio.run(create_invite_link(application.bot))
        plan = "Lifetime 💎" if is_lifetime else "Monthly 🔄"
        asyncio.run(application.bot.send_message(
            user_id,
            f"🎉 {plan} Payment Successful!\n\n"
            f"Your private channel invite link (expires in 10 minutes):\n{invite_link}\n\n"
            f"Expires: {expire_time}\n"
            f"Enjoy the premium content! 🔥"
        ))

    return '', 200


async def main():
    global application
    await init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.job_queue.run_daily(send_daily_report, time=datetime.time(9, 0))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    print("LETMEBOT is running!")

    await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
