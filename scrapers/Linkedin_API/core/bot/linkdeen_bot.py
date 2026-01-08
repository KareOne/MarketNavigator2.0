import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import random
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common import exceptions as selenium_exceptions
import pyperclip
import random
import time
import re
from typing import Optional, List
from selenium.common.exceptions import TimeoutException
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import os
import shutil
import requests
import sqlite3
from pathlib import Path
import uuid
import threading
import pickle


#from instabot import Bot

from config.config import BOT, CHROME, HASHTAGS, socketio
from utils.logger import bot_logger
from utils.exceptions import *

import time
import random
from datetime import datetime


class LinkedinBot:
    def __init__(self,username,is_first = 0):
        """Initialize LinkedIn bot with necessary configurations.

        is_first determines whether a login attempt should be performed by the
        global bot wrapper (we keep Chrome open between tasks). The login
        logic itself now targets LinkedIn (previous leftover Instagram
        selectors removed).
        """
        self.username = username
        self.user_id = None
        self.is_first = is_first
        self.setup_driver(username)

        # OpenAI Client removed - using only Gemini API
        self.wait_times = BOT['wait_times']
    


    
    
    def setup_driver(self,username) -> None:
        """Configure and initialize Chrome driver"""
        try:
            options = uc.ChromeOptions()

            # اضافه کردن آپشن‌ها
            for option in CHROME['options']:
                options.add_argument(option)

            # Use persistent Chrome profile - stays logged in forever
            profile_path = Path("chrome-profiles") / username
            profile_path.mkdir(parents=True, exist_ok=True)
            options.user_data_dir = str(profile_path.resolve())
            
            bot_logger.info(f"Using persistent profile: {profile_path.resolve()}")

            # تنظیم حالت headless
            if CHROME['is_headless']:
                options.add_argument('--headless=new')

            # Use undetected-chromedriver when requested to reduce detection
            bot_logger.info(f"Initializing Chrome in headless mode: {CHROME['is_headless']}")

            # encapsulate driver creation so we can retry with a headless fallback
            def _create_driver(opts, use_uc_flag):
                # try undetected-chromedriver when requested
                if use_uc_flag:
                    try:
                        opts.headless = CHROME['is_headless']
                        chrome_driver_path = "/home/social/Documents/programs/chrome_driver/chromedriver-linux64/chromedriver"
                        return uc.Chrome(options=opts, version_main=None,driver_executable_path=chrome_driver_path)
                    except Exception as uc_error:
                        bot_logger.error(f"undetected-chromedriver failed: {uc_error}, falling back to system ChromeDriver")
                        # fall through to system chromedriver

                # system chromedriver or webdriver-manager fallback
                import shutil
                # chromedriver_path = shutil.which('chromedriver') or '/usr/local/bin/chromedriver'
                chromedriver_path = "/home/social/Documents/programs/chrome_driver/chromedriver-linux64/chromedriver"

                if os.path.exists(chromedriver_path):
                    bot_logger.info(f"✅ Using system ChromeDriver at: {chromedriver_path}")
                    service = Service(chromedriver_path)
                    return webdriver.Chrome(service=service, options=opts)
                else:
                    bot_logger.warning("⚠️ System ChromeDriver not found, trying webdriver-manager...")
                    try:
                        service = Service(ChromeDriverManager().install())
                        bot_logger.info("✅ Using webdriver-manager")
                        return webdriver.Chrome(service=service, options=opts)
                    except Exception as wdm_error:
                        bot_logger.error(f"webdriver-manager failed: {wdm_error}, trying undetected-chromedriver")
                        opts.headless = CHROME['is_headless']
                        chrome_driver_path = "/home/social/Documents/programs/chrome_driver/chromedriver-linux64/chromedriver"
                        return uc.Chrome(options=opts, version_main=None,driver_executable_path=chrome_driver_path)

            use_uc = os.getenv('USE_UC', 'false').lower() == 'true'
            try:
                self.driver = _create_driver(options, use_uc)
            except Exception as first_exc:
                bot_logger.error(f"Initial Chrome initialization failed: {first_exc}")
                # If running inside a container without a display, non-headless Chrome will fail.
                # Retry once with headless enabled to improve robustness in headless environments.
                try:
                    bot_logger.info("Retrying Chrome initialization with headless mode enabled as a fallback")
                    # Ensure we add the new headless flag in a way compatible with options
                    if '--headless=new' not in options.arguments:
                        options.add_argument('--headless=new')
                    self.driver = _create_driver(options, False)
                except Exception as second_exc:
                    bot_logger.error(f"Headless fallback also failed: {second_exc}")
                    raise second_exc

            # تنظیم سایز پنجره
            self.driver.set_window_size(*CHROME['window_size'])

            # Set timeouts to prevent infinite hanging
            page_load_timeout = CHROME.get('page_load_timeout', 60)
            script_timeout = CHROME.get('script_timeout', 30)
            self.driver.set_page_load_timeout(page_load_timeout)
            self.driver.set_script_timeout(script_timeout)
            bot_logger.info(f"Timeouts set: page_load={page_load_timeout}s, script={script_timeout}s")

            # تنظیم زمان انتظار برای المان‌ها
            self.wait = WebDriverWait(self.driver, 30)

            bot_logger.info("Chrome driver initialized successfully")

        except Exception as e:
            bot_logger.error(f"Initial Chrome initialization failed: {e}")

            # Retry once with headless mode enabled if initial attempt failed
            try:
                if not CHROME.get('is_headless', False):
                    bot_logger.info("Retrying Chrome initialization with headless mode enabled as a fallback...")
                    # Ensure headless argument present
                    try:
                        options.add_argument('--headless=new')
                    except Exception:
                        options.headless = True

                    # Try system chromedriver first, then webdriver-manager
                    # chromedriver_path = shutil.which('chromedriver') or '/usr/local/bin/chromedriver'
                    chromedriver_path = "/home/social/Documents/programs/chrome_driver/chromedriver-linux64/chromedriver"
                    if os.path.exists(chromedriver_path):
                        bot_logger.info(f"✅ Using system ChromeDriver at: {chromedriver_path} (headless retry)")
                        port = random.randint(10000, 60000)
                        service = Service(chromedriver_path, port)
                        # if self.driver is not None:
                        #     try:
                        #         self.driver.quit()
                        #     except Exception:
                        #         pass

                        options.headless = True
                        options.add_argument('--no-sandbox')
                        options.add_argument('--disable-dev-shm-usage')
                        self.driver = webdriver.Chrome(service=service, options=options)
                    else:
                        bot_logger.info("⚠️ System ChromeDriver not found for headless retry, trying webdriver-manager...")
                        port = random.randint(10000, 60000)
                        service = Service(ChromeDriverManager().install(), port)
                        # if self.driver is not None:
                        #     try:
                        #         self.driver.quit()
                        #     except Exception:
                        #         pass

                        options.headless = True
                        options.add_argument('--no-sandbox')
                        options.add_argument('--disable-dev-shm-usage')
                        self.driver = webdriver.Chrome(service=service, options=options)

                    # finalize driver setup
                    self.driver.set_window_size(*CHROME['window_size'])
                    self.wait = WebDriverWait(self.driver, 30)
                    bot_logger.info("Chrome driver initialized successfully (headless fallback)")
                    return
            except Exception as e2:
                bot_logger.error(f"Headless retry also failed: {e2}")

            # If we reach here, both attempts failed
            raise ConnectionError(f"Failed to initialize Chrome driver: {str(e)}")

    def cleanup(self, force_quit=False) -> None:
        """Clean up and optionally quit driver
        
        Args:
            force_quit: If True, will quit the driver.
        """
        # Only quit driver if explicitly requested
        if force_quit and hasattr(self, 'driver') and self.driver is not None:
            try:
                bot_logger.info("Force closing Chrome driver...")
                self.driver.quit()
                bot_logger.info("Chrome driver closed successfully")
            except Exception as e:
                bot_logger.error(f"Error closing Chrome driver: {str(e)}")
            finally:
                self.driver = None
    
    def is_two_factor_required(self) -> bool:
        """بررسی می‌کند آیا صفحه 2FA ظاهر شده است یا خیر"""
        try:
            self.wait.until(EC.presence_of_element_located((By.NAME, "verificationCode")))
            return True
        except TimeoutException:
            return False
    
    def wait_for_two_factor_code(self):
        self._two_factor_code = None
        self._two_factor_event = threading.Event()
        bot_logger.info("Waiting for 2FA code from frontend")
        socketio.emit('two_factor_timeout_info', {
            "message": "لطفاً کد دو مرحله‌ای را در 60 ثانیه وارد کنید",
            "user_id": self.user_id
        }, to=str(self.user_id))
        if not self._two_factor_event.wait(timeout=60):
            socketio.emit('error', {
                "message": "زمان وارد کردن کد دو مرحله‌ای تمام شد. لطفاً دوباره تلاش کنید",
                "user_id": self.user_id
            }, to=str(self.user_id))
            raise LoginError("2FA code timeout")
        if self._two_factor_code:
            self.submit_two_factor_code(self._two_factor_code)
        else:
            raise LoginError("No 2FA code received")

    def set_two_factor_code(self, code):
        """وقتی کد دو مرحله‌ای از فرانت آمد این متد صدا زده می‌شود"""
        self._two_factor_code = code
        self._two_factor_event.set()

    def submit_two_factor_code(self, code):
        input_field = self.driver.find_element(By.NAME, "verificationCode")
        input_field.clear()
        input_field.send_keys(code)

        follow_button = WebDriverWait(self.driver, 10).until(
    EC.element_to_be_clickable((
        By.XPATH,
        "//button[normalize-space(text())='Confirm']"
    ))
)
        follow_button.click()

        time.sleep(20)
        if self.verify_login_status():
            bot_logger.info("2FA code accepted, logged in successfully")
        else:
            raise LoginError("کد دو مرحله‌ای نامعتبر است")
    
    def is_login_page(self) -> bool:
        """Detect LinkedIn login page.

        LinkedIn currently uses inputs with names: session_key & session_password.
        Older logic looked for 'username' which no longer exists.
        """
        try:
            self.driver.find_element(By.CSS_SELECTOR, '[name="session_key"]')
            self.driver.find_element(By.CSS_SELECTOR, '[name="session_password"]')
            return True
        except Exception as e:
            bot_logger.debug(f"Login page inputs not found: {e}")
            return False

    def load_cookies(self, driver, filename="google_cookies.pkl"):
        """Load cookies safely"""
        try:
            with open(filename, "rb") as f:
                cookies = pickle.load(f)
            
            # Navigate to Google first
            driver.get("https://linkedin.com")
            time.sleep(2)
            
            # Add cookies one by one, handling errors
            added = 0
            for cookie in cookies:
                try:
                    # Some cookies might have expired or have domain issues
                    driver.add_cookie(cookie)
                    added += 1
                except Exception as e:
                    # Skip problematic cookies
                    continue
            
            print(f"Added {added}/{len(cookies)} cookies")
            
            # Refresh to apply cookies
            driver.refresh()
            time.sleep(2)
            
            return True
            
        except FileNotFoundError:
            print(f"Cookie file {filename} not found")
            return False
        except Exception as e: 
            print(f"Error loading cookies: {e}")
            return False
        
    def login(self,username,password,user_id = 5) -> None:
        """Simple login: check if already logged in, if not try to login.
        
        Chrome profile persists the session, so after first successful login,
        subsequent runs will already be authenticated.
        """
        
        self.load_cookies(self.driver, "/home/social/Documents/projects/python_prjs/LinkedinLogin/google_cookies.pkl")
        bot_logger.info("✅ Successfully logged in! Profile saved, no need to login again.")
        return
        
        from selenium.common.exceptions import TimeoutException as SeleniumTimeoutException
        
        self.user_id = user_id
        
        # Check if already logged in (profile persists session)
        try:
            bot_logger.info("🔍 Checking if already logged in...")
            self.driver.get('https://www.linkedin.com')
            bot_logger.info("✅ LinkedIn homepage loaded")
        except SeleniumTimeoutException:
            bot_logger.error("❌ Timeout loading LinkedIn homepage - network issue?")
            raise LoginError("Timeout loading LinkedIn - check network connectivity")
        except Exception as e:
            bot_logger.error(f"❌ Error loading LinkedIn: {e}")
            raise LoginError(f"Failed to load LinkedIn: {e}")
        
        time.sleep(5)
        
        if self.verify_login_status():
            bot_logger.info("✅ Already logged in (session from persistent profile)")
            return

        # Not logged in, try to login
        if not password:
            bot_logger.warning("⚠️ Not logged in and no password provided")
            return
        
        bot_logger.info("Attempting to login...")
        bot_logger.info(f"🔑 Login credentials: username={username}, password={'*' * len(password) if password else 'NONE'}")
        
        try:
            self.driver.get('https://www.linkedin.com/login')
            bot_logger.info("✅ Login page loaded")
        except SeleniumTimeoutException:
            bot_logger.error("❌ Timeout loading LinkedIn login page")
            raise LoginError("Timeout loading LinkedIn login page")
        except Exception as e:
            bot_logger.error(f"❌ Error loading login page: {e}")
            raise LoginError(f"Failed to load login page: {e}")
            
        time.sleep(5)
        bot_logger.info(f"📍 After loading login page, URL: {self.driver.current_url}")

        try:
            # Robust waits for fields (avoid stale page issues)
            bot_logger.info("🔍 Looking for username field...")
            username_field = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,'input[name="session_key"]'))
            )
            bot_logger.info("✅ Found username field")
            
            bot_logger.info("🔍 Looking for password field...")
            password_field = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,'input[name="session_password"]'))
            )
            bot_logger.info("✅ Found password field")

            bot_logger.info("📝 Entering credentials...")
            username_field.clear(); username_field.send_keys(username)
            password_field.clear(); password_field.send_keys(password)
            bot_logger.info("✅ Credentials entered")

            bot_logger.info("🔍 Looking for submit button...")
            login_button = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR,'button[type="submit"]'))
            )
            bot_logger.info("✅ Found submit button, clicking...")
            login_button.click()
            bot_logger.info("✅ Submit button clicked")

            # Allow redirect & dynamic loads
            bot_logger.info("⏳ Waiting 8 seconds for redirect...")
            time.sleep(8)
            bot_logger.info(f"📍 After login click, URL: {self.driver.current_url}")
            bot_logger.info(f"📄 Page title: {self.driver.title}")

            if self.is_two_factor_required():
                bot_logger.info("Two-factor page detected")
                socketio.emit('two_factor_required', {
                    "username": username,
                    "message": "ورود دو مرحله‌ای لازم است",
                    "user_id": user_id
                }, to=str(self.user_id))
                self.wait_for_two_factor_code()
            else:
                if self.verify_login_status():
                    bot_logger.info("✅ Successfully logged in! Profile saved, no need to login again.")
                else:
                    # Capture diagnostics
                    try:
                        bot_logger.error(f"❌ Login failed; current URL: {self.driver.current_url}")
                        bot_logger.error(f"Page title: {self.driver.title}")
                        # Take a screenshot for debugging
                        try:
                            screenshot_path = f"/app/logs/login_failed_{int(time.time())}.png"
                            self.driver.save_screenshot(screenshot_path)
                            bot_logger.error(f"📸 Screenshot saved to: {screenshot_path}")
                        except Exception as ss_err:
                            bot_logger.error(f"Could not save screenshot: {ss_err}")
                        # Log page source snippet for debugging
                        try:
                            page_source = self.driver.page_source[:2000]
                            bot_logger.error(f"📄 Page source (first 2000 chars): {page_source}")
                        except Exception:
                            pass
                        if 'checkpoint' in self.driver.current_url.lower():
                            bot_logger.error("🚨 SECURITY CHECKPOINT DETECTED!")
                            bot_logger.error("LinkedIn requires manual verification.")
                            bot_logger.error("Set CHROME_HEADLESS=false and run locally to complete verification.")
                    except Exception:
                        pass
                    raise LoginError("Login failed - check credentials or complete security verification")
        except Exception as e:
            bot_logger.error(f"❌ Login exception: {str(e)}")
            try:
                bot_logger.error(f"📍 Current URL at failure: {self.driver.current_url}")
            except:
                pass
            raise LoginError(f"Login process failed: {str(e)}")

    def verify_login_status(self) -> bool:
        """Check if LinkedIn session is authenticated.

        Strategy:
        - URL contains /feed or /mynetwork or /in/ (profile)
        - Presence of global nav avatar / me-menu
        - Fallback: look for search box input
        """
        try:
            url = self.driver.current_url
            if any(x in url for x in ['feed','mynetwork','/in/']):
                return True

            indicators = [
                (By.ID,'global-nav-search'),
                (By.CSS_SELECTOR,'img.global-nav__me-photo'),
                (By.CSS_SELECTOR,'button[aria-label*="Me"]'),
            ]
            for by, sel in indicators:
                try:
                    self.driver.find_element(by, sel)
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            bot_logger.error(f"Error verifying login status: {e}")
            return False
        
    

    # ── db_utils.py ────────────────────────────────────────────────────────────────
