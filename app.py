# app.py
import os
import datetime
import logging
import stripe
import html  # email escape 용
from fastapi import FastAPI, Request, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut
from bot_core.db import get_pool, init_db, add_member, log_action, get_member_status
from bot_core.utils import create_invite_link, send_daily_report
from bots.let_mebot import LetMeBot
from bots.morevids_bot import MoreVidsBot
from bots.onlytrns_bot import OnlyTrnsBot
from bots.tswrldbot import TsWrldBot
from bots.lust4trans_bot import Lust4transBot
from config import (
    STRIPE_WEBHOOK_SECRET, RENDER_EXTERNAL_URL, ADMIN_USER_ID,
    LETMEBOT_TOKEN, MOREVIDS_TOKEN, ONLYTRNS_TOKEN, TSWRLDBOT_TOKEN, LUST4TRANS_TOKEN,
    LUST4TRANS_PROMOTER_ID, TSWRLDBOT_PROMOTER_ID, CHANNEL_ID, PLAN_PRICES
)
import transaction_report

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

BOT_CLASSES = {
    "letmebot": {"cls": LetMeBot, "token": LETMEBOT_TOKEN},
    "morevids": {"cls": MoreVidsBot, "token": MOREVIDS_TOKEN},
    "onlytrns": {"cls": OnlyTrnsBot, "token": ONLYTRNS_TOKEN},
    "tswrld": {"cls": TsWrldBot, "token": TSWRLDBOT_TOKEN},
    "lust4trans": {"cls": Lust4transBot, "token": LUST4TRANS_TOKEN},
}

applications = {}

@app.on_event("startup")
async def startup_event():
    pool = await get_pool()
    await init_db(pool)
    for key, cfg in BOT_CLASSES.items():
        bot_instance = cfg["cls"]()
        telegram_app = Application.builder().token(cfg["token"]).build()

        telegram_app.add_handler(CommandHandler("start", bot_instance.start))
        telegram_app.add_handler(CallbackQueryHandler(bot_instance.button_handler))

        # /paid 명령어 - 제한 제거
        telegram_app.add_handler(CommandHandler("paid", paid_command))

        # /kick 명령어 - 제한 제거 + 강제 kick
        telegram_app.add_handler(CommandHandler("kick", kick_command))

        # /user 명령어 - 관리자 + Lust4trans 홍보자 전용 (v19 이하 호환)
        telegram_app.add_handler(CommandHandler("user", user_count_command, filters=filters.User(user_id=ADMIN_USER_ID) | filters.User(user_id=int(LUST4TRANS_PROMOTER_ID))))

        # /stats 명령어 - 관리자 + Lust4trans 홍보자 전용 (v19 이하 호환)
        telegram_app.add_handler(CommandHandler("stats", lust4trans_stats_command, filters=filters.User(user_id=ADMIN_USER_ID) | filters.User(user_id=int(LUST4TRANS_PROMOTER_ID))))

        telegram_app.add_handler(CommandHandler("transactions", transaction_report.transactions_command))
        telegram_app.add_handler(CommandHandler("sync_stripe", transaction_report.sync_stripe_command))

        telegram_app.job_queue.run_daily(
            send_daily_report,
            time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc)
        )

        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{key}"
        try:
            await telegram_app.bot.set_webhook(url=webhook_url)
            logger.info(f"{key} webhook set: {webhook_url}")
        except TimedOut:
            logger.warning(f"Webhook set timeout for {key}")
        except Exception as e:
            logger.error(f"Webhook set failed for {key}: {e}")

        await telegram_app.initialize()
        await telegram_app.start()
        applications[key] = {"app": telegram_app, "bot_instance": bot_instance}

    logger.info(f"Registered applications keys: {list(applications.keys())}")

@app.get("/health")
async def health():
    return "OK"

@app.post("/webhook/{bot_key}")
async def telegram_webhook(request: Request, bot_key: str):
    if bot_key not in applications:
        logger.error(f"Unknown bot_key: {bot_key}")
        raise HTTPException(status_code=404)
    
    telegram_app = applications[bot_key]["app"]
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Telegram webhook error for {bot_key}: {e}")
        raise HTTPException(status_code=400)

