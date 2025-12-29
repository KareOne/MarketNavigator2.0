import os
from dotenv import load_dotenv

load_dotenv()
TARGET_URL = os.getenv("TARGET_URL", "https://tracxn.com/signup")
SLEEP_DELAY = float(os.getenv("SLEEP_DELAY", 1))
APIKEY_2CAPTCHA = os.getenv("APIKEY_2CAPTCHA")
DEBUG_MODE = os.getenv("DEBUG_MODE", "True")

# Proxy configuration
PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASS = os.getenv("PROXY_PASS")

RAPID_API_KEY = os.getenv("RAPID_API_KEY")
TEMPMAIL_TOKEN = os.getenv("TEMPMAIL_TOKEN")

# USE_PROXY = bool(PROXY_SERVER and PROXY_USER and PROXY_PASS)

USE_PROXY = False

# Database configuration
DB_CONFIG_HOST = "table-mountain.liara.cloud"
DB_CONFIG_PORT = 30986
DB_CONFIG_USER = "root"
DB_CONFIG_PASSWORD = "s3B0iJb3LodHdhL2KDxPfSlr"
DB_CONFIG_DATABASE = "tracxn_companies"

DB_CONFIG = {
    'host': DB_CONFIG_HOST,
    'port': DB_CONFIG_PORT,
    'user': DB_CONFIG_USER,
    'password': DB_CONFIG_PASSWORD,
    'database': DB_CONFIG_DATABASE,
}