# app.py
import os
import asyncio
import threading

from bots import let_mebot, onlytrns_bot, tswrldbot, morevids_bot
from flask import Flask

# Flask 메인 앱 (공통)
flask_app = Flask(__name__)

# Render 포트
PORT = int(os.getenv("PORT", 10000))

# 각 봇 메인 루프 실행
def run_bot(bot_main):
    asyncio.run(bot_main.main())

# 봇 실행
if __name__ == "__main__":
    # 1️⃣ Flask 앱은 공통으로 쓰고, 각 봇의 웹훅도 Flask에 등록됨
    # 2️⃣ 각 봇은 별도 스레드에서 실행
    bots = [let_mebot, onlytrns_bot, tswrldbot, morevids_bot]

    for bot in bots:
        t = threading.Thread(target=run_bot, args=(bot,))
        t.start()

    # 3️⃣ Flask 앱 실행
    flask_app.run(host="0.0.0.0", port=PORT)

