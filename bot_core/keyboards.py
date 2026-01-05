from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard(lang="EN"):
    """메인 메뉴 버튼 (plans / status / help)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 View Plans", callback_data='plans')],
        [InlineKeyboardButton("📊 My Subscription", callback_data='status')],
        [InlineKeyboardButton("❓ Help & Support", callback_data='help')]
    ])

def plans_keyboard(lang="EN", monthly=True, lifetime=True):
    """플랜 선택 버튼"""
    buttons = []
    if monthly:
        buttons.append([InlineKeyboardButton("🔄 Monthly", callback_data='select_monthly')])
    if lifetime:
        buttons.append([InlineKeyboardButton("💎 Lifetime", callback_data='select_lifetime')])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')])
    return InlineKeyboardMarkup(buttons)

def payment_keyboard(lang="EN", is_lifetime=False):
    """결제 수단 선택 버튼"""
    plan = "lifetime" if is_lifetime else "monthly"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Stripe", callback_data=f'pay_stripe_{plan}')],
        [InlineKeyboardButton("🅿️ PayPal", callback_data=f'pay_paypal_{plan}')],
        [InlineKeyboardButton("₿ Crypto", callback_data=f'pay_crypto_{plan}')],
        [InlineKeyboardButton("⬅️ Back", callback_data='plans')]
    ])
