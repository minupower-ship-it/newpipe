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
    """Stripe 이벤트에서 subscription_id를 가장 안전하게 추출"""
    if event_type == "checkout.session.completed":
        return data_object.get('subscription')

    # invoice 관련 이벤트 (가장 중요한 부분)
    if event_type in ("invoice.payment_succeeded", "invoice.paid", "invoice.finalized"):
        # 1순위: top-level
        if data_object.get('subscription'):
            return data_object['subscription']
        # 2순위: lines.data 안에 있는 subscription (최근 Stripe에서 자주 발생)
        lines = data_object.get('lines', {}).get('data', [])
        for line in lines:
            if line.get('subscription'):
                return line['subscription']
        # 3순위: invoice ID를 fallback으로 사용
        return data_object.get('id')

    if event_type.startswith("customer.subscription"):
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
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Stripe signature verification failed: {e}")
        raise HTTPException(status_code=400)

    event_type = event['type']
    data_object = event['data']['object']
    subscription_id = get_subscription_id_from_event(event_type, data_object)
    current_time = time.time()

    # 결제 성공 이벤트는 중복 스킵 완전 제외
    if event_type not in ("checkout.session.completed", "invoice.payment_succeeded", "invoice.paid"):
        if subscription_id and subscription_id in recent_notifications:
            if current_time - recent_notifications[subscription_id] < 300:
                logger.info(f"Skipping duplicate: {event_type} {subscription_id}")
                return {"status": "skipped_duplicate"}

    if subscription_id:
        recent_notifications[subscription_id] = current_time

    try:
        logger.info(f"Processing: {event_type} | sub_id: {subscription_id or 'N/A'}")

        # 첫 결제
        if event_type == "checkout.session.completed":
            session = data_object
            user_id = int(session['metadata'].get('user_id', 0))
            bot_name = session['metadata'].get('bot_name', 'unknown')
            plan = session['metadata'].get('plan', 'monthly')
            sub_id = session.get('subscription')
            customer_id = session['customer']
            amount = session['amount_total'] / 100.0

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
                    pool, user_id, username, customer_id, sub_id,
                    is_lifetime=is_lifetime, expiry=expiry, bot_name=bot_name, email=email
                )
                await log_action(pool, user_id, f'payment_stripe_{plan}', amount, bot_name)

                if bot_name in applications:
                    bot = applications[bot_name]["app"].bot
                    link, expiry_str = await create_invite_link(bot)
                    await bot.send_message(
                        user_id,
                        f"✅ Payment successful!\n\nYour invite link (expires in 5 min):\n{link}\n\n{expiry_str}"
                    )

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

                try:
                    await applications["letmebot"]["app"].bot.send_message(ADMIN_USER_ID, msg, parse_mode='Markdown')
                    logger.info(f"Admin notified - New Subscription - user:{user_id}")
                except Exception as e:
                    logger.error(f"Admin notify failed: {e}")

                promoter_id = None
                if bot_name == "lust4trans":
                    promoter_id = int(LUST4TRANS_PROMOTER_ID or 0)
                elif bot_name == "tswrld":
                    promoter_id = int(TSWRLDBOT_PROMOTER_ID or 0)

                if promoter_id and promoter_id != ADMIN_USER_ID and bot_name in applications:
                    try:
                        await applications[bot_name]["app"].bot.send_message(promoter_id, msg, parse_mode='Markdown')
                    except Exception as e:
                        logger.error(f"Promoter notify fail: {e}")

        # 재결제 (이번 문제의 핵심)
        elif event_type in ("invoice.payment_succeeded", "invoice.paid"):
            invoice = data_object
            subscription_id = get_subscription_id_from_event(event_type, invoice)

            if not subscription_id:
                logger.warning(f"Invoice {invoice.get('id')} has no subscription_id - using invoice id as fallback")
                subscription_id = invoice.get('id')

            pool = await get_pool()
            row = await pool.fetchrow(
                "SELECT user_id, bot_name, username, email FROM members WHERE stripe_subscription_id = $1",
                subscription_id
            )

            if not row:
                logger.warning(f"Member not found for {subscription_id} (invoice: {invoice.get('id')})")
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
                f"• Subscription: {str(subscription_id)[:12]}...\n"
                f"• Invoice: {invoice.get('id', 'N/A')[:12]}...\n"
                f"• Event: {event_type}\n"
                f"• Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            )

            try:
                await applications["letmebot"]["app"].bot.send_message(ADMIN_USER_ID, msg, parse_mode='Markdown')
                logger.info(f"✅ ADMIN NOTIFIED via {event_type} - ${amount} user:{user_id}")
            except Exception as e:
                logger.error(f"Admin notify failed: {e}")

            promoter_id = None
            if bot_name == "lust4trans":
                promoter_id = int(LUST4TRANS_PROMOTER_ID or 0)
            elif bot_name == "tswrld":
                promoter_id = int(TSWRLDBOT_PROMOTER_ID or 0)

            if promoter_id and promoter_id != ADMIN_USER_ID and bot_name in applications:
                try:
                    await applications[bot_name]["app"].bot.send_message(promoter_id, msg, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Promoter notify fail: {e}")

        elif event_type == "customer.subscription.updated":
            # 기존 로직 (중요 변경만 알림)
            subscription = data_object
            subscription_id = subscription.get('id')
            if subscription_id:
                previous_attrs = event.get('previous_attributes', {})
                changed_keys = set(previous_attrs.keys())
                significant_changes = {'items', 'current_period_end', 'current_period_start', 'status', 'cancel_at'}
                if not changed_keys or not (changed_keys & significant_changes):
                    logger.info(f"Skipping minor update for {subscription_id}")
                    return {"status": "skipped_minor"}

                # ... (기존 subscription.updated 로직 그대로)

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"status": "success"}


