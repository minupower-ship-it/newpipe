# bot_core/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def language_selection_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')],
        [InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')],
    ]
    return InlineKeyboardMarkup(keyboard)


def main_menu_keyboard(texts):
    keyboard = [
        [InlineKeyboardButton(texts["plans_btn"], callback_data='plans')],
        [InlineKeyboardButton(texts["status_btn"], callback_data='status')],
        [InlineKeyboardButton(texts["help_btn"], callback_data='help')],
    ]
    return InlineKeyboardMarkup(keyboard)


def plan_selection_keyboard(texts, monthly=True, lifetime=True):
    keyboard = []
    if monthly:
        keyboard.append([InlineKeyboardButton(texts["monthly"], callback_data='select_monthly')])
    if lifetime:
        keyboard.append([InlineKeyboardButton(texts["lifetime"], callback_data='select_lifetime')])
    keyboard.append([InlineKeyboardButton(texts["back"], callback_data='back_to_main')])
    return InlineKeyboardMarkup(keyboard)


def payment_method_keyboard(texts, is_lifetime=False):
    plan_type = "lifetime" if is_lifetime else "monthly"
    keyboard = [
        [InlineKeyboardButton(texts["pay_now"], callback_data=f'pay_stripe_{plan_type}')],
        [InlineKeyboardButton(texts["back"], callback_data='plans')]
    ]
    return InlineKeyboardMarkup(keyboard)
