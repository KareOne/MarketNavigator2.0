"""
Orchestrator Configuration.
Load settings from environment variables with sensible defaults.
"""
import os
from typing import Dict, List


# Server settings
ORCHESTRATOR_HOST = os.getenv("ORCHESTRATOR_HOST", "0.0.0.0")
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8010"))

# Redis settings
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")

# Backend status relay
BACKEND_STATUS_URL = os.getenv(
    "BACKEND_STATUS_URL", 
    "http://backend:8000/api/reports/status-update/"
)

# Worker authentication tokens (loaded from environment)
# Format: WORKER_TOKENS_CRUNCHBASE=token1,token2,token3
def _load_tokens() -> Dict[str, List[str]]:
    """Load worker tokens from environment variables."""
    tokens = {}
    api_types = ["crunchbase", "tracxn", "social"]
    
    for api_type in api_types:
        env_key = f"WORKER_TOKENS_{api_type.upper()}"
        env_value = os.getenv(env_key, "")
        if env_value:
            tokens[api_type] = [t.strip() for t in env_value.split(",") if t.strip()]
        else:
            # Default development tokens
            tokens[api_type] = [f"dev-{api_type}-token"]
    
    return tokens


WORKER_TOKENS: Dict[str, List[str]] = _load_tokens()

# Worker health settings
WORKER_HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "10"))  # seconds
WORKER_TIMEOUT = int(os.getenv("WORKER_TIMEOUT", "60"))  # seconds before marking offline

# Task settings
# TASK_TIMEOUT is the expected max duration for a task. Redis TTL is 2x this value.
# Crunchbase scraping can take 30+ minutes, so we set this to 2 hours.
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "7200"))  # 2 hours default
TASK_RETRY_LIMIT = int(os.getenv("TASK_RETRY_LIMIT", "3"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
