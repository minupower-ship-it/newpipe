# bot_core/texts.py
from datetime import datetime

def current_month_year(lang="EN"):
    now = datetime.utcnow()
    month = now.strftime("%B")
    year = now.year

    if lang == "AR":
        months_ar = [
            "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
        ]
        month = months_ar[now.month - 1]
    elif lang == "ES":
        months_es = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        month = months_es[now.month - 1]
    elif lang == "CN":
        months_cn = [
            "一月", "二月", "三月", "四月", "五月", "六月",
            "七月", "八月", "九月", "十月", "十一月", "十二月"
        ]
        month = months_cn[now.month - 1]

    return f"{month} {year}"

TEXTS = {
    "EN": {
        "letmebot_welcome": (
            "Welcome to Private Collection\n\n"
            "We're thrilled to have you join us! 🎉\n\n"
            "Unlock exclusive adult content, daily updates, and special perks in our private Telegram channel.\n\n"
            "Choose your plan, complete payment, and get instant access via a secure invite link.\n\n"
            "Our team is always here to support you 🤝\n"
            "Welcome to the ultimate premium experience 🌟"
        ),
        "morevids_welcome": (
            "Welcome to Private Collection\n\n"
            "Enjoy exclusive content, updates, and perks in our private Telegram channel.\n\n"
            "Choose your plan, pay securely, and get instant access.\n\n"
            "Support is available 24/7 🤝"
        ),
        "onlytrns_welcome": (
            "───────────────────────────\n\n"
            "Welcome to Private Collection\n\n"
            "───────────────────────────\n\n"
            "• Only high quality handpicked content.\n"
            "• Premium ★nlyFans Videos\n"
            f"• {current_month_year()} ★ ACTIVE ★\n\n"
            "───────────────────────────\n\n"
            "★ Price: $25\n"
            "★ INSTANT ACCESS ★\n\n"
            "───────────────────────────\n\n"
            "💡 After payment, please send proof"
        ),
        "tswrld_welcome": (
            "───────────────────────────\n\n"
            "Welcome to Private Collection\n\n"
            "───────────────────────────\n\n"
            "• Curated premium content only.\n"
            "• Exclusive videos monthly.\n"
            f"• {current_month_year()} ★ ACTIVE ★\n\n"
            "───────────────────────────\n\n"
            "★ Price: $21\n"
            "★ INSTANT ACCESS ★\n\n"
            "───────────────────────────\n\n"
            "💡 After payment, please send proof"
        ),
        "lust4trans_welcome": (
            "Lust4trans\n\n"
            "High-quality trans content\n"
            "Daily updates\n"
            "Exclusive videos only\n\n"
            "Choose your plan\n"
            "Pay securely\n"
            "Instant access\n\n"
            "Private & discreet\n"
            "Support available 24/7"
        ),
    },
    "AR": {
        "letmebot_welcome": (
            "مرحباً بك في Private Collection\n\n"
            "نحن سعداء جدًا بانضمامك إلينا! 🎉\n\n"
            "احصل على وصول فوري إلى محتوى بالغين حصري، تحديثات يومية، ومميزات خاصة في قناتنا الخاصة على تليجرام.\n\n"
            "اختر خطتك, أكمل الدفع, واحصل على رابط دعوة آمن فوراً.\n\n"
            "فريقنا دائماً هنا لدعمك 🤝\n"
            "مرحباً بك في التجربة المميزة المطلقة 🌟"
        ),
        "morevids_welcome": (
            "مرحباً بك في Private Collection\n\n"
            "استمتع بمحتوى حصري, تحديثات, ومميزات في قناتنا الخاصة على تليجرام.\n\n"
            "اختر خطتك, ادفع بأمان, واحصل على وصول فوري.\n\n"
            "الدعم متاح 24/7 🤝"
        ),
        "onlytrns_welcome": (
            "───────────────────────────\n\n"
            "مرحباً بك في Private Collection\n\n"
            "───────────────────────────\n\n"
            "• فقط محتوى مختار عالي الجودة.\n"
            "• فيديوهات ★nlyFans المميزة\n"
            f"• {current_month_year('AR')} ★ نشطة ★\n\n"
            "───────────────────────────\n\n"
            "★ السعر: $25\n"
            "★ وصول فوري ★\n\n"
            "───────────────────────────\n\n"
            "💡 بعد الدفع, يرجى إرسال الإثبات"
        ),
        "tswrld_welcome": (
            "───────────────────────────\n\n"
            "مرحباً بك في Private Collection\n\n"
            "───────────────────────────\n\n"
            "• محتوى مميز ومنسق فقط.\n"
            "• فيديوهات حصرية شهرياً.\n"
            f"• {current_month_year('AR')} ★ نشطة ★\n\n"
            "───────────────────────────\n\n"
            "★ السعر: $21\n"
            "★ وصول فوري ★\n\n"
            "───────────────────────────\n\n"
            "💡 بعد الدفع, يرجى إرسال الإثبات"
        ),
        "lust4trans_welcome": (
            "Lust4trans\n\n"
            "محتوى ترانسجندر عالي الجودة\n"
            "تحديث يومي\n"
            "فيديوهات حصرية فقط\n\n"
            "اختر خطتك\n"
            "ادفع بأمان\n"
            "وصول فوري\n\n"
            "خاص وسري\n"
            "دعم متوفر 24/7"
        ),
    },
    "ES": {
        "letmebot_welcome": (
            "Bienvenido a Private Collection\n\n"
            "¡Estamos emocionados de tenerte con nosotros! 🎉\n\n"
            "Desbloquea contenido adulto exclusivo, actualizaciones diarias y beneficios especiales en nuestro canal privado de Telegram.\n\n"
            "Elige tu plan, completa el pago y obtén acceso instantáneo mediante un enlace de invitación seguro.\n\n"
            "Nuestro equipo siempre está aquí para apoyarte 🤝\n"
            "¡Bienvenido a la experiencia premium definitiva 🌟"
        ),
        "morevids_welcome": (
            "Bienvenido a Private Collection\n\n"
            "Disfruta de contenido exclusivo, actualizaciones y beneficios en nuestro canal privado de Telegram.\n\n"
            "Elige tu plan, paga de forma segura y obtén acceso instantáneo.\n\n"
            "Soporte disponible 24/7 🤝"
        ),
        "onlytrns_welcome": (
            "───────────────────────────\n\n"
            "Bienvenido a Private Collection\n\n"
            "───────────────────────────\n\n"
            "• Solo contenido seleccionado de alta calidad.\n"
            "• Videos Premium ★nlyFans\n"
            f"• {current_month_year('ES')} ★ ACTIVO ★\n\n"
            "───────────────────────────\n\n"
            "★ Precio: $25\n"
            "★ ACCESO INMEDIATO ★\n\n"
            "───────────────────────────\n\n"
            "💡 Después del pago, envía comprobante"
        ),
        "tswrld_welcome": (
            "───────────────────────────\n\n"
            "Bienvenido a Private Collection\n\n"
            "───────────────────────────\n\n"
            "• Contenido premium curado únicamente.\n"
            "• Videos exclusivos mensuales.\n"
            f"• {current_month_year('ES')} ★ ACTIVO ★\n\n"
            "───────────────────────────\n\n"
            "★ Precio: $21\n"
            "★ ACCESO INMEDIATO ★\n\n"
            "───────────────────────────\n\n"
            "💡 Después del pago, envía comprobante"
        ),
        "lust4trans_welcome": (
            "Lust4trans\n\n"
            "Contenido trans de alta calidad\n"
            "Actualizaciones diarias\n"
            "Solo videos exclusivos\n\n"
            "Elige tu plan\n"
            "Paga de forma segura\n"
            "Acceso inmediato\n\n"
            "Privado y discreto\n"
            "Soporte disponible 24/7"
        ),
    },
    "CN": {
        "letmebot_welcome": (
            "欢迎来到私人收藏\n\n"
            "我们很高兴您加入我们！🎉\n\n"
            "在我们的私人 Telegram 频道中解锁独家成人内容、每日更新和特殊特权。\n\n"
            "选择您的计划，完成付款，通过安全的邀请链接立即获得访问权限。\n\n"
            "我们的团队随时为您提供支持 🤝\n"
            "欢迎体验终极高级体验 🌟"
        ),
        "morevids_welcome": (
            "欢迎来到私人收藏\n\n"
            "在我们的私人 Telegram 频道中享受独家内容、更新和特权。\n\n"
            "选择您的计划，安全付款，立即获得访问权限。\n\n"
            "24/7 支持可用 🤝"
        ),
        "onlytrns_welcome": (
            "───────────────────────────\n\n"
            "欢迎来到私人收藏\n\n"
            "───────────────────────────\n\n"
            "• 仅精选高质量内容。\n"
            "• 高级 ★nlyFans 视频\n"
            f"• {current_month_year('CN')} ★ 活跃 ★\n\n"
            "───────────────────────────\n\n"
            "★ 价格: $25\n"
            "★ 即时访问 ★\n\n"
            "───────────────────────────\n\n"
            "💡 付款后请发送证明"
        ),
        "tswrld_welcome": (
            "───────────────────────────\n\n"
            "欢迎来到私人收藏\n\n"
            "───────────────────────────\n\n"
            "• 仅精选高级内容。\n"
            "• 每月独家视频。\n"
            f"• {current_month_year('CN')} ★ 活跃 ★\n\n"
            "───────────────────────────\n\n"
            "★ 价格: $21\n"
            "★ 即时访问 ★\n\n"
            "───────────────────────────\n\n"
            "💡 付款后请发送证明"
        ),
        "lust4trans_welcome": (
            "Lust4trans\n\n"
            "高质量跨性别内容\n"
            "每日更新\n"
            "仅限独家视频\n\n"
            "选择计划\n"
            "安全付款\n"
            "即时访问\n\n"
            "私密且保密\n"
            "24/7 支持"
        ),
    }
}

def get_text(bot_name: str, lang="EN"):
    bot_key = f"{bot_name}_welcome"
    return TEXTS.get(lang, TEXTS["EN"]).get(bot_key, "")
