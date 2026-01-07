import os
from dotenv import load_dotenv

load_dotenv()
USERNAME = os.getenv("CRUNCHBASE_USERNAME")
PASSWORD = os.getenv("CRUNCHBASE_PASSWORD")
STATE_PATH = os.getenv("CRUNCHBASE_BROWSER_STATE_PATH")
DEBUG = True
# Determine headless mode from env var, default to True (headless)
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TEST_JSON_OUTPUT = "crunchbase/TEST_OUTPUT/test_output.json"
DB_CONFIG_HOST = os.getenv("DB_CONFIG_HOST", "localhost")
DB_CONFIG_PORT = int(os.getenv("DB_CONFIG_PORT", 3306))
DB_CONFIG_USER = os.getenv("DB_CONFIG_USER", "root")
DB_CONFIG_PASSWORD = os.getenv("DB_CONFIG_PASSWORD")
DB_CONFIG_CRUNCHBASE_DATABASE = os.getenv("DB_CONFIG_CRUNCHBASE_DATABASE")
SLEEP_DELAY = float(os.getenv("CRUNCHBASE_SLEEP_DELAY"))

PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")


def get_playwright_proxy_config():
    """Returns Playwright proxy configuration if proxy settings are available."""
    if PROXY_SERVER:
        proxy_config = {
            "server": PROXY_SERVER
        }
        if PROXY_USERNAME and PROXY_PASSWORD:
            proxy_config["username"] = PROXY_USERNAME
            proxy_config["password"] = PROXY_PASSWORD
        
        print(f"🌐 Using proxy server: {PROXY_SERVER}")
        return proxy_config
    else:
        print("🌐 No proxy configuration found - using direct connection")
    return None