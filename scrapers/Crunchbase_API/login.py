import os
from dotenv import load_dotenv
import asyncio
import csv
import random
import argparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from config import DEBUG, USERNAME, PASSWORD, STATE_PATH, SLEEP_DELAY, get_playwright_proxy_config

async def perform_initial_login(playwright):
    """Launches a browser, performs login, and saves the session state."""
    proxy_config = get_playwright_proxy_config()
    launch_options = {"headless": DEBUG, "slow_mo": 200}
    if proxy_config:
        launch_options["proxy"] = proxy_config
    
    browser = await playwright.chromium.launch(**launch_options)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        await page.goto("https://www.crunchbase.com/login", wait_until='domcontentloaded')
        
        await page.wait_for_timeout(5000)
        await page.locator("input[name=email]").fill(USERNAME)
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        await page.locator("input[name=password]").fill(PASSWORD)
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        await page.wait_for_timeout(5000)
        
        await page.locator("button[type=submit]").click()
        await page.wait_for_url("https://www.crunchbase.com/**", timeout=90000)
        await page.wait_for_timeout(5000)
        print("✅ Login successful! Saving session state...")
        await context.storage_state(path=STATE_PATH)
    
    except Exception as e:
        print(f"❌ Login failed: {e}")
        await page.screenshot(path="crunchbase/ERROR_LOGS/login_failure.png")
        print("A screenshot 'login_failure.png' has been saved.")
    
    finally:
        await browser.close()

async def check_login(playwright, page):
    """Check if page is redirected to login, and re-login if needed."""
    if "login" in page.url.lower() or "multisession-logout" in page.url.lower():
        return True
    return False