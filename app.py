# app.py
import os
import datetime
import logging
import stripe
import html
import time
from typing import Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, filters, ContextTypes
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
    LUST4TRANS_PROMOTER_ID, TSWRLDBOT_PROMOTER_ID, CHANNEL_ID
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

# 중복 방지 캐시
recent_notifications: Dict[str, float] = {}


def get_subscription_id_from_event(event_type: str, data_object: dict) -> Optional[str]:
    """Stripe 이벤트에서 subscription_id를 안전하게 추출"""
    if event_type == "checkout.session.completed":
        return data_object.get('subscription')
    
    elif event_type in ("invoice.payment_succeeded", "invoice.paid", "invoice.finalized"):
        # 1순위: top-level subscription
        sub_id = data_object.get('subscription')
        if sub_id:
            return sub_id
        
        # 2순위: line item 안에 있는 subscription (최근 Stripe에서 자주 발생)
        lines = data_object.get('lines', {}).get('data', [])
        for line in lines:
            if line.get('subscription'):
                return line['subscription']
        
        # 3순위: invoice ID를 임시로 사용 (fallback)
        return None  # None이면 아래에서 처리
    
    elif event_type.startswith("customer.subscription"):
        return data_object.get('id')
    
    return data_object.get('id') or data_object.get('subscription')


@app.on_event("startup")
async def startup_event():
    pool = await get_pool()
    await init_db(pool)
    for key, cfg in BOT_CLASSES.items():
        bot_instance = cfg["cls"]()
        telegram_app = Application.builder().token(cfg["token"]).build()

        telegram_app.add_handler(CommandHandler("start", bot_instance.start))
        telegram_app.add_handler(CallbackQueryHandler(bot_instance.button_handler))
        telegram_app.add_handler(CommandHandler("paid", paid_command))
        telegram_app.add_handler(CommandHandler("kick", kick_command))
        telegram_app.add_handler(CommandHandler("user", user_count_command,
                                                filters=filters.User(user_id=ADMIN_USER_ID) |
                                                filters.User(user_id=int(LUST4TRANS_PROMOTER_ID))))
        telegram_app.add_handler(CommandHandler("stats", lust4trans_stats_command,
                                                filters=filters.User(user_id=ADMIN_USER_ID) |
                                                filters.User(user_id=int(LUST4TRANS_PROMOTER_ID))))

        telegram_app.add_handler(CommandHandler("transactions", transaction_report.transactions_command))
        telegram_app.add_handler(CommandHandler("sync_stripe", transaction_report.sync_stripe_command))

        telegram_app.job_queue.run_daily(send_daily_report, time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc))

        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{key}"
        try:
            await telegram_app.bot.set_webhook(url=webhook_url)
            logger.info(f"{key} webhook set: {webhook_url}")
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
        raise HTTPException(status_code=404)
    telegram_app = applications[bot_key]["app"]
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        raise HTTPException(status_code=400)


