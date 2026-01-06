# config.py
import os

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Telegram Bots - Tokens
LETMEBOT_TOKEN = os.getenv("LETMEBOT_TOKEN")
ONLYTRNS_TOKEN = os.getenv("ONLYTRNS_TOKEN")
TSWRLDBOT_TOKEN = os.getenv("TSWRLDBOT_TOKEN")
MOREVIDS_TOKEN = os.getenv("MOREVIDS_TOKEN")

# Telegram Bots - Stripe Price IDs
LETMEBOT_PRICE_MONTHLY = os.getenv("LETMEBOT_PRICE_MONTHLY")
LETMEBOT_PRICE_LIFETIME = os.getenv("LETMEBOT_PRICE_LIFETIME")

ONLYTRNS_PRICE_LIFETIME = os.getenv("ONLYTRNS_PRICE_LIFETIME")

TSWRLDBOT_PRICE_LIFETIME = os.getenv("TSWRLDBOT_PRICE_LIFETIME")

MOREVIDS_PRICE_MONTHLY = os.getenv("MOREVIDS_PRICE_MONTHLY")
MOREVIDS_PRICE_LIFETIME = os.getenv("MOREVIDS_PRICE_LIFETIME")

# Portal Return URLs (결제 후 리턴 URL - 각 봇의 t.me 링크 추천)
LETMEBOT_PORTAL_RETURN_URL = os.getenv("LETMEBOT_PORTAL_RETURN_URL", "https://t.me/your_letmebot")
ONLYTRNS_PORTAL_RETURN_URL = os.getenv("ONLYTRNS_PORTAL_RETURN_URL", "https://t.me/your_onlytrnsbot")
TSWRLDBOT_PORTAL_RETURN_URL = os.getenv("TSWRLDBOT_PORTAL_RETURN_URL", "https://t.me/your_tswrldbot")
MOREVIDS_PORTAL_RETURN_URL = os.getenv("MOREVIDS_PORTAL_RETURN_URL", "https://t.me/your_morevidsbot")

# 필수 추가 변수 (오류 해결 + 기능 작동용)
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")          # 관리자 Telegram ID (숫자만, 예: 123456789)
CHANNEL_ID = os.getenv("CHANNEL_ID")                # 프라이빗 채널 ID (예: -1001234567890)

# 선택적 (Render webhook 자동 설정용)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")  # 예: https://your-service.onrender.com