async def paid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("Admin only command.")
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /paid <user_id> <bot_name>")
            return

        target_user_id = int(args[0])
        bot_name = args[1] if len(args) > 1 else 'letmebot'

        pool = await get_pool()
        await pool.execute(
            'UPDATE members SET active = TRUE WHERE user_id = $1 AND bot_name = $2',
            target_user_id, bot_name
        )
        await update.message.reply_text(f"User {target_user_id} paid status updated for {bot_name}.")
    except Exception as e:
        logger.error(f"/paid error: {e}")
        await update.message.reply_text(f"Error: {str(e)}")


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("Admin only command.")
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /kick <user_id>")
            return

        target_user_id = int(args[0])

        kicked = False
        for key in applications.keys():
            bot = applications[key]["app"].bot
            try:
                await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=target_user_id)
                logger.info(f"Kick success - User {target_user_id} from {key}")
                kicked = True
            except Exception as e:
                logger.error(f"Kick failed - User {target_user_id} from {key}: {e}")

        pool = await get_pool()
        rows = await pool.fetch(
            'SELECT bot_name FROM members WHERE user_id = $1 AND active = TRUE',
            target_user_id
        )

        if rows:
            async with pool.acquire() as conn:
                for row in rows:
                    await conn.execute(
                        'UPDATE members SET active = FALSE WHERE user_id = $1 AND bot_name = $2',
                        target_user_id, row['bot_name']
                    )

        if kicked:
            await update.message.reply_text(f"✅ 강제 Kick 완료! User ID: {target_user_id}")
        else:
            await update.message.reply_text(f"User ID {target_user_id} kick 실패.")

    except Exception as e:
        logger.error(f"/kick error: {e}")
        await update.message.reply_text(f"Error: {str(e)}")


async def user_count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_ids = [ADMIN_USER_ID, int(LUST4TRANS_PROMOTER_ID)]
    if user_id not in allowed_ids:
        await update.message.reply_text("This command is for admin or Lust4trans promoter only.")
        return

    pool = await get_pool()
    today = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    count = await pool.fetchval(
        '''
        SELECT COUNT(DISTINCT user_id) 
        FROM daily_logs 
        WHERE bot_name = 'lust4trans' AND timestamp >= $1
        ''',
        today
    )

    await update.message.reply_text(f"Today's unique users on Lust4trans: **{count or 0}**")


async def lust4trans_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_ids = [ADMIN_USER_ID, int(LUST4TRANS_PROMOTER_ID)]
    if user_id not in allowed_ids:
        await update.message.reply_text("This command is for admin or Lust4trans promoter only.")
        return

    pool = await get_pool()

    weekly_count = await pool.fetchval(
        "SELECT COUNT(DISTINCT user_id) FROM daily_logs WHERE bot_name = 'lust4trans' AND action = 'payment_stripe_weekly'"
    )
    monthly_count = await pool.fetchval(
        "SELECT COUNT(DISTINCT user_id) FROM daily_logs WHERE bot_name = 'lust4trans' AND action = 'payment_stripe_monthly'"
    )
    lifetime_count = await pool.fetchval(
        "SELECT COUNT(DISTINCT user_id) FROM daily_logs WHERE bot_name = 'lust4trans' AND action = 'payment_stripe_lifetime'"
    )

    total_count = (weekly_count or 0) + (monthly_count or 0) + (lifetime_count or 0)
    total_amount = (weekly_count or 0) * 11 + (monthly_count or 0) * 21 + (lifetime_count or 0) * 52

    await update.message.reply_text(
        f"Lust4trans Stripe 결제 누적\n\n"
        f"Weekly: {weekly_count or 0}명 (${(weekly_count or 0) * 11})\n"
        f"Monthly: {monthly_count or 0}명 (${(monthly_count or 0) * 21})\n"
        f"Lifetime: {lifetime_count or 0}명 (${(lifetime_count or 0) * 52})\n\n"
        f"총: {total_count}명 (${total_amount})"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