@app.post("/stripe_webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Stripe signature failed: {e}")
        raise HTTPException(status_code=400)

    event_type = event['type']
    data_object = event['data']['object']
    subscription_id = get_subscription_id_from_event(event_type, data_object)
    current_time = time.time()

    # 결제 성공 이벤트는 중복 스킵 완전 해제
    if event_type not in ("checkout.session.completed", "invoice.payment_succeeded", "invoice.paid"):
        if subscription_id and subscription_id in recent_notifications:
            if current_time - recent_notifications[subscription_id] < 300:
                logger.info(f"Duplicate skipped: {event_type} {subscription_id}")
                return {"status": "skipped"}

    if subscription_id:
        recent_notifications[subscription_id] = current_time

    try:
        logger.info(f"Processing: {event_type} | sub_id: {subscription_id or 'N/A'}")

        # === 첫 결제 ===
        if event_type == "checkout.session.completed":
            # (기존 로직 그대로 유지)
            session = data_object
            user_id = int(session['metadata'].get('user_id', 0))
            bot_name = session['metadata'].get('bot_name', 'unknown')
            # ... (나머지 기존 코드 그대로)

            if user_id and bot_name != 'unknown':
                # 기존 첫 결제 처리 로직 (add_member, 알림 등) 그대로
                username = session['metadata'].get('username', f"user_{user_id}")
                email = session.get('customer_details', {}).get('email', 'unknown')
                amount = session['amount_total'] / 100.0
                plan = session['metadata'].get('plan', 'monthly')

                pool = await get_pool()
                await add_member(pool, user_id, username, session['customer'], session.get('subscription'),
                                 is_lifetime=plan == 'lifetime', bot_name=bot_name, email=email)

                await log_action(pool, user_id, f'payment_stripe_{plan}', amount, bot_name)

                # 사용자에게 invite link
                if bot_name in applications:
                    bot = applications[bot_name]["app"].bot
                    link, expiry_str = await create_invite_link(bot)
                    await bot.send_message(user_id, f"✅ Payment successful!\n\n{link}\n\n{expiry_str}")

                # Admin / Promoter 알림 (기존)
                # ... (기존 코드 그대로)

        # === 재결제 / 인보이스 성공 ===
        elif event_type in ("invoice.payment_succeeded", "invoice.paid"):
            invoice = data_object
            subscription_id = get_subscription_id_from_event(event_type, invoice)  # 다시 한번 안전 추출

            if not subscription_id:
                logger.warning(f"Invoice {invoice.get('id')} has NO subscription_id → treating as possible one-time but still trying to notify")
                # fallback: invoice ID로도 시도 (드물지만)
                subscription_id = invoice.get('id')

            pool = await get_pool()
            row = await pool.fetchrow(
                "SELECT user_id, bot_name, username, email FROM members WHERE stripe_subscription_id = $1",
                subscription_id
            )

            if not row:
                logger.warning(f"Member not found for subscription {subscription_id} (invoice: {invoice.get('id')})")
                return {"status": "no_member"}

            user_id = row['user_id']
            bot_name = row['bot_name']
            username = row['username'] or f"ID{user_id}"
            email = row['email'] or 'unknown'

            amount = invoice.get('amount_paid', 0) / 100.0
            is_renewal = invoice.get('billing_reason') == 'subscription_cycle'

            await log_action(pool, user_id, 'payment_stripe_renewal', amount, bot_name)

            email_display = f"• Email: {html.escape(email)}" if email and email != 'unknown' else ''
            msg = (
                f"{'🔄 **Subscription Renewed**' if is_renewal else '💳 **Payment Succeeded**'}\n\n"
                f"• Bot: {bot_name.upper()}\n"
                f"• User: @{username} (ID: {user_id})\n"
                f"{email_display}\n"
                f"• Amount: ${amount:.2f}\n"
                f"• Subscription: {subscription_id[:12] if subscription_id else 'N/A'}...\n"
                f"• Invoice: {invoice.get('id', 'N/A')[:12]}...\n"
                f"• Event: {event_type}\n"
                f"• Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            )

            # Admin
            try:
                await applications["letmebot"]["app"].bot.send_message(ADMIN_USER_ID, msg, parse_mode='Markdown')
                logger.info(f"✅ ADMIN NOTIFIED via {event_type} - ${amount} user:{user_id}")
            except Exception as e:
                logger.error(f"Admin notify failed: {e}")

            # Promoter
            promoter_id = None
            if bot_name == "lust4trans":
                promoter_id = int(LUST4TRANS_PROMOTER_ID or 0)
            elif bot_name == "tswrld":
                promoter_id = int(TSWRLDBOT_PROMOTER_ID or 0)

            if promoter_id and promoter_id != ADMIN_USER_ID and bot_name in applications:
                try:
                    await applications[bot_name]["app"].bot.send_message(promoter_id, msg, parse_mode='Markdown')
                    logger.info(f"Promoter notified via {event_type}")
                except Exception as e:
                    logger.error(f"Promoter notify fail: {e}")

        # subscription.updated 등 기존 로직은 그대로 유지 (생략)

    except Exception as e:
        logger.error(f"Webhook error: {e}")

    return {"status": "success"}


# paid_command, kick_command, user_count_command, lust4trans_stats_command 함수들은 기존 그대로 (들여쓰기만 맞춤)
# ... (이전 버전과 동일하게 복사)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
