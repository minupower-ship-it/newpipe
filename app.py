# app.py
import os
import asyncio
import logging
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, JobQueue

from config import *
from bot_core.db import init_db, add_member, log_action, get_pool
from bot_core.utils import create_invite_link, send_daily_report

# 봇 핸들러 import
from bots.let_mebot import start as letme_start, button_handler as letme_handler
from bots.onlytrns_bot import start as onlytrns_start, button_handler as onlytrns_handler
from bots.tswrldbot import start as tswrld_start, button_handler as tswrld_handler
from bots.morevids_bot import start as morevids_start, button_handler as morevids_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")
if not BASE_URL:
    raise ValueError("RENDER_EXTERNAL_URL 환경변수 필수!")

PORT = int(os.environ.get("PORT", 10000))

BOT_CONFIG = {
    "letme": {"token": LETMEBOT_TOKEN, "name": "letmebot"},
    "onlytrns": {"token": ONLYTRNS_TOKEN, "name": "onlytrns"},
    "tswrld": {"token": TSWRLDBOT_TOKEN, "name": "tswrld"},
    "morevids": {"token": MOREVIDS_TOKEN, "name": "morevids"},
}

applications = {}

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
        price_id = session['line_items']['data'][0]['price']['id']
        is_lifetime = any(price_id == cfg.get(f"{bot_name.upper()}_PRICE_LIFETIME") for cfg in [globals()])
        amount = 50 if is_lifetime else 20  # 실제 가격은 bot별로 다름

        asyncio.create_task(handle_successful_payment(user_id, username, session, is_lifetime, bot_name, amount))

    return '', 200

async def handle_successful_payment(user_id, username, session, is_lifetime, bot_name, amount):
    await add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime, bot_name)
    await log_action(user_id, f'payment_stripe_{"lifetime" if is_lifetime else "monthly"}', amount)

    # 자동 초대 링크 생성 및 전송
    app = next((a for a in applications.values() if a.bot.username.lower().startswith(bot_name)), None)
    if app:
        try:
            link, expiry = await create_invite_link(app.bot)
            await app.bot.send_message(user_id, f"🎉 Payment successful!\n\nYour access link (expires {expiry}):\n{link}")
        except Exception as e:
            logger.error(f"Invite link send failed for {user_id}: {e}")

@flask_app.route('/webhook/<token>', methods=['POST'])
def telegram_webhook(token):
    app = next((a for a in applications.values() if a.bot.token == token), None)
    if not app:
        return abort(404)

    try:
        update = Update.de_json(request.get_json(force=True), app.bot)
        asyncio.create_task(app.process_update(update))
    except Exception as e:
        logger.error(f"Update processing error: {e}")

    return 'OK'

async def setup_bots():
    await init_db()

    for key, cfg in BOT_CONFIG.items():
        token = cfg["token"]
        bot_name = cfg["name"]
        app = Application.builder().token(token).build()

        # 핸들러 등록
        start_handler = globals()[f"{key}_start"]
        handler = globals()[f"{key}_handler"]
        app.add_handler(CommandHandler("start", start_handler))
        app.add_handler(CallbackQueryHandler(handler))

        # Job Queue (매일 리포트)
        app.job_queue.run_daily(send_daily_report, time=datetime.time(9, 0, 0))

        webhook_url = f"{BASE_URL}/webhook/{token}"
        await app.bot.set_webhook(url=webhook_url)
        logger.info(f"{bot_name.upper()} webhook set: {webhook_url}")

        await app.initialize()
        await app.start()
        applications[key] = app

if __name__ == "__main__":
    asyncio.run(setup_bots())
    logger.info("All 4 bots running with WEBHOOK!")
    flask_app.run(host="0.0.0.0", port=PORT)
