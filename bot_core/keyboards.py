from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def language_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')],
        [InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]
    ])

def main_menu_keyboard(texts):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(texts["plans_btn"], callback_data='plans')],
        [InlineKeyboardButton(texts["status_btn"], callback_data='status')],
        [InlineKeyboardButton(texts["help_btn"], callback_data='help')]
    ])

