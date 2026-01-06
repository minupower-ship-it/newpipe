# app.py
import os
import asyncio
import logging
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.error import TimedOut

from config import *
from bot_core.db import init_db, add_member, log_action
from bot_core.utils import create_invite_link, send_daily_report

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")
if not BASE_URL:
    raise ValueError("RENDER_EXTERNAL_URL 환경변수를 반드시 설정하세요!")

PORT = int(os.environ.get("PORT", 10000))

BOT_CONFIG = {
    "letme": {"token": LETMEBOT_TOKEN, "name": "letmebot"},
    "onlytrns": {"token": ONLYTRNS_TOKEN, "name": "onlytrns"},
    "tswrld": {"token": TSWRLDBOT_TOKEN, "name": "tswrld"},
    "morevids": {"token": MOREVIDS_TOKEN, "name": "morevids"},
}

applications = {}

# Stripe Webhook (봇 구분 처리)
@flask_app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Stripe webhook signature verification failed: {e}")
        return abort(400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        bot_name = session['metadata'].get('bot_name', 'unknown')
        username = session.get('customer_details', {}).get('email') or f"user_{user_id}"

        # 가격 ID로 lifetime 여부 판단 (간단히 bot_name 기반)
        is_lifetime = 'lifetime' in session['display_items'][0]['price']['id'].lower() if session.get('display_items') else True
        amount_map = {
            "letmebot": 50 if is_lifetime else 20,
            "onlytrns": 25,
            "tswrld": 21,
            "morevids": 50 if is_lifetime else 20,
        }
        amount = amount_map.get(bot_name, 0)

        asyncio.create_task(handle_payment_success(user_id, username, session, is_lifetime, bot_name, amount))

    return '', 200

async def handle_payment_success(user_id, username, session, is_lifetime, bot_name, amount):
    try:
        await add_member(user_id, username, session.get('customer'), session.get('subscription'), is_lifetime, bot_name)
        await log_action(user_id, f'payment_stripe_{"lifetime" if is_lifetime else "monthly"}', amount, bot_name)

        # 해당 봇 앱 찾아서 초대 링크 전송
        app = next((a for a in applications.values() if bot_name in a.bot.username.lower()), None)
        if app:
            link, expiry = await create_invite_link(app.bot)
            await app.bot.send_message(
                user_id,
                f"🎉 Payment Confirmed!\n\n"
                f"Your exclusive invite link (expires {expiry}):\n{link}\n\n"
                f"Welcome to the premium experience! 🌟"
            )
    except Exception as e:
        logger.error(f"Payment success handling failed for {user_id}: {e}")

# Telegram Webhook
@flask_app.route('/webhook/<token>', methods=['POST'])
def telegram_webhook(token):
    app = next((a for a in applications.values() if a.bot.token == token), None)
    if not app:
        return abort(404)

    try:
        update = Update.de_json(request.get_json(force=True), app.bot)
        asyncio.create_task(app.process_update(update))
    except Exception as e:
        logger.error(f"Telegram update error: {e}")

    return 'OK'

async def setup_bots():
    await init_db()

    for key, cfg in BOT_CONFIG.items():
        token = cfg["token"]
        bot_name = cfg["name"]

        app = Application.builder().token(token).build()

        # 핸들러 등록
        start_h = globals()[f"{key}_start"]
        btn_h = globals()[f"{key}_handler"]
        app.add_handler(CommandHandler("start", start_h))
        app.add_handler(CallbackQueryHandler(btn_h))

        # 매일 리포트 (UTC 09:00)
        app.job_queue.run_daily(send_daily_report, time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc))

        # Webhook 설정
        webhook_url = f"{BASE_URL}/webhook/{token}"
        try:
            await app.bot.set_webhook(url=webhook_url)
            logger.info(f"{bot_name.upper()} webhook set: {webhook_url}")
        except TimedOut:
            logger.warning(f"Webhook set timeout for {bot_name}")

        await app.initialize()
        await app.start()
        applications[key] = app

if __name__ == "__main__":
    asyncio.run(setup_bots())
    logger.info("All 4 bots are running with WEBHOOK mode!")
    flask_app.run(host="0.0.0.0", port=PORT)
