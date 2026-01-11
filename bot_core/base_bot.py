import datetime
import logging
import stripe
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_core.db import get_pool, log_action, get_member_status, add_member
from bot_core.texts import get_text
from bot_core.keyboards import main_menu_keyboard, plans_keyboard, payment_keyboard
from config import STRIPE_SECRET_KEY, CRYPTO_ADDRESS, CRYPTO_QR_URL, PLAN_PRICES

stripe.api_key = STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class BaseBot:
    def __init__(self, bot_name, token, price_monthly=None, price_lifetime=None, price_weekly=None, welcome_video=None, paypal_monthly=None, paypal_lifetime=None, paypal_weekly=None, has_monthly=True, has_lifetime=True, has_weekly=False, portal_return_url=None):
        self.bot_name = bot_name
        self.token = token
        self.price_monthly = price_monthly
        self.price_lifetime = price_lifetime
        self.price_weekly = price_weekly
        self.welcome_video = welcome_video
        self.paypal_monthly = paypal_monthly
        self.paypal_lifetime = paypal_lifetime
        self.paypal_weekly = paypal_weekly
        self.has_monthly = has_monthly
        self.has_lifetime = has_lifetime
        self.has_weekly = has_weekly
        self.portal_return_url = portal_return_url

    async def get_user_language(self, user_id):
        pool = await get_pool()
        row = await get_member_status(pool, user_id, self.bot_name)
        return row.get('language', "EN") if row else "EN"

    async def set_user_language(self, user_id, lang):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO members (user_id, language, bot_name) VALUES ($1, $2, $3) ON CONFLICT (user_id, bot_name) DO UPDATE SET language=$2',
                user_id, lang, self.bot_name
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pool = await get_pool()
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"  # username None 방지
        await log_action(pool, user_id, 'start', bot_name=self.bot_name)
        lang = await self.get_user_language(user_id)

        if lang == "EN":
            keyboard = [
                [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
                [InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')],
                [InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]
            ]
            await update.message.reply_text(
                "🌍 Please select your preferred language:\n\n"
                "🇬🇧 English\n"
                "🇸🇦 العربية\n"
                "🇪🇸 Español",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await self.send_welcome_and_menu(update, context, lang)

    async def send_welcome_and_menu(self, update_or_query, context, lang):
        chat_id = update_or_query.message.chat_id if hasattr(update_or_query, 'message') else update_or_query.callback_query.message.chat_id
        if self.welcome_video:
            try:
                await context.bot.send_video(chat_id=chat_id, video=self.welcome_video)
            except Exception as e:
                logger.error(f"Failed to send video for {self.bot_name}: {e}")
        today = datetime.datetime.utcnow().strftime("%b %d")
        text = get_text(self.bot_name, lang) + f"\n\n📅 {today} — System Active\n⚡️ Instant Access — Ready"
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown', reply_markup=main_menu_keyboard(lang))

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        lang = await self.get_user_language(user_id)

        if query.data.startswith('lang_'):
            new_lang = query.data.split('_')[1].upper()
            await self.set_user_language(user_id, new_lang)
            await query.edit_message_text(f"✅ Language changed to {new_lang}!")
            await self.send_welcome_and_menu(query, context, new_lang)
            return

        if query.data == 'change_language':
            keyboard = [
                [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
                [InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')],
                [InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]
            ]
            await query.edit_message_text(
                "🌍 Change your preferred language:\n\nSelect below 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        if query.data == 'plans':
            prices = PLAN_PRICES.get(self.bot_name, {'weekly': 'N/A', 'monthly': 'N/A', 'lifetime': 'N/A'})
            text = "Choose Your Plan\n\n"
            if self.has_weekly:
                text += f"• Weekly: {prices['weekly']}/week\n"
            if self.has_monthly:
                text += f"• Monthly: {prices['monthly']}/month\n"
            if self.has_lifetime:
                text += f"• Lifetime: {prices['lifetime']} (one-time)\n"
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=plans_keyboard(lang, monthly=self.has_monthly, lifetime=self.has_lifetime, weekly=self.has_weekly))
            return

        if query.data == 'status':
            pool = await get_pool()
            row = await get_member_status(pool, user_id, self.bot_name)
            if row:
                is_lifetime = row['is_lifetime']
                subscription_id = row['stripe_subscription_id']
                expiry = row['expiry']
                created_at = row['created_at']
                if is_lifetime:
                    plan_name = 'Lifetime'
                elif subscription_id:
                    plan_name = 'Monthly'
                else:
                    plan_name = 'Weekly'
                expiry_text = "Expiry: Permanent" if is_lifetime else f"Expiry: {expiry.strftime('%Y-%m-%d')}" if expiry else "N/A"
                payment_date = created_at.strftime('%Y-%m-%d') if created_at else "N/A"
                
                text = (
                    "📊 Your Subscription Status\n\n"
                    f"• Plan: {plan_name}\n"
                    f"• Payment Date: {payment_date}\n"
                    f"• {expiry_text}"
                )
            else:
                text = "😔 No active subscription found.\nChoose a plan to begin!"
            
            await query.edit_message_text(text, parse_mode='Markdown')
            return

        if query.data == 'help':
            text = (
                "❓ Help & Support\n\n"
                "• Payment or access issues?\n"
                "• Contact support directly:\n\n"
                "👉 @mbrypie"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Contact Support", url="https://t.me/mbrypie")]
            ])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
            return

        if query.data == 'select_weekly' and self.has_weekly:
            keyboard = payment_keyboard(lang, 'weekly')
            await query.edit_message_text("💳 Select Payment Method for Weekly", parse_mode='Markdown', reply_markup=keyboard)
            return

        if query.data == 'select_monthly' and self.has_monthly:
            keyboard = payment_keyboard(lang, 'monthly')
            await query.edit_message_text("💳 Select Payment Method for Monthly", parse_mode='Markdown', reply_markup=keyboard)
            return

        if query.data == 'select_lifetime' and self.has_lifetime:
            keyboard = payment_keyboard(lang, 'lifetime')
            await query.edit_message_text("💳 Select Payment Method for Lifetime", parse_mode='Markdown', reply_markup=keyboard)
            return

        if query.data.startswith('pay_paypal_'):
            plan = query.data.split('_')[2]
            paypal_link = self.paypal_weekly if plan == 'weekly' else self.paypal_monthly if plan == 'monthly' else self.paypal_lifetime
            if paypal_link:
                buttons = [
                    [InlineKeyboardButton("Pay Now", url=paypal_link)],
                    [InlineKeyboardButton("Send proof here", url="https://t.me/mbrypie")]
                ]
                await query.edit_message_text(
                    f"💲 Pay via PayPal ({plan.capitalize()})",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ PayPal not available for this plan.")
            return

        if query.data.startswith('pay_crypto_'):
            if CRYPTO_ADDRESS and CRYPTO_QR_URL:
                text = f"💎 Pay via Crypto\n\nAddress: `{CRYPTO_ADDRESS}`"
                buttons = [
                    [InlineKeyboardButton("QR Code", url=CRYPTO_QR_URL)],
                    [InlineKeyboardButton("Send proof here", url="https://t.me/mbrypie")]
                ]
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ Crypto payment not configured.")
            return

        if query.data.startswith('pay_stripe_'):
            plan = query.data.split('_')[2]
            price_id = self.price_weekly if plan == 'weekly' else self.price_monthly if plan == 'monthly' else self.price_lifetime
            mode = 'subscription' if plan == 'monthly' else 'payment'
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{'price': price_id, 'quantity': 1}],
                    mode=mode,
                    success_url=self.portal_return_url,
                    cancel_url=self.portal_return_url,
                    metadata={'user_id': user_id, 'bot_name': self.bot_name, 'plan': plan}
                )
                buttons = [
                    [InlineKeyboardButton("💳 Pay Now", url=session.url)],
                    [InlineKeyboardButton("Help", url="https://t.me/mbrypie")]
                ]
                await query.edit_message_text(
                    f"🔒 Redirecting to secure Stripe checkout ({plan.capitalize()})...",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception as e:
                logger.error(f"Stripe session creation failed for {self.bot_name}: {e}")
                await query.edit_message_text("❌ Payment error. Please try again or contact support.")
            return

        if query.data == 'back_to_main':
            await query.edit_message_text("Back to main menu", reply_markup=main_menu_keyboard(lang))
            return
