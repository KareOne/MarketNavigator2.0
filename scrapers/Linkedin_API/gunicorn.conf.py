# Gunicorn configuration file
import os
from utils.logger import bot_logger
# gunicorn. conf.py
import os

# Worker-specific driver storage
worker_drivers = {}

# Server socket
bind = "0.0.0.0:5001"
workers = 1
worker_class = "sync"
timeout = 120

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    bot_logger.info("🚀 Gunicorn master process starting...")

def when_ready(server):
    """Called just after the server is started."""
    bot_logger.info("✅ Gunicorn server is ready")

def post_worker_init(worker):
    """Called just after a worker has been initialized."""
    bot_logger.info(f"👷 Worker {worker.pid} initialized...")
    
    # ✅ Register API routes FIRST (before starting worker)
    # This must happen in worker context to avoid circular imports
    try:
        from config.config import _register_routes
        bot_logger.info("📋 Registering API routes...")
        if _register_routes():
            bot_logger.info("✅ API routes registered successfully")
        else:
            bot_logger.warning("⚠️  Route registration returned False")
    except Exception as e:
        bot_logger.error(f"❌ Failed to register routes in worker: {e}")
    
    # Now start the background worker
    try:
        from core.scheduler.worker import hashtag_worker
        if not hashtag_worker.is_running:
            bot_logger.info("🤖 Starting hashtag worker...")
            hashtag_worker.start()
            bot_logger.info("✅ Hashtag worker started successfully in worker process")
        else:
            bot_logger.info("ℹ️  Hashtag worker already running")
    except Exception as e:
        bot_logger.error(f"❌ Failed to start hashtag worker: {e}")

def worker_exit(server, worker):
    
    """Called just after a worker has been exited."""
    pid = worker.pid
    
    if pid in worker_drivers and worker_drivers[pid]:
        try:
            worker_drivers[pid].quit()
            print(f"[Worker {pid}] WebDriver session closed")
        except Exception as e:
            print(f"[Worker {pid}] Error closing WebDriver: {e}")
        finally:
            del worker_drivers[pid]
    
    # Also kill any remaining chromedriver processes
    try:
        os.system(f"pkill -P {pid} chromedriver")
    except:
        pass
    
    """Called just after a worker has been exited."""
    bot_logger.info(f"👋 Worker {worker.pid} exiting, stopping background worker...")
    
    try:
        from core.scheduler.worker import hashtag_worker
        if hashtag_worker.is_running:
            hashtag_worker.stop()
            bot_logger.info("✅ Hashtag worker stopped")
    except Exception as e:
        bot_logger.error(f"❌ Error stopping worker: {e}")
