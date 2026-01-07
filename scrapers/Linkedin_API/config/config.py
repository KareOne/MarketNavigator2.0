from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv, find_dotenv
import logging
import pymysql

# Load environment variables from .env file
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
if dotenv_path and os.getenv("FLASK_DEBUG", "False").lower() == "true":
    print(f"Loading .env from: {dotenv_path}")
    load_dotenv(dotenv_path)
elif os.getenv("FLASK_DEBUG", "False").lower() == "true":
    print("⚠️ فایل .env پیدا نشد!")

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Database settings for MySQL
DATABASE = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'alishams333444'),
    'database': os.getenv('MYSQL_DATABASE', 'linkdeen_bot'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'backup_dir': BASE_DIR / 'backups'
}

# Function to get MySQL connection
def get_db_connection():
    conn = pymysql.connect(
        host=DATABASE['host'],
        user=DATABASE['user'],
        password=DATABASE['password'],
        database=DATABASE['database'],
        port=DATABASE['port'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    if not conn.open:
        conn = pymysql.connect(
            host=DATABASE['host'],
            user=DATABASE['user'],
            password=DATABASE['password'],
            database=DATABASE['database'],
            port=DATABASE['port'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    return conn

# Google Gemini AI removed - no AI generation needed in this application

# API keys and AI generation functions removed
try:
    from utils.logger import bot_logger
except Exception:
    bot_logger = None
    
def try_generate(prompt: str) -> str:
    """
    AI generation disabled - returns empty string
    """
    if bot_logger:
        try: 
            bot_logger.info("AI generation is disabled in this version")
        except Exception: 
            pass
    return ""


# LinkedIn hashtags to monitor
HASHTAGS = ['یادگیری_عمیق', 'هوش_مصنوعی', 'ماشین_لرنینگ', 'برنامه_نویسی']

# Bot behavior settings
BOT = {
    'min_likes_per_hashtag': 1,
    'max_likes_per_hashtag': 5,
    'min_caption_length': 45,
    'wait_times': {
        'after_login': 7,
        'after_like': (20, 30),
        'after_scroll': (30, 60),
        'after_page_load': 15,
        'after_action': (30, 40)
    }
}

# Chrome settings
CHROME = {
    'user_data_dir': BASE_DIR / 'browser_data',
    'options': [
        '--start-maximized',
        '--disable-gpu',
        '--no-sandbox',
        '--disable-dev-shm-usage',  # Overcome limited resource problems
        '--disable-notifications',
        '--disable-setuid-sandbox',
        '--lang=en-US',
        # Critical flags for Docker/headless environments
        '--disable-extensions',
        '--disable-software-rasterizer',
        '--disable-background-networking',
        '--disable-default-apps',
        '--disable-sync',
        '--disable-translate',
        '--disable-features=VizDisplayCompositor',
        '--disable-blink-features=AutomationControlled',
        '--remote-debugging-port=9222',
        '--password-store=basic',
        '--window-size=1920,1080',
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ],
    # Auto-detect headless mode based on environment (headless in Docker, GUI if DISPLAY available)
    'is_headless': os.getenv('CHROME_HEADLESS', 'true').lower() == 'true',
    'window_size': (1920, 1080),
    'page_load_timeout': 60,  # Max seconds to wait for page load
    'script_timeout': 30,     # Max seconds for script execution
}

# Logging settings
LOGGING = {
    'dir': Path('logs'),
    'filename': 'logger.txt'
}

# Media path for storing files (e.g., profile pictures)
MEDIA_PATH = 'media'

SMS_API_URL = 'https://api2.ippanel.com/api/v1/sms/pattern/normal/send'
SMS_API_KEY = 'y_w09NKuT3wVfPblO4m0lLRzDPX-ccmTowKkCzaj_cA='
SMS_SENDER = '+983000505'
SMS_PATTERN_CODE = 'd740jsltbwggubb'

class User:
    def __init__(self, id, phone_number, role="user", is_active=0):
        self.id = id
        self.phone_number = phone_number
        self.role = role
        self.is_active = is_active

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot_logger')

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.mp4', '.mov'}

MEDIA_FOLDER = 'media/'
if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)

bot_instances = {}

from flask import Flask
from flask_cors import CORS
from flask_restx import Api

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = '28061380'

# تنظیمات Flask-RESTx
api = Api(app,
    version='1.0',
    title='API ربات لینکدین',
    description='برای لینکدین',
    doc='/swagger',
    authorizations={
        'Bearer Auth': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'Enter your Bearer token in the format **Bearer &lt;token&gt;**'
        }
    },
    security='Bearer Auth'
)

phone_number = "+989922417276"
users_verification = {}
auth_ns = api.namespace('auth', description='عملیات مربوط به احراز هویت')
account_ns = api.namespace('account', description='مدیریت حساب‌های اینستاگرام')
follow_ns = api.namespace('follow', description='مدیریت تسک‌های فالو')
send_ns = api.namespace('send', description='مدیریت ارسال دیتا ')
report_ns = api.namespace('report', description='مدیریت گزارش‌گیری ')
routine_ns = api.namespace('routine', description='عملیات مربوط به مدیریت روتین‌ها')
content_ns = api.namespace('content', description='عملیات مربوط به مدیریت content ها')
user_ns = api.namespace('user', description='عملیات مربوط به مدیریت user ها')

# ✅ Namespace های جدید برای Queue System
hashtag_ns = api.namespace('hashtag', description='مدیریت صف هشتگ‌ها و پردازش آن‌ها')
page_ns = api.namespace('page', description='مدیریت صف صفحات شرکت‌ها و پردازش آن‌ها')
keyword_ns = api.namespace('keyword', description='مدیریت جستجوی کلمات کلیدی و پردازش آن‌ها')


MAX_FILE_SIZE = 10 * 1024 * 1024  # حداکثر 10 مگابایت

# CAPTCHA removed - causes dependency conflicts with flask-restx
# Authentication should be handled by DRF backend

from flask_socketio import SocketIO

socketio = SocketIO(app, cors_allowed_origins="*")

running_bots = {}

from threading import Lock

followers_scheduler_lock = Lock()
routine_scheduler_lock = Lock()

# Global Bot Instance Manager
_global_bot_instance = None
_bot_lock = Lock()
_bot_logged_in = False

def get_global_bot(username="pr1", password="", user_id=5, is_first=0):
    """
    Get or create a global bot instance that persists across requests.
    This ensures Chrome stays open for all operations.
    
    If password is empty or None, the bot will skip login and only access public data.
    """
    global _global_bot_instance, _bot_logged_in
    
    # Use standard logging since bot_logger may be None due to import order
    import logging
    logger = logging.getLogger('bot_logger')
    
    logger.info(f"🔄 get_global_bot() called: username={username}, is_first={is_first}")
    
    with _bot_lock:
        if _global_bot_instance is None:
            logger.info(f"🆕 Creating new global bot instance for {username}")
            
            # Import here to avoid circular dependency
            from core.bot.linkdeen_bot import LinkedinBot
            
            # Always create with is_first=0 to avoid duplicate login
            _global_bot_instance = LinkedinBot(username, is_first=0)
            
            logger.info("✅ Global bot instance created (Chrome opened)")
        else:
            logger.info("♻️ Reusing existing global bot instance")
        
        # Login only if password is provided AND is_first == 1
        if not _bot_logged_in and is_first == 1 and password:
            logger.info(f"🔑 Attempting login for username: {username}")
            try:
                _global_bot_instance.login(username, password, user_id)
                _bot_logged_in = True
                logger.info("✅ Login call completed")
            except Exception as e:
                logger.error(f"❌ Login attempt raised error: {e}")
            
            # Verify authenticated session before marking as logged in
            # try:
            #     if hasattr(_global_bot_instance, 'verify_login_status') and _global_bot_instance.verify_login_status():
            #         _bot_logged_in = True
            #         logger.info("✅ Login verified - bot is ready for use")
            #     else:
            #         logger.warning("⚠️ Login not verified; will retry on next is_first call")
            # except Exception as e:
            #     logger.error(f"❌ Error verifying login status: {e}")
        elif not password and is_first == 1:
            logger.info("⚠️ No password provided - bot will only access public LinkedIn data (no login)")
        elif _bot_logged_in:
            logger.info("✅ Bot already logged in, skipping login")
        
        return _global_bot_instance

def close_global_bot():
    """
    Close the global bot instance (only call on app shutdown)
    """
    global _global_bot_instance, _bot_logged_in
    
    with _bot_lock:
        if _global_bot_instance is not None:
            if bot_logger:
                bot_logger.info("Closing global bot instance")
            _global_bot_instance.cleanup(force_quit=True)
            _global_bot_instance = None
            _bot_logged_in = False

KAVENEGAR_API_KEY = "6F766C646B30307173454A30675876744659594C4A377A4763673161346F58763454696546633576744D413D"
KAVENEGAR_TEMPLATE = "verification-code"  # اسم تمپلیتت تو پنل

# Ensure API routes are registered when this module is imported by Gunicorn
def _register_routes():
    """
    Register namespaces and import route modules.
    This must be called AFTER all other module initialization is complete
    to avoid circular import issues.
    """
    global api, hashtag_ns, page_ns, keyword_ns
    import logging
    logger = logging.getLogger('bot_logger')
    
    try:
        # ✅ First, add namespaces to the API object
        # This is required for Flask-RESTX to expose the endpoints
        api.add_namespace(hashtag_ns, path='/hashtag')
        api.add_namespace(page_ns, path='/content')
        api.add_namespace(keyword_ns, path='/keyword')
        
        # Importing these modules attaches resources to namespaces defined above
        import api.routes.hashtag_routes_new  # noqa: F401
        import api.routes.page_routes_new     # noqa: F401
        import api.routes.keyword_routes      # noqa: F401
        
        logger.info("✅ Namespaces added to API and routes imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to register routes: {e}", exc_info=True)
        # Don't break app import; Swagger will still load, but without endpoints
        return False

# ⚠️ Don't call _register_routes() here at module level
# It will be called from gunicorn.conf.py post_worker_init hook
# to avoid circular imports during initial module load


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
    
    # Check worker status (optional, may not be started yet in gunicorn context)
    try:
        from core.scheduler.worker import hashtag_worker
        worker_status = "running" if hashtag_worker.is_running else "stopped"
    except Exception:
        worker_status = "unknown"
    
    health_data = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": os.getenv("SERVICE_NAME", "linkedin-bot"),
        "version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "components": {
            "database": db_status,
            "worker": worker_status,
            "api": "healthy"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    from flask import jsonify
    return jsonify(health_data), status_code


# ✅ OpenAPI JSON endpoint (alias to /swagger.json)
@app.route('/openapi.json')
def openapi_spec():
    """Returns OpenAPI/Swagger specification in JSON format"""
    from flask import redirect
    # Redirect to the built-in swagger.json endpoint provided by Flask-RESTX
    return redirect('/swagger.json', code=307)


