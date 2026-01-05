# bot_core/texts.py
from datetime import datetime

def current_month_year(lang="EN"):
    now = datetime.utcnow()
    month = now.strftime("%B")   # 영어 기준 월
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
        "onlytrns_welcome": (
            "Welcome to Private Collection\n\n"
            "──────────────────────────────\n\n"
            "• Only high quality handpicked content.\n"
            "• Premium ★nlyFans Videos\n"
            f"• {current_month_year()} ★ ACTIVE ★\n"
            "──────────────────────────────\n\n"
            "★ Price: $25\n"
            "★ INSTANT ACCESS ★\n\n"
            "💡 After payment, please send proof"
        ),
        "tswrld_welcome": (
            "Welcome to Private Collection\n\n"
            "──────────────────────────────\n\n"
            "• Curated premium content only.\n"
            "• Exclusive videos monthly.\n"
            f"• {current_month_year()} ★ ACTIVE ★\n"
            "──────────────────────────────\n\n"
            "★ Price: $21\n"
            "★ INSTANT ACCESS ★\n\n"
            "💡 After payment, please send proof"
        ),
        "morevids_welcome": (
            "Welcome to Private Collection\n\n"
            "Enjoy exclusive content, updates, and perks in our private Telegram channel.\n\n"
            "Choose your plan, pay securely, and get instant access.\n\n"
            "Support is available 24/7 🤝"
        )
    },
    "AR": {
        "letmebot_welcome": (
            "Welcome to Private Collection\n\n"
            "نحن سعداء جدًا بانضمامك إلينا! 🎉\n\n"
            "احصل على وصول فوري إلى محتوى بالغين حصري، تحديثات يومية، ومميزات خاصة في قناتنا الخاصة على تليجرام.\n\n"
            "اختر خطتك، أكمل الدفع، واحصل على رابط دعوة آمن فوراً.\n\n"
            "فريقنا دائماً هنا لدعمك 🤝\n"
            "مرحباً بك في التجربة المميزة المطلقة 🌟"
        ),
        "onlytrns_welcome": (
            "Welcome to Private Collection\n\n"
            "──────────────────────────────\n\n"
            "• فقط محتوى مختار عالي الجودة.\n"
            "• فيديوهات ★nlyFans المميزة\n"
            f"• {current_month_year('AR')} ★ نشطة ★\n"
            "──────────────────────────────\n\n"
            "★ السعر: $25\n"
            "★ وصول فوري ★\n\n"
            "💡 بعد الدفع، يرجى إرسال الإثبات"
        ),
        "tswrld_welcome": (
            "Welcome to Private Collection\n\n"
            "──────────────────────────────\n\n"
            "• محتوى مميز ومنسق فقط.\n"
            "• فيديوهات حصرية شهرياً.\n"
            f"• {current_month_year('AR')} ★ نشطة ★\n"
            "──────────────────────────────\n\n"
            "★ السعر: $21\n"
            "★ وصول فوري ★\n\n"
            "💡 بعد الدفع، يرجى إرسال الإثبات"
        ),
        "morevids_welcome": (
            "Welcome to Private Collection\n\n"
            "استمتع بالمحتوى الحصري والتحديثات والمزايا في قناتنا الخاصة على تليجرام.\n\n"
            "اختر خطتك، ادفع بأمان، واحصل على وصول فوري.\n\n"
            "الدعم متاح 24/7 🤝"
        )
    },
    "ES": {
        "letmebot_welcome": (
            "Welcome to Private Collection\n\n"
            "¡Estamos emocionados de tenerte con nosotros! 🎉\n\n"
            "Desbloquea contenido adulto exclusivo, actualizaciones diarias y beneficios especiales en nuestro canal privado de Telegram.\n\n"
            "Elige tu plan, completa el pago y obtén acceso instantáneo mediante un enlace de invitación seguro.\n\n"
            "Nuestro equipo siempre está aquí para apoyarte 🤝\n"
            "¡Bienvenido a la experiencia premium definitiva 🌟"
        ),
        "onlytrns_welcome": (
            "Welcome to Private Collection\n\n"
            "──────────────────────────────\n\n"
            "• Solo contenido seleccionado de alta calidad.\n"
            "• Videos Premium ★nlyFans\n"
            f"• {current_month_year('ES')} ★ ACTIVO ★\n"
            "──────────────────────────────\n\n"
            "★ Precio: $25\n"
            "★ ACCESO INMEDIATO ★\n\n"
            "💡 Después del pago, envía comprobante"
        ),
        "tswrld_welcome": (
            "Welcome to Private Collection\n\n"
            "──────────────────────────────\n\n"
            "• Contenido premium curado únicamente.\n"
            "• Videos exclusivos mensuales.\n"
            f"• {current_month_year('ES')} ★ ACTIVO ★\n"
            "──────────────────────────────\n\n"
            "★ Precio: $21\n"
            "★ ACCESO INMEDIATO ★\n\n"
            "💡 Después del pago, envía comprobante"
        ),
        "morevids_welcome": (
            "Welcome to Private Collection\n\n"
            "Disfruta de contenido exclusivo, actualizaciones y beneficios en nuestro canal privado de Telegram.\n\n"
            "Elige tu plan, paga de forma segura y obtén acceso instantáneo.\n\n"
            "Soporte disponible 24/7 🤝"
        )
    }
}

def get_text(bot_name: str, lang="EN"):
    bot_key = f"{bot_name}_welcome"
    return TEXTS.get(lang, TEXTS["EN"]).get(bot_key, "")
