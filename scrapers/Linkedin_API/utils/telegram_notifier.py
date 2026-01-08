import asyncio
import os
from telegram import Bot

# خواندن توکن از environment variable
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_IDS_STR = os.getenv('TELEGRAM_CHAT_IDS', '')

# تبدیل رشته chat IDs به لیست
TELEGRAM_CHAT_IDS = []
if TELEGRAM_CHAT_IDS_STR:
    try:
        TELEGRAM_CHAT_IDS = [int(x.strip()) for x in TELEGRAM_CHAT_IDS_STR.split(',') if x.strip()]
    except:
        pass

# فعال/غیرفعال بودن تلگرام
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS)

def send_to_telegram(message: str):
    """ارسال پیام به تلگرام (async safe)"""
    # اگر تلگرام غیرفعال است، چیزی ارسال نشود
    if not TELEGRAM_ENABLED:
        return
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        for chat_id in TELEGRAM_CHAT_IDS:
            try:
                # استفاده از asyncio برای اجرای async function
                asyncio.run(bot.send_message(chat_id=chat_id, text=message))
            except RuntimeError:
                # اگر event loop در حال اجراست، از این روش استفاده می‌کنیم
                pass
    except Exception as e:
        # فقط اگر debug mode فعال باشد، خطا را نمایش بده
        if os.getenv('FLASK_DEBUG', 'False').lower() == 'true':
            print(f"[DEBUG] Telegram error: {e}")

