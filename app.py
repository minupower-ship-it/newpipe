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
                    is_lifetime=is_lifetime, expiry=expiry
