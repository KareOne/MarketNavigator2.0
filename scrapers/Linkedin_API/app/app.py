from config.config import account_ns, auth_ns, close_global_bot, socketio, app, get_db_connection, api
from flask_restx import Resource
from api.models.swagger import (account_model, page_list_model,
                                 hashtag_model, post_list_model, create_output_model,
                                 start_input_model, all_data_model, post_list_model,
                                 start_page_model2, page_list_model2, page_output, post_output,
                                 queue_hashtag_response)
from flask import request
from api.middlewares.auth import require_token
from core.automation.page_scraper import add_account, list_pages
import os
from datetime import datetime
from core.automation.hashtag import get_post, get_page, get_data_page, get_data_post, get_page2, get_post2
from utils.logger import bot_logger
import atexit

# ✅ Import Worker و Socket Handlers
from core.scheduler.worker import hashtag_worker
from services.socket_handlers import initialize_socket_handlers

# ✅ Import Route های جدید
from api.routes.hashtag_routes_new import hashtag_ns
from api.routes.page_routes_new import content_ns
from api.routes.keyword_routes import keyword_ns

# ✅ Register namespaces with the API
api.add_namespace(hashtag_ns)
api.add_namespace(content_ns)
api.add_namespace(keyword_ns)

# تابع cleanup برای زمان خاموش شدن برنامه
def cleanup_on_exit():
    bot_logger.info("Application is shutting down, closing Chrome...")
    
    # ✅ توقف Worker
    bot_logger.info("Stopping Worker...")
    hashtag_worker.stop()
    
    # ✅ بازگشت task‌های processing به pending
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE hashtags_queue SET status = 'pending' WHERE status = 'processing'")
        cursor.execute("UPDATE keywords_queue SET status = 'pending' WHERE status = 'processing'")
        cursor.execute("UPDATE linkdeen_posts SET analysis_status = 'pending' WHERE analysis_status = 'processing'")
        conn.commit()
        cursor.close()
        conn.close()
        bot_logger.info("Pending tasks restored")
    except Exception as e:
        bot_logger.error(f"Error restoring pending tasks: {e}")
    
    close_global_bot()
    bot_logger.info("Cleanup completed")

# ثبت تابع cleanup برای زمان خاموش شدن
atexit.register(cleanup_on_exit)


# ✅ مقداردهی اولیه Socket Handlers
bot_logger.info("🔌 در حال راه‌اندازی Socket Handlers...")
socket_handler_instance = initialize_socket_handlers(socketio)
bot_logger.info("✅ Socket Handlers راه‌اندازی شد")

bot_logger.info("✅ همه Route های جدید از طریق Namespace ها ثبت شدند")


# ✅ Health check endpoint for microservices monitoring
@app.route('/health')
def health_check():
    """
    Health check endpoint for load balancers and orchestrators
    Returns service status and basic diagnostics
    """
    try:
        # Check database connectivity
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check worker status
    from core.scheduler.worker import hashtag_worker
    worker_status = "running" if hashtag_worker.is_running else "stopped"
    
    health_data = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "linkedin-bot",
        "version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "components": {
            "database": db_status,
            "worker": worker_status,
            "api": "healthy"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return health_data, status_code


@account_ns.route('/add-account')
class AddAccount(Resource):
    @account_ns.expect(account_model)
    @account_ns.doc('افزودن حساب اینستاگرام')
    @require_token
    def post(self):
        return add_account(request)


# ✅ تمام endpoint های hashtag و page در namespace های زیر هستند:
# - hashtag_ns (در hashtag_routes_new.py): 
#     POST /start/hashtag/
#     POST /get-data/hashtag/
#     GET  /hashtag/list
#     GET  /worker/status
#
# - content_ns (در page_routes_new.py):
#     POST /start/page/
#     POST /get-data/page/
#     GET  /page/list


if __name__ == "__main__":
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # ✅ شروع Worker
    bot_logger.info("Starting Hashtag Worker...")
    hashtag_worker.start()
    bot_logger.info("Application started with background worker")
   
    socketio.run(app, debug=debug_mode, host='0.0.0.0', port=5001)
