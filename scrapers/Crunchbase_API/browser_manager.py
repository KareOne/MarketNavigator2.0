"""
Persistent browser manager for Crunchbase scraping.
Maintains a single browser instance across multiple operations.
Uses a queue system to handle concurrent requests safely.
"""

import os
import asyncio
import random
from typing import Callable, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, expect
from config import DEBUG, USERNAME, PASSWORD, STATE_PATH, SLEEP_DELAY, get_playwright_proxy_config


class CrunchbaseBrowserManager:
    """
    Manages a persistent browser instance for Crunchbase operations.
    
    - Opens browser once and keeps it alive
    - Creates new tabs for each operation
    - Handles login/session validation
    - Automatically recovers from session expiry
    - Queues concurrent requests to prevent interference
    """
    
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self._lock = asyncio.Lock()  # Prevent concurrent browser operations
        self._queue = asyncio.Queue()  # Queue for concurrent requests
        self._processing = False  # Flag to track if queue processor is running
        self._active_operations = 0  # Counter for active operations
        
    async def initialize(self):
        """Start playwright and create browser instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.browser:
            await self._create_browser()
            
    async def _create_browser(self):
        """Create a new browser and context."""
        proxy_config = get_playwright_proxy_config()
        launch_options = {"headless": DEBUG, "slow_mo": 100}
        if proxy_config:
            launch_options["proxy"] = proxy_config
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        self.context = await self.browser.new_context(
            storage_state=STATE_PATH if os.path.exists(STATE_PATH) else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        )
        print("✅ Browser instance created")
        
    async def _close_browser(self):
        """Close browser and context."""
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        print("🔄 Browser instance closed")
        
    async def is_logged_in(self, page: Page) -> bool:
        """
        Checks if the user is logged in by looking for elements
        that ONLY appear when authenticated.
        
        Returns:
            True if a logged-in element is found, False otherwise.
        """
        
        try:
            # Indicator 1: The "Account" button (Appears on all pages in the header)
            # This is the most reliable indicator across all pages
            account_button = page.get_by_role("button", name="Account")
            await expect(account_button).to_be_visible(timeout=2500)
            return True
        except Exception:
            # Fallback: Try to find the welcome heading
            try:
                # Look for any heading containing "Welcome back"
                welcome_heading = page.locator("h1, h2, h3").filter(has_text="Welcome back")
                await expect(welcome_heading).to_be_visible(timeout=2500)
                return True
            except Exception:
                # If neither is found, we are logged out
                return False
                
    async def _perform_login(self):
        """Perform login and save session state."""
        print("🔐 Performing login...")
        
        # Close existing browser if any
        await self._close_browser()
        
        # Create fresh browser without saved state
        proxy_config = get_playwright_proxy_config()
        launch_options = {"headless": DEBUG, "slow_mo": 200}
        if proxy_config:
            launch_options["proxy"] = proxy_config
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        )
        
        page = await self.context.new_page()
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
            
            # Verify login
            if await self.is_logged_in(page):
                print("✅ Login successful! Saving session state...")
                await self.context.storage_state(path=STATE_PATH)
                await page.close()
                return True
            else:
                print("❌ Login verification failed")
                await page.close()
                return False
        
        except Exception as e:
            print(f"❌ Login failed: {e}")
            try:
                await page.screenshot(path="crunchbase/ERROR_LOGS/login_failure.png")
                print("A screenshot 'login_failure.png' has been saved.")
            except:
                pass
            await page.close()
            return False
            
    async def ensure_logged_in(self, page: Page) -> bool:
        """
        Ensure the session is logged in. If not, perform login.
        
        Args:
            page: A page to check login status
            
        Returns:
            True if logged in (or successfully logged in), False otherwise
        """
        async with self._lock:  # Prevent concurrent login attempts
            if await self.is_logged_in(page):
                return True
            
            print("⚠️ Session expired, re-logging in...")
            await page.close()  # Close the check page
            
            login_success = await self._perform_login()
            if not login_success:
                raise Exception("Failed to login to Crunchbase")
            
            return True
    
    async def _start_queue_processor(self):
        """Start the background queue processor if not already running."""
        if not self._processing:
            self._processing = True
            asyncio.create_task(self._process_queue())
            print("🔄 Queue processor started")
    
    async def _process_queue(self):
        """Background task that processes queued operations sequentially."""
        while self._processing:
            try:
                # Get next operation from queue (wait up to 1 second)
                try:
                    operation = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # No operations in queue, continue loop
                    continue
                
                func, args, kwargs, result_future = operation
                
                try:
                    # Execute the operation
                    self._active_operations += 1
                    result = await func(*args, **kwargs)
                    result_future.set_result(result)
                except Exception as e:
                    result_future.set_exception(e)
                finally:
                    self._active_operations -= 1
                    self._queue.task_done()
                    
            except Exception as e:
                print(f"❌ Error in queue processor: {e}")
    
    async def queue_operation(self, func: Callable, *args, **kwargs) -> Any:
        """
        Queue an operation to be executed sequentially.
        
        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function execution
        """
        # Start queue processor if needed
        await self._start_queue_processor()
        
        # Create a future to hold the result
        result_future = asyncio.Future()
        
        # Add operation to queue
        await self._queue.put((func, args, kwargs, result_future))
        
        # Wait for result
        return await result_future
            
    async def new_page(self) -> Page:
        """
        Create a new page (tab) in the persistent browser.
        
        Returns:
            A new Page instance
        """
        if not self.context:
            await self.initialize()
            
        page = await self.context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return page
    
    def get_queue_status(self) -> dict:
        """
        Get current status of the operation queue.
        
        Returns:
            Dictionary with queue size and active operations count
        """
        return {
            "queue_size": self._queue.qsize(),
            "active_operations": self._active_operations,
            "is_processing": self._processing
        }
        
    async def close(self):
        """Cleanup: close browser and playwright."""
        # Stop queue processor
        self._processing = False
        
        # Wait for active operations to complete (max 30 seconds)
        wait_time = 0
        while self._active_operations > 0 and wait_time < 30:
            print(f"⏳ Waiting for {self._active_operations} active operations to complete...")
            await asyncio.sleep(1)
            wait_time += 1
        
        await self._close_browser()
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        print("✅ Browser manager closed")


# Global browser manager instance
_browser_manager = None


async def get_browser_manager() -> CrunchbaseBrowserManager:
    """Get or create the global browser manager instance."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = CrunchbaseBrowserManager()
        await _browser_manager.initialize()
    return _browser_manager


async def close_browser_manager():
    """Close the global browser manager."""
    global _browser_manager
    if _browser_manager:
        await _browser_manager.close()
        _browser_manager = None
