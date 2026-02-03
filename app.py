# app.py
import os
import datetime
import logging
import stripe
from fastapi import FastAPI, Request, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut
from bot_core.db import get_pool, init_db, add_member, log_action
from bot_core.utils import create_invite_link, send_daily_report
from bots.let_mebot import LetMeBot
from bots.morevids_bot import MoreVidsBot
from bots.onlytrns_bot import OnlyTrnsBot
from bots.tswrldbot import TsWrldBot
from bots.lust4trans_bot import Lust4transBot
from config import (
    STRIPE_WEBHOOK_SECRET, RENDER_EXTERNAL_URL, ADMIN_USER_ID,
    LETMEBOT_TOKEN, MOREVIDS_TOKEN, ONLYTRNS_TOKEN, TSWRLDBOT_TOKEN, LUST4TRANS_TOKEN,
    LUST4TRANS_PROMOTER_ID
)

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

        # /kick 명령어 - 제한 제거
        telegram_app.add_handler(CommandHandler("kick", kick_command))

        # /user 명령어 (홍보자 전용 유지)
        telegram_app.add_handler(CommandHandler("user", user_count_command, filters=filters.User(user_id=int(LUST4TRANS_PROMOTER_ID))))

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

    logger.info(f"Registered applications keys: {list(applications.keys())}")

@app.get("/health")
async def health():
    return "OK"

@app.post("/webhook/stripe")
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

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        bot_name = session['metadata'].get('bot_name', 'unknown')
        plan = session['metadata'].get('plan', 'unknown')
        username = session['metadata'].get('username', f"user_{user_id}")
        email = session.get('customer_details', {}).get('email') or 'unknown'
        now = datetime.datetime.utcnow()
        if plan == 'lifetime':
            is_lifetime = True
            expiry = None
        else:
            is_lifetime = False
            expiry = now + datetime.timedelta(
                days=30 if plan == 'monthly' else 7 if plan == 'weekly' else 0
            )
        amount_map = {
            "letmebot": {"weekly": 10, "monthly": 20, "lifetime": 50},
            "morevids": {"weekly": 10, "monthly": 20, "lifetime": 50},
            "onlytrns": {"lifetime": 25},
            "tswrld": {"lifetime": 21},
            "lust4trans": {"weekly": 11, "monthly": 21, "lifetime": 52},
        }
        amount = amount_map.get(bot_name, {}).get(plan, 0)
        await handle_payment_success(
            user_id, username, session, is_lifetime, expiry, bot_name, plan, amount, email
        )

    return "", 200

async def handle_payment_success(user_id, username, session, is_lifetime, expiry, bot_name, plan, amount, email):
    pool = await get_pool()
    try:
        await add_member(
            pool, user_id, username,
            session.get('customer'), session.get('subscription'),
            is_lifetime, expiry, bot_name,
            email=email
        )
        await log_action(pool, user_id, f'payment_stripe_{plan}', amount, bot_name)

        app_info = next(
            (a for a in applications.values() if a["bot_instance"].bot_name == bot_name),
            None
        )
        if app_info:
            bot = app_info["app"].bot
            link, expiry_str = await create_invite_link(bot)
            await bot.send_message(
                user_id,
                f"🎉 Payment successful!\n\nYour invite link (expires {expiry_str}):\n{link}\n\nWelcome!"
            )

        plan_type = plan.capitalize()
        payment_date = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        expire_date = "Permanent" if is_lifetime else (expiry.strftime('%Y-%m-%d') if expiry else "N/A")
        admin_text = (
            f"🔔 New Stripe Payment!\n\n"
            f"User ID: {user_id}\n"
            f"Username: @{username.lstrip('@') if username.startswith('@') else username}\n"
            f"Email: {email}\n"
            f"Bot: {bot_name}\n"
            f"Plan: {plan_type}\n"
            f"Payment Date: {payment_date}\n"
            f"Expire Date: {expire_date}\n"
            f"Amount: ${amount}"
        )

        letme_app = applications.get("letmebot")
        if letme_app:
            bot = letme_app["app"].bot
            await bot.send_message(ADMIN_USER_ID, admin_text)

        # lust4trans 결제 시 홍보자에게도 알림 보내기
        if bot_name == "lust4trans":
            promoter_id = LUST4TRANS_PROMOTER_ID
            if promoter_id:
                promoter_text = (
                    f"🔔 Lust4trans 새 결제!\n\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{username.lstrip('@') if username.startswith('@') else username}\n"
                    f"Plan: {plan_type}\n"
                    f"Amount: ${amount}\n"
                    f"Date: {payment_date}"
                )
                try:
                    await bot.send_message(promoter_id, promoter_text)
                    logger.info(f"Promoter 알림 전송 성공: {promoter_id}")
                except Exception as e:
                    logger.error(f"Promoter 알림 실패: {e}")

    except Exception as e:
        logger.error(f"Payment handling failed for {user_id} ({bot_name}): {e}")

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    telegram_app = next(
        (a["app"] for a in applications.values() if a["app"].bot.token == token),
        None
    )
    if not telegram_app:
        raise HTTPException(404)

    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

async def paid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/paid 명령어 입력 감지 - user_id: {update.effective_user.id}, args: {context.args}")
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /paid [user_id] [plan]\nExample: /paid 123456789 weekly")
        return

    try:
        user_id = int(args[0])
        plan = args[1].lower()

        if plan not in ['weekly', 'monthly']:
            await update.message.reply_text("Plan must be weekly or monthly.")
            return

        pool = await get_pool()

        days = 7 if plan == 'weekly' else 30
        kick_at = datetime.datetime.utcnow() + datetime.timedelta(days=days)

        async with pool.acquire() as conn:
            await conn.execute(
                'UPDATE members SET kick_scheduled_at = $1 WHERE user_id = $2 AND active = TRUE',
                kick_at, user_id
            )

        await update.message.reply_text(
            f"✅ /paid processed!\n"
            f"User ID: {user_id}\n"
            f"Plan: {plan}\n"
            f"Scheduled kick: {kick_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Notification 1 day before will be sent automatically."
        )

    except Exception as e:
        logger.error(f"/paid error: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/kick 명령어 입력 감지 - user_id: {update.effective_user.id}, args: {context.args}")
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /kick [user_id]\nExample: /kick 123456789")
        return

    try:
        user_id = int(args[0])

        pool = await get_pool()

        # 해당 user_id의 모든 활성 구독 찾아서 처리
        rows = await pool.fetch
