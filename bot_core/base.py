# bot_core/base.py
import os
import asyncio
import datetime
import stripe

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .db import add_member, log_action, get_member_status

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

stripe.api_key = STRIPE_SECRET_KEY


# 다국어 텍스트 (EN / AR / ES)
TEXTS = {
    "EN": {
        "welcome": "👋 Welcome to Premium Access Bot 👋\n\n"
                   "We're thrilled to have you join us! 🎉\n\n"
                   "Unlock exclusive content and perks in our private Telegram channel.\n\n"
                   "Choose your plan, complete payment, and get instant access via a secure invite link.\n",
        "no_sub": "😔 No active subscription found.\nChoose a plan to begin!",
        "status_title": "📊 Your Subscription Status",
        "plan": "Plan",
        "payment_date": "Payment Date",
        "expires": "Expires",
        "permanent": "Permanent access",
        "back": "⬅️ Back",
        "pay_now": "💳 Pay with Stripe",
    },
    "AR": {
        "welcome": "👋 مرحباً بك في بوت الوصول المميز 👋\n\n"
                   "نحن سعداء جدًا بانضمامك إلينا! 🎉\n\n"
                   "احصل على وصول فوري إلى محتوى حصري ومميزات خاصة في قناتنا على Telegram.\n\n"
                   "اختر خطتك، أكمل الدفع، واحصل على رابط دعوة آمن فوراً.\n",
        "no_sub": "😔 لا يوجد اشتراك نشط.\nاختر خطة للبدء!",
        "status_title": "📊 حالة اشتراكك",
        "plan": "الخطة",
        "payment_date": "تاريخ الدفع",
        "expires": "ينتهي في",
        "permanent": "وصول دائم",
        "back": "⬅️ رجوع",
        "pay_now": "💳 ادفع بـ Stripe",
    },
    "ES": {
        "welcome": "👋 ¡Bienvenido a Premium Access Bot! 👋\n\n"
                   "¡Estamos emocionados de tenerte con nosotros! 🎉\n\n"
                   "Desbloquea contenido exclusivo y beneficios en nuestro canal privado de Telegram.\n\n"
                   "Elige tu plan, completa el pago y obtén acceso instantáneo mediante un enlace seguro.\n",
        "no_sub": "😔 No se encontró suscripción activa.\n¡Elige un plan para comenzar!",
        "status_title": "📊 Estado de Tu Suscripción",
        "plan": "Plan",
        "payment_date": "Fecha de Pago",
        "expires": "Expira",
        "permanent": "Acceso permanente",
        "back": "⬅️ Atrás",
        "pay_now": "💳 Pagar con Stripe",
    }
}


def t(key, lang="EN"):
    """다국어 텍스트 반환"""
    return TEXTS.get(lang, TEXTS["EN"]).get(key, key)


async def get_user_language(user_id, default="EN"):
    """DB에서 사용자 언어 가져오기"""
    row = await get_member_status(user_id)
    return row['language'] if row and row.get('language') else default


async def create_stripe_session(user_id, price_id, mode="payment", success_url=None, cancel_url=None):
    """Stripe 결제 세션 생성"""
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode=mode,
        success_url=success_url or "https://t.me/yourbot",
        cancel_url=cancel_url or "https://t.me/yourbot",
        metadata={'user_id': user_id}
    )
    return session
