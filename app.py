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
from config import STRIPE_WEBHOOK_SECRET, RENDER_EXTERNAL_URL, ADMIN_USER_ID, LETMEBOT_TOKEN, MOREVIDS_TOKEN, ONLYTRNS_TOKEN, TSWRLDBOT_TOKEN

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ← 여기서 app을 먼저 정의해야 모든 데코레이터가 정상 동작!
app = FastAPI()

# 이제 BOT_CLASSES, applications, 그리고 모든 @app 데코레이터를 아래에 배치
BOT_CLASSES = {
    "letmebot": {"cls": LetMeBot, "token": LETMEBOT_TOKEN},
    "morevids": {"cls": MoreVidsBot, "token": MOREVIDS_TOKEN},
    "onlytrns": {"cls": OnlyTrnsBot, "token": ONLYTRNS_TOKEN},
    "tswrld": {"cls": TsWrldBot, "token": TSWRLDBOT_TOKEN},
}

applications = {}

@app.on_event("startup")
async def startup_event():
    # ... (기존 코드 그대로)

@app.get("/health")
async def health():
    return "OK"

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    # ... (기존 webhook 코드)

async def handle_payment_success(...):
    # ... (기존 함수)

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    # ... (기존 webhook 코드)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
