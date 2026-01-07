"""
Worker Agent Configuration.
Load settings from environment variables.
"""
import os


# Orchestrator connection
ORCHESTRATOR_URL = os.getenv(
    "ORCHESTRATOR_URL", 
    "ws://localhost:8010/ws/worker"
)

# Worker authentication
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "dev-crunchbase-token")
API_TYPE = os.getenv("API_TYPE", "crunchbase")

# Local API endpoint (the actual scraper API this agent wraps)
LOCAL_API_URL = os.getenv("LOCAL_API_URL", "http://localhost:8003")

# Connection settings
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "10"))  # seconds
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "5"))  # seconds
MAX_RECONNECT_ATTEMPTS = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "0"))  # 0 = infinite

# Worker metadata
WORKER_NAME = os.getenv("WORKER_NAME", "")
WORKER_VERSION = os.getenv("WORKER_VERSION", "1.0.0")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
