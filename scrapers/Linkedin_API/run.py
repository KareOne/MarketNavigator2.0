#!/usr/bin/env python3
"""
Entry point اصلی برای اجرای برنامه LinkedIn Bot
"""
from app.app import app, socketio
from config.config import close_global_bot
from utils.logger import bot_logger
from core.scheduler.worker import hashtag_worker
import atexit
import os

# ثبت cleanup handler
atexit.register(close_global_bot)

if __name__ == '__main__':
    bot_logger.info("=" * 60)
    bot_logger.info("🚀 شروع سرور Flask - LinkedIn Scraping Bot")
    bot_logger.info("=" * 60)
    bot_logger.info("📍 آدرس: http://localhost:5001")
    bot_logger.info("📚 Swagger UI: http://localhost:5001/swagger")
    bot_logger.info("=" * 60)
    
    # 🔥 شروع Worker برای پردازش صف‌ها
    bot_logger.info("🤖 راه‌اندازی Worker برای پردازش صف‌ها...")
    hashtag_worker.start()
    bot_logger.info("✅ Worker شروع به کار کرد")
    bot_logger.info("=" * 60)
    
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    try:
        socketio.run(app, host='0.0.0.0', port=5001, debug=debug_mode, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        bot_logger.info("\n⚠️  دریافت سیگنال توقف...")
        hashtag_worker.stop()
        close_global_bot()
        bot_logger.info("✅ برنامه با موفقیت متوقف شد")
    except Exception as e:
        bot_logger.error(f"❌ خطا در اجرای برنامه: {str(e)}")
        hashtag_worker.stop()
        close_global_bot()
