import logging
from logging.handlers import TimedRotatingFileHandler
import sys
from pathlib import Path
from datetime import datetime

# Import از مسیر جدید
try:
    from config.config import LOGGING
except ImportError:
    # برای اولین بار که config هنوز منتقل نشده
    LOGGING = {'dir': Path('logs'), 'filename': 'logger.txt'}

from utils.telegram_notifier import send_to_telegram

class TelegramHandler(logging.Handler):
    """Handler سفارشی برای ارسال تمام لاگ‌ها به تلگرام با پیشوند tehran_system"""
    def emit(self, record):
        try:
            # فرمت پیام لاگ با اضافه کردن پیشوند linkedin_system
            log_message = f"linkedin_system {self.format(record)}"
            
            # ارسال پیام به تلگرام
            send_to_telegram(log_message)
        except Exception as e:
            # در صورت بروز خطا در ارسال به تلگرام، آن را چاپ می‌کنیم
            print(f"خطا در ارسال پیام به تلگرام: {str(e)}")

def setup_logger(name: str) -> logging.Logger:
    """
    Configure and return a logger with both file and console handlers.
    Logs are saved daily in files named logger_YYYY-MM-DD.txt.

    Args:
        name: Name of the logger

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(LOGGING['dir'])
    log_dir.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent adding handlers if already configured
    if not logger.handlers:
        # Log format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler (rotates daily, with date in filename)
        log_file = log_dir / f"logger_{datetime.now().strftime('%Y-%m-%d')}.txt"
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',  # چرخش روزانه در نیمه‌شب
            interval=1,       # هر 1 روز
            backupCount=30,   # نگه‌داری حداکثر 30 فایل لاگ (30 روز)
            encoding='utf-8'  # تنظیم انکودینگ UTF-8 برای فایل
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        # تنظیم پسوند فایل به تاریخ
        file_handler.suffix = "_%Y-%m-%d.txt"

        # Console handler with UTF-8 encoding
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        # Set encoding for stdout to UTF-8
        if hasattr(console_handler.stream, "reconfigure"):  # Python 3.7+
            console_handler.stream.reconfigure(encoding='utf-8')

        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # اضافه کردن TelegramHandler فقط به bot_logger
        if name == 'linkedin_bot':
            telegram_handler = TelegramHandler()
            telegram_handler.setFormatter(formatter)
            telegram_handler.setLevel(logging.INFO)  # برای همه سطوح لاگ
            logger.addHandler(telegram_handler)

    return logger

# Create specific loggers
bot_logger = setup_logger('linkedin_bot')
db_logger = setup_logger('database')

# اطمینان از وجود فایل لاگ
def ensure_log_file():
    log_dir = Path(LOGGING['dir'])
    log_file = log_dir / f"logger_{datetime.now().strftime('%Y-%m-%d')}.txt"
    if not log_file.exists():
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('Log file created\n')

# اجرای اولیه برای اطمینان از وجود فایل
ensure_log_file()
