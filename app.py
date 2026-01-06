# app.py
import os
import asyncio
import logging
import datetime
import threading
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.error import TimedOut

from config import *
from bot_core.db import init_db, add_member, log_action
from bot_core.utils import create_invite_link, send_daily_report

# 핸들러 명시적 import
from bots.let_mebot import start as letme_start, button_handler as letme_handler
from bots.morevids_bot import start as morevids_start, button_handler as morevids_handler
from bots.onlytrns_bot import start as onlytrns_start, button_handler as onlytrns_handler
from bots.tswrldbot import start as tswrld_start, button_handler as tswrld_handler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")
if not BASE_URL:
    raise ValueError("RENDER_EXTERNAL_URL 환경변수를 반드시 설정하세요!")

PORT = int(os.environ.get("PORT", 10000))

# Background async loop (no event loop 오류 해결)
async_loop = None

def run_async_loop():
    global async_loop
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    async_loop.run_forever()

threading.Thread(target=run_async_loop, daemon=True).start()

# Health 체크 엔드포인트 (Render 포트 감지용)
@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/')
def home():
    return "Bot service is running!", 200

# 봇 설정
BOT_HANDLERS = {
    "letme": {"start": letme_start, "handler": letme_handler, "token": LETMEBOT_TOKEN},
    "morevids": {"start": morevids_start, "handler": morevids_handler, "token": MOREVIDS_TOKEN},
    "onlytrns": {"start": onlytrns_start, "handler": onlytrns_handler, "token": ONLYTRNS_TOKEN},
    "tswrld": {"start": tswrld_start, "handler": tswrld_handler, "token": TSWRLDBOT_TOKEN},
}

applications = {}

# Stripe Webhook
@flask_app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return abort(400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        bot_name = session['metadata'].get('bot_name', 'unknown')
        username = session.get('customer_details', {}).get('email') or f"user_{user_id}"

        is_lifetime = session['mode'] == 'payment'
        amount_map = {
            "letmebot": 50 if is_lifetime else 20,
            "onlytrns": 25,
            "tswrld": 21,
            "morevids": 50 if is_lifetime else 20,
        }
        amount = amount_map.get(bot_name, 0)

        asyncio.run_coroutine_threadsafe(handle_payment_success(user_id, username, session, is_lifetime, bot_name, amount), async_loop)

    return '', 200

async def handle_payment_success(user_id, username, session, is_lifetime, bot_name, amount):
    try:
        await add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime, bot_name)
        await log_action(user_id, f'payment_stripe_{"lifetime" if is_lifetime else "monthly"}', amount, bot_name)

        app = next((a for a in applications.values() if bot_name in a.bot.username.lower()), None)
        if app:
            link, expiry = await create_invite_link(app.bot)
            await app.bot.send_message(user_id, f"🎉 Payment successful!\n\nYour invite link (expires {expiry}):\n{link}\n\nWelcome!")
    except Exception as e:
        logger.error(f"Payment handling failed for {user_id}: {e}")

# Telegram Webhook
@flask_app.route('/webhook/<token>', methods=['POST'])
def telegram_webhook(token):
    app = next((a for a in applications.values() if a.bot.token == token), None)
    if not app:
        return abort(404)

    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, app.bot)
        asyncio.run_coroutine_threadsafe(app.process_update(update), async_loop)
    except Exception as e:
        logger.error(f"Telegram update error: {e}")

    return 'OK'

async def setup_bots():
    await init_db()

    for key, cfg in BOT_HANDLERS.items():
        token = cfg["token"]
        telegram_app = Application.builder().token(token).build()

        telegram_app.add_handler(CommandHandler("start", cfg["start"]))
        telegram_app.add_handler(CallbackQueryHandler(cfg["handler"]))

        # 매일 리포트
        telegram_app.job_queue.run_daily(
            send_daily_report,
            time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc)
        )

        webhook_url = f"{BASE_URL}/webhook/{token}"
        try:
            await telegram_app.bot.set_webhook(url=webhook_url)
            logger.info(f"{key.upper()} webhook set: {webhook_url}")
        except TimedOut:
            logger.warning(f"Webhook set timeout for {key}")
        except Exception as e:
            logger.error(f"Webhook set failed for {key}: {e}")

        await telegram_app.initialize()
        await telegram_app.start()
        applications[key] = telegram_app

if __name__ == "__main__":
    logger.info(f"Starting Flask server on http://0.0.0.0:{PORT}")
    flask_app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )

    # setup_bots 실행
    threading.Thread(target=asyncio.run, args=(setup_bots(),)).start()
