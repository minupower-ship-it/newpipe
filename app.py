# app.py
import os
import asyncio
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# 각 봇의 핸들러만 import (main 함수는 사용 안 함)
from bots.let_mebot import start as letme_start, button_handler as letme_handler
from bots.onlytrns_bot import start as onlytrns_start, button_handler as onlytrns_handler
from bots.tswrldbot import start as tswrld_start, button_handler as tswrld_handler
from bots.morevids_bot import start as morevids_start, button_handler as morevids_handler

from bot_core.db import init_db

flask_app = Flask(__name__)

# 환경변수에서 도메인 가져오기 (Render 자동 제공)
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")  # 예: https://your-service.onrender.com
if not BASE_URL:
    raise ValueError("RENDER_EXTERNAL_URL 환경변수를 설정해주세요! (Render 대시보드 > Environment)")

PORT = int(os.environ.get("PORT", 10000))

# 각 봇 토큰 (config.py에서 불러온다고 가정)
BOT_CONFIG = {
    "letme":     LETMEBOT_TOKEN,       # 실제 변수명 확인하세요
    "onlytrns":  ONLYTRNS_TOKEN,
    "tswrld":    TSWRLDBOT_TOKEN,
    "morevids":  MOREVIDS_TOKEN,
}

# Application 객체 저장소
applications = {}

# Stripe 웹훅 (기존 어느 봇에서든 하나만 가져오면 됨 → 예: onlytrns_bot 기준)
# 필요시 기존 코드 복사해서 붙여넣기 (현재는 간단히 유지)
@flask_app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    # 기존에 있던 stripe webhook 코드 그대로 복사해서 쓰세요
    # (모든 봇이 같은 STRIPE_WEBHOOK_SECRET 사용한다고 가정)
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print("Stripe webhook error:", e)
        return abort(400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        # 공통 add_member, log_action 호출
        asyncio.run(add_member(user_id, "stripe_user", session.get('customer'), session.get('subscription'), True))
        asyncio.run(log_action(user_id, 'payment_stripe_webhook', 0))

    return '', 200

# Telegram Webhook 공통 엔드포인트
@flask_app.route('/webhook/<token>', methods=['POST'])
def telegram_webhook(token):
    if token not in BOT_CONFIG.values():
        return abort(404)

    # 해당 토큰의 app 찾아서 업데이트 처리
    for app in applications.values():
        if app.bot.token == token:
            try:
                update = Update.de_json(request.get_json(force=True), app.bot)
                asyncio.run(app.process_update(update))
            except Exception as e:
                print(f"Error processing update for {token}: {e}")
            return 'OK'

    return abort(404)

# 각 봇 webhook 설정 + 핸들러 등록
async def setup_bots():
    await init_db()

    for name, token in BOT_CONFIG.items():
        app = Application.builder().token(token).build()

        # 핸들러 등록 (각 봇별)
        if name == "letme":
            app.add_handler(CommandHandler("start", letme_start))
            app.add_handler(CallbackQueryHandler(letme_handler))
        elif name == "onlytrns":
            app.add_handler(CommandHandler("start", onlytrns_start))
            app.add_handler(CallbackQueryHandler(onlytrns_handler))
        elif name == "tswrld":
            app.add_handler(CommandHandler("start", tswrld_start))
            app.add_handler(CallbackQueryHandler(tswrld_handler))
        elif name == "morevids":
            app.add_handler(CommandHandler("start", morevids_start))
            app.add_handler(CallbackQueryHandler(morevids_handler))

        # Webhook URL 설정
        webhook_url = f"{BASE_URL}/webhook/{token}"
        await app.bot.set_webhook(url=webhook_url)
        print(f"{name.upper()} BOT webhook set → {webhook_url}")

        applications[name] = app
        await app.initialize()
        await app.start()

# 메인 실행
if __name__ == "__main__":
    # 비동기 설정 실행
    asyncio.run(setup_bots())

    print("All 4 bots are running with WEBHOOK mode on one service!")
    print("Stripe webhook: /webhook/stripe")
    print(f"Server starting on port {PORT}...")

    # Flask 실행 (blocking)
    flask_app.run(host="0.0.0.0", port=PORT)
