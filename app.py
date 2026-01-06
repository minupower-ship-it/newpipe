# app.py
import os
import datetime
import logging
import stripe
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.error import TimedOut
from bot_core.db import get_pool, init_db, add_member, log_action
from bot_core.utils import create_invite_link, send_daily_report
from bots.let_mebot import LetMeBot
from bots.morevids_bot import MoreVidsBot
from bots.onlytrns_bot import OnlyTrnsBot
from bots.tswrldbot import TsWrldBot
from config import STRIPE_WEBHOOK_SECRET, RENDER_EXTERNAL_URL, ADMIN_USER_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

BOT_CLASSES = {
    "letmebot": {"cls": LetMeBot, "token": LetMeBot().token},
    "morevids": {"cls": MoreVidsBot, "token": MoreVidsBot().token},
    "onlytrns": {"cls": OnlyTrnsBot, "token": OnlyTrnsBot().token},
    "tswrld": {"cls": TsWrldBot, "token": TsWrldBot().token},
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

        telegram_app.job_queue.run_daily(
            send_daily_report,
            time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc)
        )

        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{cfg['token']}"
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

@app.get("/health")
async def health():
    return "OK"

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        bot_name = session['metadata'].get('bot_name', 'unknown')
        username = session.get('customer_details', {}).get('email') or f"user_{user_id}"
        is_lifetime = session['mode'] == 'payment'
        amount_map = {
            "letmebot": 50 if is_lifetime else 20,
            "morevids": 50 if is_lifetime else 20,
            "onlytrns": 25,
            "tswrld": 21,
        }
        amount = amount_map.get(bot_name, 0)
        await handle_payment_success(user_id, username, session, is_lifetime, bot_name, amount)

    return "", 200

async def handle_payment_success(user_id, username, session, is_lifetime, bot_name, amount):
    pool = await get_pool()
    try:
        await add_member(pool, user_id, username, session.get('customer'), session.get('subscription'), is_lifetime, bot_name)
        await log_action(pool, user_id, f'payment_stripe_{"lifetime" if is_lifetime else "monthly"}', amount, bot_name)

        # 사용자에게 성공 메시지 보내기
        app_info = next((a for a in applications.values() if a["bot_instance"].bot_name == bot_name), None)
        if app_info:
            bot = app_info["app"].bot
            link, expiry = await create_invite_link(bot)
            await bot.send_message(user_id, f"🎉 Payment successful!\n\nYour invite link (expires {expiry}):\n{link}\n\nWelcome!")

        # ★★★ 추가: 관리자에게 새 Stripe 결제 알림 ★★★
        plan_type = "Lifetime" if is_lifetime else "Monthly"
        payment_date = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        expire_date = "Permanent" if is_lifetime else (datetime.datetime.utcnow() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        admin_text = (
            f"🔔 New Stripe Payment!\n\n"
            f"User ID: {user_id}\n"
            f"Username: {username}\n"
            f"Bot: {bot_name}\n"
            f"Plan: {plan_type}\n"
            f"Payment Date: {payment_date}\n"
            f"Expire Date: {expire_date}\n"
            f"Amount: ${amount}"
        )
        # ADMIN_USER_ID로 알림 전송 (config.py에 정의되어 있어야 함)
        await bot.send_message(ADMIN_USER_ID, admin_text)

    except Exception as e:
        logger.error(f"Payment handling failed for {user_id} ({bot_name}): {e}")

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    telegram_app = next((a["app"] for a in applications.values() if a["app"].bot.token == token), None)
    if not telegram_app:
        raise HTTPException(404)

    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