@app.post("/stripe_webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400)

    event_type = event['type']

    try:
        logger.info(f"Webhook event received - type: {event_type}, subscription_id: {event['data']['object'].get('subscription', 'N/A')}")

        if event_type == "checkout.session.completed":
            session = event['data']['object']
            user_id = int(session['metadata'].get('user_id', 0))
            bot_name = session['metadata'].get('bot_name', 'unknown')
            plan = session['metadata'].get('plan', 'monthly')
            subscription_id = session.get('subscription')
            customer_id = session['customer']

            if user_id and bot_name != 'unknown':
                username = session['metadata'].get('username', f"user_{user_id}")
                email = session.get('customer_details', {}).get('email', 'unknown')

                expiry = None
                is_lifetime = plan == 'lifetime'
                if not is_lifetime:
                    days = 7 if plan == 'weekly' else 30
                    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=days)

                pool = await get_pool()
                await add_member(
                    pool, user_id, username, customer_id, subscription_id,
                    is_lifetime=is_lifetime, expiry=expiry, bot_name=bot_name, email=email
                )
                await log_action(pool, user_id, f'payment_stripe_{plan}', session['amount_total'] / 100, bot_name)

                # 첫 결제 성공 시 invite link 생성 및 알림
                if bot_name in applications:
                    bot = applications[bot_name]["app"].bot
                    link, expiry_str = await create_invite_link(bot)
                    await bot.send_message(
                        user_id,
                        f"✅ Payment successful!\n\nYour invite link (expires in 5 min):\n{link}\n\n{expiry_str}"
                    )

                # 첫 결제 알림 → admin & promoter
                amount = session['amount_total'] / 100
                email_display = f"• Email: {html.escape(email)}" if email and email != 'unknown' else ''
                msg = (
                    f"💳 **New Subscription (First Payment)**\n\n"
                    f"• Bot: {bot_name.upper()}\n"
                    f"• User: @{username} (ID: {user_id})\n"
                    f"{email_display}\n"
                    f"• Plan: {plan.capitalize()}\n"
                    f"• Amount: ${amount:.2f}\n"
                    f"• Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                )

                # Admin
                try:
                    await applications["letmebot"]["app"].bot.send_message(ADMIN_USER_ID, msg, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Admin notify fail: {e}")

                # Promoter
                promoter_id = None
                if bot_name == "lust4trans":
                    promoter_id = int(LUST4TRANS_PROMOTER_ID or 0)
                elif bot_name == "tswrld":
                    promoter_id = int(TSWRLDBOT_PROMOTER_ID or 0)

                if promoter_id and promoter_id != ADMIN_USER_ID:
                    try:
                        await applications[bot_name]["app"].bot.send_message(promoter_id, msg, parse_mode='Markdown')
                    except Exception as e:
                        logger.error(f"Promoter notify fail {promoter_id}: {e}")

        elif event_type == "invoice.payment_succeeded":
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            if subscription_id:
                pool = await get_pool()
                row = await pool.fetchrow(
                    "SELECT user_id, bot_name, username, email FROM members WHERE stripe_subscription_id = $1",
                    subscription_id
                )

                if row:
                    user_id = row['user_id']
                    bot_name = row['bot_name']
                    username = row['username'] or f"ID{user_id}"
                    email = row['email'] or 'unknown'

                    amount = invoice['amount_paid'] / 100.0
                    plan = "monthly"  # 재결제는 기본 monthly로 가정

                    await log_action(pool, user_id, 'payment_stripe_renewal', amount, bot_name)

                    is_renewal = invoice.get('billing_reason') == 'subscription_cycle'

                    email_display = f"• Email: {html.escape(email)}" if email and email != 'unknown' else ''
                    msg = (
                        f"{'🔄 **Subscription Renewed**' if is_renewal else '💳 **Payment Succeeded**'}\n\n"
                        f"• Bot: {bot_name.upper()}\n"
                        f"• User: @{username} (ID: {user_id})\n"
                        f"{email_display}\n"
                        f"• Amount: ${amount:.2f}\n"
                        f"• Subscription: {subscription_id[:12]}...\n"
                        f"• Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                    )

                    # Admin 알림
                    try:
                        await applications["letme
