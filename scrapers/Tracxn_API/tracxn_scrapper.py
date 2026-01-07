#!/usr/bin/env python3
import os
import random
import time
import asyncio
import requests
import logging
import json 
import re
import base64
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import Playwright, async_playwright, TimeoutError as PlaywrightTimeoutError
from twocaptcha import TwoCaptcha, ApiException
from config import DEBUG_MODE, APIKEY_2CAPTCHA, TARGET_URL, SLEEP_DELAY, PROXY_SERVER, PROXY_USER, PROXY_PASS, USE_PROXY
from tempmailcore import EmailInbox
import uuid
from helpers.index import calculate_captcha, send_request, test_request
# test_request()

OUTPUT_DIR = "company_data"

class TracxnBot:
    def __init__(self, playwright: Playwright, debug: bool = False):
        load_dotenv()
        self.target_url = TARGET_URL
        self.api_key = APIKEY_2CAPTCHA
        self.debug = debug
        self.playwright = playwright
        self.browser = None
        self.page = None
        self.image_chache_path = f"images_cache/downloaded_image_{uuid.uuid4().hex}.png"
        self.audio_cache_path = f"audio_cache/downloaded_audio_{uuid.uuid4().hex}.mp3"
        self.email_inbox = None
        self.email_address = None
        self.setup_logging()
        
        # Log proxy configuration status
        if USE_PROXY:
            self.log.info(f"Proxy configuration loaded: {PROXY_SERVER}")
        else:
            self.log.info("No proxy configuration - running without proxy")

    def setup_logging(self):
        """Set up logging to both file and console (conditionally)."""
        os.makedirs("logs", exist_ok=True)
        log_filename = datetime.now().strftime("logs/session_%Y-%m-%d_%H-%M-%S.log")

        logging.basicConfig(
            level=logging.DEBUG if self.debug else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8"),
                logging.StreamHandler() if self.debug else logging.NullHandler(),
            ],
        )

        self.log = logging.getLogger("LoginBot")

    async def human_fill(self, selector, text):
        """Simulate human typing into an input field."""
        await self.page.fill(selector, "")
        for ch in text:
            await self.page.type(selector, ch, delay=random.randint(50, 170))

    def css_escape_tile_id(self, index: int) -> str:
        """Return CSS selector for captcha tile index."""
        s = str(index - 1)
        if len(s) == 1:
            escaped = f"\\3{s}"
        else:
            escaped = f"\\3{s[0]} {s[1]}"
        return f"td#{escaped}.rc-imageselect-tile"

    async def solve_and_verify(self, iframe_locator, instruction_text, grid_type):
        """Solve captcha using 2Captcha and click verify."""
        solver = TwoCaptcha(self.api_key)
        rows, cols = (3, 3) if grid_type == "3x3" else (4, 4)

        self.log.info("Starting CAPTCHA solve attempt...")
        img_locator = iframe_locator.locator(
            f"div.rc-image-tile-wrapper > img.rc-image-tile-{grid_type.replace('x', '')}"
        )

        await img_locator.first.wait_for(state="attached", timeout=15_000)
        src_url = await img_locator.first.get_attribute("src")

        if not src_url:
            self.log.warning("No image found or src attribute missing.")
            return False

        image_data = requests.get(src_url).content
        try:
            image_dir = os.path.dirname(self.image_chache_path)
            os.makedirs(image_dir, exist_ok=True)
            with open(self.image_chache_path, "wb") as f:
                f.write(image_data)
        except IOError as e:
            self.log.error(f"Failed to write image to cache: {e}")
            return False

        try:
            result = solver.grid(
                self.image_chache_path,
                recaptcharows=rows,
                recaptchacols=cols,
                textinstructions=instruction_text,
            )

            result_code = result.get("code", "")
            if not result_code.startswith("click:"):
                self.log.warning(f"Unexpected result format: {result_code}")
                return False

            indexes = [int(x) for x in result_code.replace("click:", "").split("/") if x.isdigit()]
            for index in indexes:
                tile_id = self.css_escape_tile_id(index)
                try:
                    locator = iframe_locator.locator(tile_id)
                    await locator.click()
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                except Exception as e:
                    self.log.warning(f"Failed to click tile {index}: {e}")

            old_url = self.page.url
            await iframe_locator.locator("button#recaptcha-verify-button").click()

            for _ in range(20):
                await asyncio.sleep(0.5)
                new_url = self.page.url
                if new_url != old_url:
                    self.log.info(f"URL changed after verification!")
                    return True
            self.log.warning("URL did not change after verification.")
            return False

        except (ApiException, Exception) as e:
            self.log.error(f"Captcha solving error: {e}")
            return False

    async def download_audio_file(self, audio_url):
        """Download audio file from URL and save to cache."""
        try:
            self.log.info(f"Downloading audio from: {audio_url}")
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            
            # Ensure audio cache directory exists
            audio_dir = os.path.dirname(self.audio_cache_path)
            os.makedirs(audio_dir, exist_ok=True)
            
            with open(self.audio_cache_path, "wb") as f:
                f.write(response.content)
            
            self.log.info(f"Audio saved to: {self.audio_cache_path}")
            return True
        except Exception as e:
            self.log.error(f"Failed to download audio: {e}")
            return False

    async def solve_audio_captcha_with_2captcha(self, audio_file_path):
        """Solve audio captcha using 2captcha library (consistent with image captcha approach)."""
        try:
            solver = TwoCaptcha(self.api_key)
            
            self.log.info("Sending audio captcha to 2captcha using library method...")
            
            # Use TwoCaptcha library's audio method
            result = solver.audio(audio_file_path, lang="en")
            
            self.log.info(f"2captcha audio result: {result}")
            
            # Extract the solution text from result
            solution_text = result.get("code")
            
            if solution_text:
                self.log.info(f"Audio captcha solved: {solution_text}")
                return solution_text
            else:
                self.log.error(f"No solution code in result: {result}")
                return None
            
        except ApiException as e:
            self.log.error(f"2captcha API exception: {e}")
            return None
        except Exception as e:
            self.log.error(f"Error solving audio captcha: {e}")
            import traceback
            self.log.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def solve_audio_captcha(self, iframe_locator):
        """Complete audio captcha solving flow."""
        try:
            # Click the audio button to switch to audio challenge
            self.log.info("Clicking audio button...")
            audio_button = iframe_locator.locator("button#recaptcha-audio-button")
            await audio_button.wait_for(state="visible", timeout=10000)
            await audio_button.click()
            await asyncio.sleep(random.uniform(2, 3))
            
            # Wait for audio challenge to load
            audio_challenge = iframe_locator.locator("div#rc-audio")
            await audio_challenge.wait_for(state="visible", timeout=10000)
            self.log.info("Audio challenge loaded")
            
            # Get the audio download link
            audio_link = iframe_locator.locator("a.rc-audiochallenge-tdownload-link")
            audio_url = await audio_link.get_attribute("href")
            
            if not audio_url:
                self.log.error("Could not find audio download URL")
                return False
            
            # Download the audio file
            if not await self.download_audio_file(audio_url):
                return False
            
            # Solve the audio captcha using 2captcha
            solution_text = await self.solve_audio_captcha_with_2captcha(self.audio_cache_path)
            
            if not solution_text:
                return False
            
            # Enter the solution in the text box
            self.log.info("Entering solution text...")
            audio_input = iframe_locator.locator("input#audio-response")
            await audio_input.fill(solution_text)
            await asyncio.sleep(random.uniform(0.5, 1))
            
            # Click verify button
            self.log.info("Clicking verify button...")
            old_url = self.page.url
            verify_button = iframe_locator.locator("button#recaptcha-verify-button")
            await verify_button.click()
            
            # Check for URL change
            for _ in range(20):
                await asyncio.sleep(0.5)
                new_url = self.page.url
                if new_url != old_url:
                    self.log.info("URL changed after audio verification!")
                    return True
            
            self.log.warning("URL did not change after audio verification.")
            return False
            
        except Exception as e:
            self.log.error(f"Error in audio captcha solving: {e}")
            return False

    async def check_url_change(self, old_url, timeout=10):
        """Wait for URL change for a few seconds."""
        for _ in range(timeout * 2):
            await asyncio.sleep(0.5)
            new_url = self.page.url
            if new_url != old_url:
                self.log.info("URL changed after clicking submit — no captcha required.")
                return True
        return False

    async def handle_captcha(self, captcha_type="audio"):
        """Handle captcha solving loop with support for both image and audio types."""
        iframe_locator = self.page.frame_locator(
            "iframe[title='recaptcha challenge expires in two minutes']"
        )
        self.log.info("Iframe found and attached.")

        if captcha_type == "audio":
            # Try audio captcha solving
            self.log.info("Attempting to solve audio captcha...")
            for attempt in range(5):
                self.log.info(f"--- Audio CAPTCHA Solve Attempt {attempt + 1} ---")
                success = await self.solve_audio_captcha(iframe_locator)
                if success:
                    self.log.info("Audio CAPTCHA solved successfully!")
                    return True
                else:
                    self.log.info(f"Retrying audio CAPTCHA... (Attempt {attempt + 1}/5)")
                    # Reload to get a new audio challenge
                    try:
                        reload_button = iframe_locator.locator("button#recaptcha-reload-button")
                        await reload_button.click()
                        await asyncio.sleep(random.uniform(2, 3))
                    except Exception as e:
                        self.log.warning(f"Failed to reload captcha: {e}")
                    await asyncio.sleep(random.uniform(2, 4))
            
            self.log.error("Failed to solve audio CAPTCHA after multiple attempts.")
            return False
        
        else:
            # Image captcha solving (existing logic)
            for attempt in range(15):
                self.log.info(f"--- Image CAPTCHA Solve Attempt {attempt + 1} ---")

                try:
                    instruction_locator = iframe_locator.locator("div.rc-imageselect-desc-wrapper")
                    await instruction_locator.first.wait_for(state="visible", timeout=10000)
                    instruction_text = (await instruction_locator.inner_text()).strip()
                    self.log.info(f"Instruction text: {instruction_text}")
                    if instruction_text.endswith("Click verify once there are none left.") or instruction_text.endswith("Click verify once there are none left") :
                        await iframe_locator.locator("button#recaptcha-reload-button").click()
                        self.log.info("Reloaded CAPTCHA due to complicated instruction.")
                        await asyncio.sleep(random.uniform(2, 4))
                        continue
                except Exception as e:
                    self.log.warning(f"Could not fetch instruction text: {e}")
                    continue

                img_3x3_locator = iframe_locator.locator(
                    "div.rc-image-tile-wrapper > img.rc-image-tile-33"
                )
                img_4x4_locator = iframe_locator.locator(
                    "div.rc-image-tile-wrapper > img.rc-image-tile-44"
                )

                if await img_3x3_locator.count() > 0:
                    grid_type = "3x3"
                elif await img_4x4_locator.count() > 0:
                    grid_type = "4x4"
                else:
                    self.log.warning("Could not determine grid type. Retrying...")
                    await asyncio.sleep(2)
                    continue

                success = await self.solve_and_verify(iframe_locator, instruction_text, grid_type)
                if success:
                    self.log.info("Image CAPTCHA solved successfully!")
                    return True
                else:
                    self.log.info(f"Retrying image CAPTCHA solve... (Attempt {attempt + 1}/15)")
                    await asyncio.sleep(random.uniform(2, 4))

            self.log.error("Failed to solve image CAPTCHA after multiple attempts.")
            return False

    async def search_companies_via_api(self, query="artificial intelligence", size=100, sort_by="relevance"):
        """
        Search companies using TracXN API directly with browser cookies and headers.
        This is faster than UI-based scraping.
        
        Args:
            query: Search keyword(s) for companies
            size: Number of results to return (max 100 per request)
            sort_by: Sort field (e.g., "relevance", "total_equity_funding")
            
        Returns:
            List of company reference links
        """
        list_of_companies = []
        
        try:
            # Extract cookies from the browser context
            cookies = await self.page.context.cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            self.log.info(f"Extracted {len(cookies)} cookies from browser")
            
            # Log important authentication cookies
            auth_cookies = ['at', 'st', 'wt', 'TID', 'tci']
            for cookie in cookies:
                if cookie['name'] in auth_cookies:
                    self.log.info(f"Auth cookie found: {cookie['name']} = {cookie['value'][:20]}...")
            
            # Get current page URL for referer
            current_url = self.page.url
            self.log.info(f"Current page URL (for referer): {current_url}")
            
            # Verify we're logged in by checking the URL
            if 'platform.tracxn.com' not in current_url or 'login' in current_url.lower():
                self.log.warning(f"May not be properly logged in. Current URL: {current_url}")
            else:
                self.log.info("Appears to be logged in successfully")
            
            # Prepare the API request payload
            payload = {
                "dataset": "query",
                "sort": [{"sortField": sort_by, "order": "DEFAULT"}],
                "filter": {},
                "query": {"companyKeyword": {"query": [query]}},
                "size": size,
                "from": 0
            }
            
            self.log.info(f"API Request Payload: {json.dumps(payload, indent=2)}")
            
            # Prepare headers (dynamically updated from browser)
            headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en;q=0.9,fa-IR;q=0.8,fa;q=0.7,en-US;q=0.6',
                'cache-control': 'no-cache',
                'content-type': 'application/json',
                'origin': 'https://platform.tracxn.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': current_url,
                'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                'x-frontend-app-version': 'portalApp-1763725640953-5.7.3',
                'x-request-source': 'List Page',
                'Cookie': cookie_string
            }
            
            # Make the API request
            api_url = 'https://platform.tracxn.com/api/3.0/companies'
            self.log.info(f"Making POST request to: {api_url}")
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            
            self.log.info(f"API Response Status Code: {response.status_code}")
            self.log.info(f"API Response Headers: {dict(response.headers)}")
            
            # Log response content for debugging
            try:
                response_text = response.text
                self.log.info(f"API Response (first 500 chars): {response_text[:500]}")
            except:
                pass
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # API response saving disabled per user request
            # try:
            #     os.makedirs("api_responses", exist_ok=True)
            #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            #     response_file = f"api_responses/api_response_{query.replace(' ', '_')}_{timestamp}.json"
            #     with open(response_file, 'w', encoding='utf-8') as f:
            #         json.dump(data, f, indent=2, ensure_ascii=False)
            #     self.log.info(f"API response saved to: {response_file}")
            # except Exception as e:
            #     self.log.warning(f"Failed to save API response to file: {e}")
            
            self.log.info(f"API Response JSON keys: {list(data.keys())}")
            
            # Check if response has 'result' key (TracXN API returns result directly, not nested in 'data')
            if 'result' in data:
                results = data['result']
                total_count = data.get('total_count', 0)
                self.log.info(f"Found 'result' key with {len(results)} results (total_count: {total_count})")
                
                # Log first result for debugging
                if len(results) > 0:
                    first_result = results[0]
                    self.log.info(f"First result keys: {list(first_result.keys())}")
                    self.log.info(f"First result sample: {json.dumps(first_result, indent=2)[:500]}...")
                    
                    # Extract company data from the response
                    for company in results:
                        try:
                            # Extract required fields
                            company_id = company.get('id')
                            company_name = company.get('name')
                            domain = company.get('domain', '')
                            
                            # Get tracxnScore (nested object with 'overall' key)
                            tracxn_score = None
                            if 'tracxnScore' in company and isinstance(company['tracxnScore'], dict):
                                tracxn_score = company['tracxnScore'].get('overall')
                            
                            # Get detailedDescription
                            detailed_description = company.get('detailedDescription', '')
                            
                            # Build reference link from company ID and domain (as slug)
                            # Format: /a/d/company/{id}/{domain}
                            if company_id and domain:
                                reference = f"/a/d/company/{company_id}/{domain}"
                                
                                # Create company data dictionary with all required fields
                                company_data = {
                                    'reference': reference,
                                    'id': company_id,
                                    'name': company_name,
                                    'domain': domain,
                                    'tracxnScore': tracxn_score,
                                    'detailedDescription': detailed_description
                                }
                                
                                list_of_companies.append(company_data)
                                self.log.debug(f"Found company: {company_name} (Score: {tracxn_score}, Ref: {reference})")
                            else:
                                self.log.warning(f"Company missing required fields. ID: {company_id}, Domain: {domain}, Name: {company_name}")
                                
                        except Exception as e:
                            self.log.error(f"Error processing company: {e}")
                            continue
                else:
                    self.log.warning("Result array is empty")
            else:
                self.log.warning(f"'result' key not found in response. Available keys: {list(data.keys())}")
                self.log.info(f"Full response: {json.dumps(data, indent=2)[:1000]}")
            
            self.log.info(f"API search returned {len(list_of_companies)} companies for query: '{query}'")
            
        except requests.exceptions.RequestException as e:
            self.log.error(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.log.error(f"Response status: {e.response.status_code}")
                self.log.error(f"Response body: {e.response.text[:500]}")
        except Exception as e:
            self.log.error(f"Error in search_companies_via_api: {e}")
            import traceback
            self.log.error(f"Traceback: {traceback.format_exc()}")
        
        return list_of_companies

    async def search_companies(self, query="artificial intelligence", type="none", sort_by="Total Equity Funding", filter="none", filter_value="2024", return_description=True):
        list_of_companies = []
        await self.page.locator('div.txn--global-search > span.txn--display-flex-row').click()
        await self.human_fill('input#keyword_',query)
        if type == "description":
            await self.page.locator('input[name=selectAll]').click()
            await self.page.locator('input[id=t_selectedFields_companyDescription]').click()
        old_url = self.page.url
        await self.page.get_by_role("button", name="Search", exact=True).click()
        if await self.check_url_change(old_url):
            self.log.info("Search executed successfully.")
            await asyncio.sleep(random.uniform(5*SLEEP_DELAY, 6*SLEEP_DELAY))
            try:
                if filter == "year":
                    # 1. Click the "Founded Year" filter button to open the pop-up
                    self.log.info("Clicking 'Founded Year' filter button...")
                    # This selector targets the specific clickable blue "Founded Year" text
                    await self.page.locator(
                        'div.search-view__quick-filter-button div.txn--text-color-curious-blue:has-text("Founded Year")'
                    ).click()
                    await asyncio.sleep(random.uniform(2*SLEEP_DELAY, 4*SLEEP_DELAY))
                    # 2. Define the popper (pop-up) element to scope our next actions
                    # This makes our selectors for the input and button more reliable
                    popper = self.page.locator('div.popper-component')
                    
                    # Wait for the popper to be visible
                    await popper.wait_for(state="visible", timeout=5000)
                    self.log.info("Filter pop-up is visible.")

                    # 3. Find the input field inside the popper and fill it
                    # We use the placeholder "Enter Keyword" to find it
                    year_input = popper.locator('input[placeholder="Enter Keyword"]')
                    
                    # Assumes 'filter_value' is a variable passed to this function
                    # For example: filter_value = "2025"
                    await year_input.fill(filter_value) 
                    self.log.info(f"Filled year with: {filter_value}")
                    await asyncio.sleep(random.uniform(2*SLEEP_DELAY, 4*SLEEP_DELAY))

                    # 4. Find the "Apply" button inside the popper and click it
                    # Using get_by_role is the most reliable way to find buttons
                    apply_button = popper.get_by_role("button", name="Apply")
                    await apply_button.click()

                    # 5. Wait for the popper to disappear to confirm the action
                    await popper.wait_for(state="hidden", timeout=5000)
                    self.log.info(f"Successfully applied filter '{filter}' with value '{filter_value}'")

            except Exception as e:
                self.log.error(f"Failed to apply filter '{filter}': {e}")
            # try:
            #     if sort_by == "Total Equity Funding":
            #         await self.page.locator('button[title="Total Equity Funding (USD)"]').click()
            #         await asyncio.sleep(random.uniform(1*SLEEP_DELAY, 2*SLEEP_DELAY))
            #         await self.page.locator('li.icon-dropdown-popper__item > span[id="DEFAULT"]').click()
            #     else:
            #         pass
            # except Exception as e:
            #     self.log.error(f"Failed to sort: {e}")
            await asyncio.sleep(random.uniform(2*SLEEP_DELAY, 3*SLEEP_DELAY))
            await self.page.locator('.comp--gridtable__row.txn--compact-companyName').first.click()
            await self.page.keyboard.press('End')
            await asyncio.sleep(random.uniform(1*SLEEP_DELAY, 2*SLEEP_DELAY))
            await self.page.keyboard.press('End')
            await asyncio.sleep(random.uniform(1*SLEEP_DELAY, 2*SLEEP_DELAY))
            await self.page.keyboard.press('End')
            await asyncio.sleep(random.uniform(1*SLEEP_DELAY, 2*SLEEP_DELAY))
            await self.page.keyboard.press('End')
            await asyncio.sleep(random.uniform(1*SLEEP_DELAY, 2*SLEEP_DELAY))
            await self.page.keyboard.press('End')
            await asyncio.sleep(random.uniform(1*SLEEP_DELAY, 2*SLEEP_DELAY))
            rows = self.page.locator('.comp--gridtable__row.txn--compact-companyName')
            for i in range(await rows.count()):
                row = rows.nth(i)
                link = row.locator('a')
                if await link.count() > 0:
                    href = await link.first.get_attribute('href')
                    list_of_companies.append(href)
            if not list_of_companies:
                href = await self.page.locator(".global-search--landing-page-body a").first.get_attribute('href')
                list_of_companies.append(href)
            return list_of_companies
        else:
            self.log.warning("search failed.")
        return list_of_companies
    
    async def open_target_page(self, with_init = True):
        """Initialize browser and navigate to target page"""
        try:
            self.log.info("Launching browser...")
            
            # Configure browser launch options
            launch_options = {"headless": False, "args": ['--password-store=basic']}
            
            # Add proxy configuration if available
            if USE_PROXY:
                self.log.info(f"Using proxy: {PROXY_SERVER}")
                launch_options["proxy"] = {
                    "server": f"http://{PROXY_SERVER}",
                    "username": PROXY_USER,
                    "password": PROXY_PASS
                }
            
            if with_init:
                self.browser = await self.playwright.chromium.launch(**launch_options)
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                self.log.info(f"Navigating to {self.target_url}")
                await self.page.goto(self.target_url, timeout=2 * 60_000)
                self.log.info("Successfully navigated to target page")
            else:
                await self.page.evaluate("window.stop()")
                await self.page.reload(wait_until="domcontentloaded")
                await self.page.evaluate("window.stop()")
                # self.page = await self.context.new_page()

            cookies = await self.context.cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            cookie_string += "; _ga_63RZ0E5CHG=GS2.1.s1765831962$o1$g0$t1765831962$j60$l0$h0; _ga=GA1.1.1509787402.1765831962"
            return cookie_string, True
            
        except PlaywrightTimeoutError as te:
            self.log.error(f"Timeout occurred while opening target page: {te}")
            return False
        except Exception as e:
            self.log.error(f"Unexpected error while opening target page: {e}")
            return False

    async def close(self):
        """Close browser safely"""
        if os.path.exists(self.image_chache_path):
            try:
                os.remove(self.image_chache_path)
            except Exception as e:
                self.log.error(f"Failed to remove image cache file: {e}")
        if os.path.exists(self.audio_cache_path):
            try:
                os.remove(self.audio_cache_path)
            except Exception as e:
                self.log.error(f"Failed to remove audio cache file: {e}")
        try:
            if self.browser:
                await self.browser.close()
                self.log.info("Browser closed.")
            else:
                self.log.info("Browser was not initialized, nothing to close.")
        except Exception as e:
            self.log.error(f"Error closing browser: {e}")
        finally:
            self.browser = None
            self.page = None

    async def get_new_email(self):
        try:
            self.email_inbox = EmailInbox()
            self.email_address = self.email_inbox.get_new_mailbox(domain="illfavoured.com")
        except Exception as e:
            self.log.error(f"Error creating new email inbox: {e}")
            return ""
        return self.email_address.strip()
    
    async def get_verification_code(self):
        try:
            verification_code = self.email_inbox.get_mail(self.email_address, timeout=150)
        except Exception as e:
            self.log.error(f"Error retrieving verification code: {e}")
            return ""
        return verification_code.strip()
    
    async def login(self):
        """Login to TracXN platform and return success status"""
        try:
            # Try to open the target page first
            cookie_string, page_opened = await self.open_target_page()
            if not page_opened:
                self.log.error("Failed to open target page")
                return False
            
            # await self.open_target_page(False)
            # return False

            # Keep the original locator logic exactly
            input_email = await self.get_new_email()
            if not input_email:
                self.log.error("Failed to get email address")
                return False
            
            print("---- cookie ----")
            print(cookie_string)
            print("---- end of cookie ----")
            #------------------
            # captcha_code = calculate_captcha()

            # resp = send_request(input_email, captcha_code, cookie_string)

            # print("---- response ----")
            # print(resp)
            # print("---- end of response ----")

            # if resp is None:
            #     return False
            #------------------
            
            cookie_string, page_opened = await self.open_target_page(False)

            print("---- cookie ----")
            print(cookie_string)
            print("---- end of cookie ----")
                
            email_box_selector = 'input[placeholder="yourname@yourbusiness.com"]'
            await self.human_fill(email_box_selector, input_email)

            await asyncio.sleep(2)
            await self.page.click("button[type='submit']", timeout=10_000)
            self.log.info("Submit button clicked.")
            old_url = self.page.url

            # Check for URL change — skip captcha if it changes
            if await self.check_url_change(old_url):
                self.log.info("Login successful without captcha.")
            # If URL didn't change, continue with captcha solving
            else:
                captcha_success = await self.handle_captcha()
                if not captcha_success:
                    self.log.error("CAPTCHA solving failed")
                    return False
                    
            code = await self.get_verification_code()
            if not code:
                self.log.error("Failed to get verification code")
                return False
                
            if code:
                otp_inputs = await self.page.query_selector_all(
                    'input[aria-label^="Please enter OTP"]'
                )
                if otp_inputs:
                    for i, ch in enumerate(code):
                        if i < len(otp_inputs):
                            await otp_inputs[i].fill(ch)
            self.log.info("verification code filled.")
            await self.page.locator('input[id="userAgreement__userAgreement"]').click(force=True)
            self.log.info("User agreement checkbox clicked.")
            old_url = self.page.url
            await asyncio.sleep(2)
            await self.page.click("button[type='submit']", timeout=10_000)
            self.log.info("Final submit button clicked.")
            if await self.check_url_change(old_url):
                self.log.info("Login successful after submitting verification code.")
                return True
            else:
                self.log.warning("URL did not change after final submit.")
                return False
            
        except PlaywrightTimeoutError as te:
            self.log.error(f"Timeout occurred during login: {te}")
            return False
        except Exception as e:
            self.log.error(f"Unexpected error during login: {e}")
            return False
    
    async def manual_login(self, email: str = None, verification_code: str = None):
        """
        Manual login to TracXN platform using terminal input for email and verification code.
        
        Args:
            email: Email address to use for login (will prompt if not provided)
            verification_code: Verification code (will prompt when needed if not provided)
            
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            # Navigate directly to login page (not signup)
            login_url = "https://tracxn.com/login"
            self.log.info(f"Launching browser and navigating to {login_url}...")
            
            # Configure browser launch options
            launch_options = {"headless": False, "args": ['--password-store=basic']}
            
            # Add proxy configuration if available
            if USE_PROXY:
                self.log.info(f"Using proxy: {PROXY_SERVER}")
                launch_options["proxy"] = {
                    "server": f"http://{PROXY_SERVER}",
                    "username": PROXY_USER,
                    "password": PROXY_PASS
                }
            
            self.browser = await self.playwright.chromium.launch(**launch_options)
            self.page = await self.browser.new_page()
            
            await self.page.goto(login_url, timeout=2 * 60_000)
            self.log.info("Successfully navigated to login page")

            # Get email from terminal if not provided
            if not email:
                self.log.info("Waiting for email input from terminal...")
                # Use asyncio.to_thread to run blocking input() in a thread
                email = await asyncio.to_thread(input, "Enter your TracXN email address: ")
                email = email.strip()
            
            if not email:
                self.log.error("No email address provided")
                return False
                
            self.log.info(f"Using email: {email}")
            
            # Fill in email
            email_box_selector = 'input[placeholder="yourname@yourbusiness.com"]'
            await self.human_fill(email_box_selector, email)

            await asyncio.sleep(2)
            await self.page.click("button[type='submit']", timeout=10_000)
            self.log.info("Submit button clicked, waiting for response...")
            
            # Wait a moment for the page to respond
            await asyncio.sleep(2)
            
            # Check if OTP input page appeared (no CAPTCHA) or if we need to handle CAPTCHA
            try:
                # Try to find OTP input fields with a short timeout
                await self.page.wait_for_selector('input.txn--otp-input', timeout=5000)
                self.log.info("OTP input page loaded successfully (no CAPTCHA)")
            except Exception:
                # OTP inputs not found, check if CAPTCHA appeared
                self.log.info("OTP inputs not immediately visible, checking for CAPTCHA...")
                old_url = self.page.url
                
                # Check for URL change — skip captcha if it changes
                if await self.check_url_change(old_url):
                    self.log.info("Email submitted successfully, waiting for OTP page...")
                    # Wait again for OTP inputs after URL change
                    try:
                        await self.page.wait_for_selector('input.txn--otp-input', timeout=10000)
                        self.log.info("OTP input page loaded after navigation")
                    except Exception as e:
                        self.log.error(f"OTP input fields not found after navigation: {e}")
                        return False
                else:
                    # URL didn't change and no OTP inputs, likely CAPTCHA
                    self.log.info("CAPTCHA detected, attempting to solve...")
                    captcha_success = await self.handle_captcha()
                    if not captcha_success:
                        self.log.error("CAPTCHA solving failed")
                        return False
                    
                    # After solving CAPTCHA, wait for OTP input page
                    try:
                        await self.page.wait_for_selector('input.txn--otp-input', timeout=10000)
                        self.log.info("OTP input page loaded after CAPTCHA")
                    except Exception as e:
                        self.log.error(f"OTP input fields not found after CAPTCHA: {e}")
                        return False
            
            # Get verification code from terminal if not provided
            if not verification_code:
                self.log.info("Waiting for verification code input from terminal...")
                # Use asyncio.to_thread to run blocking input() in a thread
                verification_code = await asyncio.to_thread(input, "Enter the 6-digit verification code from your email: ")
                verification_code = verification_code.strip()
            
            if not verification_code or len(verification_code) != 6:
                self.log.error("Invalid verification code provided (must be 6 digits)")
                return False
            
            self.log.info("Filling in verification code...")
            
            # Get all OTP input fields
            otp_inputs = await self.page.query_selector_all('input.txn--otp-input')
            
            if len(otp_inputs) != 6:
                self.log.error(f"Expected 6 OTP input fields but found {len(otp_inputs)}")
                return False
            
            # Fill each OTP input field with one digit
            for i, digit in enumerate(verification_code):
                if i < len(otp_inputs):
                    await otp_inputs[i].fill(digit)
                    await asyncio.sleep(0.1)  # Small delay between inputs
            
            self.log.info("Verification code filled in all fields")
            await asyncio.sleep(1)
            
            # Click "Verify Code" button
            old_url = self.page.url
            try:
                # Wait for the button to become enabled (it's disabled initially)
                await self.page.wait_for_selector('button[type="submit"]:not([disabled])', timeout=5000)
                await self.page.click('button[type="submit"]', timeout=10_000)
                self.log.info("Verify Code button clicked")
            except Exception as e:
                self.log.error(f"Failed to click Verify Code button: {e}")
                return False
            
            # Wait for navigation after OTP verification
            await asyncio.sleep(3)
            
            # Check if we moved to the next page (possibly user agreement or dashboard)
            if await self.check_url_change(old_url):
                self.log.info("OTP verified successfully, checking for next step...")
                
                # Check if there's a user agreement checkbox on the next page
                try:
                    user_agreement_checkbox = await self.page.query_selector('input[id="userAgreement__userAgreement"]')
                    if user_agreement_checkbox:
                        self.log.info("User agreement page found, clicking checkbox...")
                        await self.page.locator('input[id="userAgreement__userAgreement"]').click(force=True)
                        self.log.info("User agreement checkbox clicked")
                        
                        await asyncio.sleep(2)
                        await self.page.click("button[type='submit']", timeout=10_000)
                        self.log.info("Final submit button clicked")
                        await asyncio.sleep(3)
                except Exception as e:
                    self.log.info(f"No user agreement page or already logged in: {e}")
                
                self.log.info("Login successful!")
                return True
            else:
                self.log.error("OTP verification failed - URL did not change")
                return False
            
        except PlaywrightTimeoutError as te:
            self.log.error(f"Timeout occurred during manual login: {te}")
            return False
        except Exception as e:
            self.log.error(f"Unexpected error during manual login: {e}")
            return False
    
    def is_data_valid(self, data):
        """Check if scraped company data is valid and not empty"""
        if not data or not isinstance(data, list):
            self.log.warning("Data is None or not a list")
            return False
        
        # Check if data has meaningful content
        valid_sections = 0
        for section in data:
            if not isinstance(section, dict):
                continue
            section_name = section.get('section', 'unknown')
            section_data = section.get('data', {})
            
            if section_data and isinstance(section_data, dict):
                # Check if any section has non-empty values
                non_empty_fields = 0
                for key, value in section_data.items():
                    if value and str(value).strip() and str(value).strip().lower() not in ['', 'null', 'none', 'not found', 'n/a']:
                        non_empty_fields += 1
                
                if non_empty_fields > 0:
                    valid_sections += 1
                    self.log.debug(f"Section '{section_name}' has {non_empty_fields} valid fields")
                else:
                    self.log.debug(f"Section '{section_name}' has no valid data")
        
        is_valid = valid_sections > 0
        if is_valid:
            self.log.info(f"Data validation passed: {valid_sections} sections with valid data")
        else:
            self.log.warning(f"Data validation failed: No sections contain meaningful data")
        
        return is_valid
    
    async def navigate_to_page_and_load_all(self, page_url: str, max_scrolls: int = 200):
        """
        Navigate to a specific page URL and scroll to load all companies in the table.
        
        Args:
            page_url: The full URL or relative path to navigate to
            max_scrolls: Maximum number of scroll attempts (default 200 for ~4000 companies)
            
        Returns:
            bool: True if navigation and loading successful, False otherwise
        """
        try:
            # If page_url is not a full URL, make it one
            if not page_url.startswith('http'):
                base_url = 'https://platform.tracxn.com'
                page_url = base_url + page_url if page_url.startswith('/') else base_url + '/' + page_url
            
            self.log.info(f"Navigating to page: {page_url}")
            await self.page.goto(page_url, timeout=2 * 60_000)
            self.log.info("Successfully navigated to target page")
            
            # Wait for the page to load
            await asyncio.sleep(random.uniform(3 * SLEEP_DELAY, 5 * SLEEP_DELAY))
            
            # Find the table/grid container with companies
            # This selector might need adjustment based on the actual page structure
            try:
                # Wait for company rows to appear
                await self.page.wait_for_selector('.comp--gridtable__row.txn--compact-companyName', timeout=20000)
            except Exception as e:
                self.log.warning(f"Company rows not found with primary selector: {e}")
                # Try alternative selector
                try:
                    await self.page.wait_for_selector('.txn--compact-companyName', timeout=10000)
                except Exception as e2:
                    self.log.error(f"Could not find company rows with any selector: {e2}")
                    return False
            
            self.log.info("Starting to scroll and load all companies...")
            
            # Track unique row IDs and extract company references as we scroll
            # Tracxn uses virtualization, so we must extract data immediately as it appears
            seen_row_ids = set()
            company_references = []  # Store company references extracted during scroll
            previous_unique_count = 0
            no_change_count = 0
            scroll_count = 0
            
            # Click on first row to enable keyboard navigation
            try:
                await self.page.locator('.comp--gridtable__row.txn--compact-companyName').first.click()
                await asyncio.sleep(1)
            except Exception as e:
                self.log.warning(f"Could not click first row: {e}")
            
            # Scroll down repeatedly to load all companies
            while scroll_count < max_scrolls:
                # Press End key to scroll to bottom - this loads dynamic content
                await self.page.keyboard.press('End')
                await asyncio.sleep(random.uniform(0.5 * SLEEP_DELAY, 1 * SLEEP_DELAY))
                
                # Also try Page Down for better loading
                await self.page.keyboard.press('PageDown')
                await asyncio.sleep(random.uniform(0.5 * SLEEP_DELAY, 1 * SLEEP_DELAY))
                
                # Additional scroll using JavaScript to ensure all content loads
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(random.uniform(0.3 * SLEEP_DELAY, 0.7 * SLEEP_DELAY))
                
                # Extract company references from currently visible rows
                # Tracxn uses virtualization, so only visible rows are in DOM
                rows = self.page.locator('.comp--gridtable__row.txn--compact-companyName')
                current_visible_count = await rows.count()
                
                # Extract row IDs and company references from visible rows
                for i in range(current_visible_count):
                    try:
                        row = rows.nth(i)
                        row_id = await row.get_attribute('data-walk-through-id')
                        
                        # Only process new rows we haven't seen before
                        if row_id and row_id not in seen_row_ids:
                            seen_row_ids.add(row_id)
                            
                            # Extract company reference immediately
                            # Look for the company name link (should start with /a/d/company/)
                            link = row.locator('a[href^="/a/d/company/"]')
                            if await link.count() > 0:
                                href = await link.first.get_attribute('href')
                                if href and '/a/d/company/' in href:
                                    company_references.append(href)
                                    self.log.debug(f"Extracted reference from {row_id}: {href}")
                    except Exception as e:
                        # Row might have been removed during iteration (virtualization)
                        self.log.debug(f"Error processing row {i}: {e}")
                        continue
                
                current_unique_count = len(seen_row_ids)
                current_refs_count = len(company_references)
                
                if current_unique_count > previous_unique_count:
                    new_rows = current_unique_count - previous_unique_count
                    self.log.info(f"Discovered {current_unique_count} unique companies (scroll {scroll_count + 1}/{max_scrolls}) - +{new_rows} new, {current_refs_count} references extracted")
                    previous_unique_count = current_unique_count
                    no_change_count = 0
                else:
                    no_change_count += 1
                    
                    # If no new companies discovered after 10 consecutive scrolls, we've reached the end
                    if no_change_count >= 10:
                        self.log.info(f"No new companies discovered after 10 scrolls. Total unique companies: {current_unique_count}")
                        break
                
                scroll_count += 1
                
                # Progress update every 20 scrolls
                if scroll_count % 20 == 0:
                    self.log.info(f"Progress: {scroll_count} scrolls completed, {current_unique_count} unique companies discovered, {current_refs_count} references extracted")
            
            # Final count
            self.log.info(f"Finished scrolling! Total unique companies discovered: {len(seen_row_ids)}")
            self.log.info(f"Total company references extracted: {len(company_references)}")
            self.log.info(f"Note: Due to virtualization, only ~{current_visible_count} rows visible in DOM at once")
            
            # Store the company references for later use
            self.company_references = company_references
            
            return True
            
        except Exception as e:
            self.log.error(f"Error navigating to page and loading companies: {e}")
            return False
    
    async def extract_and_scrape_all_companies(self, save_progress_every: int = 50, save_callback=None):
        """
        Scrape all companies using references already extracted during scrolling.
        
        Args:
            save_progress_every: Save progress to log every N companies (default 50)
            save_callback: Optional callback function to save data immediately after scraping each company.
                          Should accept (reference, data) and return True on success, False otherwise.
            
        Returns:
            list: List of dictionaries containing company reference and scraped data
        """
        try:
            # Use company references already extracted during scroll
            if not hasattr(self, 'company_references') or not self.company_references:
                self.log.error("No company references found! Must call navigate_to_page_and_load_all() first")
                return []
            
            company_references = self.company_references
            self.log.info(f"Starting to scrape {len(company_references)} companies...")
            
            # Now scrape each company one by one
            scraped_results = []
            failed_companies = []
            
            for index, ref in enumerate(company_references, 1):
                try:
                    self.log.info(f"Scraping company {index}/{len(company_references)}: {ref}")
                    
                    # Scrape the company
                    data = await self.scrape_company(ref)
                    
                    # Validate the data
                    if data and self.is_data_valid(data):
                        result_entry = {
                            'reference': ref,
                            'data': data,
                            'status': 'success',
                            'saved': False
                        }
                        
                        # Save immediately if callback is provided
                        if save_callback:
                            try:
                                saved = save_callback(ref, data)
                                result_entry['saved'] = saved
                                if saved:
                                    self.log.info(f"Successfully saved company {index}/{len(company_references)}: {ref}")
                            except Exception as e:
                                self.log.error(f"Error in save callback for company {ref}: {e}")
                        
                        scraped_results.append(result_entry)
                        self.log.info(f"Successfully scraped company {index}/{len(company_references)}")
                    else:
                        scraped_results.append({
                            'reference': ref,
                            'data': None,
                            'status': 'invalid_data',
                            'error': 'Scraped data is empty or invalid',
                            'saved': False
                        })
                        failed_companies.append(ref)
                        self.log.warning(f"Invalid data for company {index}/{len(company_references)}: {ref}")
                    
                    # Progress logging
                    if index % save_progress_every == 0:
                        success_count = len([r for r in scraped_results if r['status'] == 'success'])
                        self.log.info(f"Progress: {index}/{len(company_references)} companies processed, {success_count} successful")
                    
                    # Small delay between scrapes to avoid rate limiting
                    await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                    
                except Exception as e:
                    self.log.error(f"Error scraping company {index}/{len(company_references)} ({ref}): {e}")
                    scraped_results.append({
                        'reference': ref,
                        'data': None,
                        'status': 'error',
                        'error': str(e),
                        'saved': False
                    })
                    failed_companies.append(ref)
            
            # Final summary
            success_count = len([r for r in scraped_results if r['status'] == 'success'])
            failed_count = len(failed_companies)
            
            self.log.info(f"Scraping completed! Total: {len(company_references)}, Success: {success_count}, Failed: {failed_count}")
            
            if failed_companies:
                self.log.info(f"Failed companies: {failed_companies[:10]}{'...' if len(failed_companies) > 10 else ''}")
            
            return scraped_results
            
        except Exception as e:
            self.log.error(f"Error extracting and scraping companies: {e}")
            return []
    
    async def scrape_company(self, href):
        """
        Main scraping function for a single company page.
        Navigates to different sections and scrapes the data.

        Args:
            href: The URL path for the company page.
        """
        base_url = 'https://platform.tracxn.com'
        full_url = base_url + href if href.startswith('/') else base_url + '/' + href
        
        # Extract company/investor name from URL path
        # Format: /a/d/company/63fcf60e529803362b2114b4/storybird.ai
        company_name = None
        try:
            path_parts = href.rstrip('/').split('/')
            if len(path_parts) > 0:
                company_name = path_parts[-1]  # Last part is the company name
        except Exception as e:
            self.log.warning(f"Could not extract company name from href {href}: {e}")
        
        await self.page.goto(full_url, timeout=2 * 60_000)
        # investor_or_company = self.page.locator(".txn--comp-inpage-left-nav-item").get_by_text("Portfolio Deepdive")
        if href.startswith('/a/d/investor'):
            
            results = []

            # Ensure the main profile section is expanded to make sub-links clickable
            try:
                profile_tab = self.page.locator('div[title="Profile"]:has(.fa-caret-right)')
                if await profile_tab.is_visible(timeout=5000):
                    await profile_tab.click()
                    self.log.debug("Expanded Profile section.")
                    await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
            except Exception:
                self.log.debug("Profile section already expanded or not found.")
            
            results.append({"section": "company_basic_details", "data": await self.get_company_details()})

            # --- Scrape Key Metrics ---
            await self.navigate_to_section("Key Metrics")
            key_metrics = await self.get_company_key_metrics()
            results.append({"section": "key_metrics", "data": key_metrics})

            # --- Scrape About ---
            await self.navigate_to_section("About")
            about = await self.get_company_about()
            results.append({"section": "about", "data": about})

            # --- Scrape People ---
            # await self.navigate_to_section("People")
            # people_data = await self.get_people_data()
            # results.append({"section": "people", "data": people_data})

            try:
                await self.page.locator(".txn--comp-inpage-left-nav-item").get_by_text("Portfolio Deepdive").click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                # await self.navigate_to_section("Portfolio Leaderboard")
                portfolio_leaderboard = await self.get_portfolio_leaderboard()
                results.append({"section": "portfolio_leaderboard", "data": portfolio_leaderboard})
            except Exception as e:
                self.log.warning(f"Could not navigate to Competitive Landscape section: {e}")
            try:
                await self.page.locator(".txn--comp-inpage-left-nav-item").get_by_text("Incubator").click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))

                program_link = self.page.locator("span[title='Incubator Programs']:visible")
                await program_link.wait_for(state="visible", timeout=10000)
                await program_link.click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                incubator_programs = await self.get_incubator_programs()
                results.append({"section": "incubator_programs", "data": incubator_programs})

                batches_link = self.page.locator("span[title='Incubator Batches']:visible")
                await batches_link.wait_for(state="visible", timeout=10000)
                await batches_link.click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                incubator_batches = await self.get_incubator_batches()
                results.append({"section": "incubator_batches", "data": incubator_batches})

                companies_link = self.page.locator("span[title='Incubated Companies']:visible")
                await companies_link.wait_for(state="visible", timeout=10000)
                await companies_link.click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                incubated_companies = await self.get_incubated_companies()
                results.append({"section": "incubated_companies", "data": incubated_companies})

            except Exception as e:
                self.log.warning(f"Could not navigate to Incubator section: {e}")

            # Add company name to results
            if company_name:
                results.insert(0, {"section": "company_name", "data": company_name})
            
            return results
        if href.startswith('/a/d/company'):
            
            results = []

            # Ensure the main profile section is expanded to make sub-links clickable
            try:
                profile_tab = self.page.locator('div[title="Profile"]:has(.fa-caret-right)')
                if await profile_tab.is_visible(timeout=5000):
                    await profile_tab.click()
                    self.log.debug("Expanded Profile section.")
                    await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
            except Exception:
                self.log.debug("Profile section already expanded or not found.")

            results.append({"section": "company_basic_details", "data": await self.get_company_details()})

            # --- Scrape Key Metrics ---
            await self.navigate_to_section("Key Metrics")
            key_metrics = await self.get_company_key_metrics()
            results.append({"section": "key_metrics", "data": key_metrics})

            # --- Scrape About ---
            await self.navigate_to_section("About")
            about = await self.get_company_about()
            results.append({"section": "about", "data": about})

            # --- Scrape Coverage Areas ---
            await self.navigate_to_section("Coverage Areas")
            coverage_areas = await self.get_coverage_areas()
            results.append({"section": "coverage_areas", "data": coverage_areas})

            # --- Scrape Funding & Investors ---
            await self.navigate_to_section("Funding & Investors")
            funding_and_investors = await self.get_funding_and_investors()
            results.append({"section": "funding_and_investors", "data": funding_and_investors})

            # --- Scrape People ---
            await self.navigate_to_section("People")
            people_data = await self.get_people_data()
            results.append({"section": "people", "data": people_data})

            await self.navigate_to_section("Next Round Investment")
            next_round_data = await self.get_next_round_investment_data()
            results.append({"section": "next_round_investment", "data": next_round_data})
            try:
                await self.page.locator(".txn--comp-inpage-left-nav-item").get_by_text("Competitive Landscape").click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))

                await self.navigate_to_section("Competitor summary")
                competitor_summary = await self.get_competitor_summary()
                results.append({"section": "competitor_summary", "data": competitor_summary})

                await self.navigate_to_section("Competitor List")
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                competitor_list = await self.get_competitor_list()
                results.append({"section": "competitor_list", "data": competitor_list})

                await self.navigate_to_section("Competitor Distribution")
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                competitor_distribution = await self.get_competitor_distribution()
                results.append({"section": "competitor_distribution", "data": competitor_distribution})

                await self.navigate_to_section("Compare Competitors")
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                competitor_comparison_data = await self.get_competitor_comparison_data()
                results.append({"section": "competitor_comparison", "data": competitor_comparison_data})

                await self.navigate_to_section("Funding & Investors in Competition Set")
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                competition_set_funding_data = await self.get_competition_set_funding_data()
                results.append({"section": "competition_set_funding", "data": competition_set_funding_data})
            except Exception as e:
                self.log.warning(f"Could not navigate to Competitive Landscape section: {e}")
            try:
                await self.page.locator(".txn--comp-inpage-left-nav-item").get_by_text("Market Share & Retention").click()
                await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
                self.log.debug("Opened Market Share & Retention section.")
                market_share_data = await self.get_market_share_data()
                results.append({"section": "market_share", "data": market_share_data})
            except Exception as e:
                self.log.warning(f"Could not navigate to Market Share & Retention section: {e}")
            
            # Add company name to results
            if company_name:
                results.insert(0, {"section": "company_name", "data": company_name})
            
            return results

    async def navigate_to_section(self, section_title):
        """
        Navigates to a specific section on the page by clicking the left navigation link.

        Args:
            section_title: The title of the section to navigate to (e.g., "About", "Key Metrics").
        """
        try:
            # Locator for the navigation links based on their title
            nav_link_selector = f'div[role="button"][title="{section_title}"]'
            nav_link = self.page.locator(nav_link_selector)
            await nav_link.wait_for(state="visible", timeout=10000)
            await nav_link.click()
            self.log.info(f"Navigated to section: {section_title}")
            
            # Scroll down to ensure dynamic content loads
            await self.page.keyboard.press('End')
            # Wait for a random delay to mimic human behavior and allow content to load
            await asyncio.sleep(random.uniform(1 * SLEEP_DELAY, 2 * SLEEP_DELAY))
        except Exception as e:
            self.log.warning(f"Could not navigate to section '{section_title}': {e}")
    async def get_company_details(self):
        """
        Extracts the company name, founded year, city, and country from the page header.
        This version is designed to handle multiple DOM variations for location.

        Returns:
            A dictionary containing the company's basic details.
        """
        details = {
            "name": "Not found",
            "founded_year": "Not found",
            "city": "Not found",
            "country": "Not found"
        }
        
        # Wait for the profile card to be visible
        try:
            # Wait for the main profile card container
            await self.page.locator('.txn--dp-new-profile-card').first.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"Company details section not found or timed out: {e}")
            return details # Return default values if section isn't found

        # 1. Extract Company Name
        try:
            # Multiple approaches to find company name
            # Approach 1: Look for link with company path and specific styling
            name_element = self.page.locator('a[href*="/company/"].txn--text-color-bunting.txn--font-medium')
            
            if await name_element.count() > 0:
                name_text = await name_element.first.inner_text()
                details["name"] = name_text.strip()
            else:
                # Approach 2: Look in the profile card title area
                name_element_alt = self.page.locator('.txn--dp-new-profile-card .txn--text-headline a[href*="/company/"]')
                if await name_element_alt.count() > 0:
                    name_text = await name_element_alt.first.inner_text()
                    details["name"] = name_text.strip()
                else:
                    self.log.debug("Company name element not found with any selector.")
        except Exception as e:
            self.log.debug(f"Could not extract company name: {e}")

        # 2. Extract Founded Year
        try:
            # Look for div with title="Founded Year" and extract the year
            year_element = self.page.locator('div[title="Founded Year"].txn--text-color-bunting')
            
            if await year_element.count() > 0:
                year_text = await year_element.first.inner_text()
                # Extract just the year part (e.g., "2000" from "2000|" or "2000 |")
                year_clean = year_text.split('|')[0].strip()
                if year_clean:
                    details["founded_year"] = year_clean
            else:
                self.log.debug("Founded year element not found.")
        except Exception as e:
            self.log.debug(f"Could not extract founded year: {e}")

        # 3. Extract City and Country (Robust logic for multiple cases)
        try:
            # Look for the location container with title="Location"
            location_container = self.page.locator('div[title="Location"]')
            
            if await location_container.count() > 0:
                # Find the div with class txn--comp-multi-location inside
                location_base = location_container.locator('div.txn--comp-multi-location').first
                
                if await location_base.count() > 0:
                    # Get the full text first
                    full_location_text = await location_base.inner_text()
                    
                    # Try to find the country span (in parentheses)
                    country_span = location_base.locator('span.txn--text-color-aluminum')
                    
                    if await country_span.count() > 0:
                        # --- Case 1: "City (Country)" format ---
                        country_text = await country_span.first.inner_text()
                        # Remove parentheses to get country name
                        country_clean = country_text.strip().strip('()')
                        details["country"] = country_clean
                        
                        # Extract city by removing the country part from full text
                        # Also remove the flag icon if present
                        city_text = full_location_text.replace(country_text, "").strip()
                        
                        # Remove any remaining non-city text (like flag icons)
                        if city_text:
                            details["city"] = city_text.strip()
                    else:
                        # --- Case 2: "Country" only format ---
                        # No parentheses found, entire text is likely the country
                        location_clean = full_location_text.strip()
                        
                        if location_clean:
                            details["country"] = location_clean
                            # City remains "Not found" as it wasn't specified
                else:
                    self.log.debug("Location multi-location div not found.")
            else:
                self.log.debug("Location container with title='Location' not found.")
                
        except Exception as e:
            self.log.debug(f"Could not extract location: {e}")

        self.log.info(f"Extracted company details: {details}")
        return details
    async def get_company_key_metrics(self):
        """
        Extracts and saves all the key metrics from the company's Tracxn page.

        Returns:
            A dictionary containing the key metrics.
        """
        key_metrics = {}
        
        # Wait for the key metrics section to be visible
        try:
            key_metrics_section = self.page.locator("#a\\:key-metrics")
            await key_metrics_section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Key Metrics section not found: {e}")
            return key_metrics
        # Get all the metric cards
        metric_cards = key_metrics_section.locator(".txn--common-key-metrics-card")
        
        count = await metric_cards.count()

        for i in range(count):
            card = metric_cards.nth(i)
            try:
                # Extract the title of the metric
                title_element = card.locator(".txn--text-color-bunting.txn--font-12")
                title = await title_element.inner_text()
                title = title.strip()

                # Extract the main value of the metric
                value_element = card.locator(".txn--common-key-metrics-card--stat-value")
                
                # Extract additional details if they exist
                details_element = card.locator(".txn--text-color-monsoon.txn--font-12")
                
                # Check for special cases where data is not available
                not_found_element = card.locator(".txn--text-color-dark-gray.txn--font-12.txn--text-italic")

                if await value_element.count() > 0:
                    value = await value_element.inner_text()
                    value = value.strip()
                    details = ""
                    if await details_element.count() > 0:
                        details = await details_element.inner_text()
                        details = details.strip()
                    key_metrics[title] = {"value": value, "details": details}
                elif await not_found_element.count() > 0:
                    not_found_text = await not_found_element.inner_text()
                    key_metrics[title] = {"value": not_found_text.strip(), "details": ""}
                else:
                    key_metrics[title] = {"value": "Not found", "details": ""}

            except Exception as e:
                self.log.debug(f"Could not process a key metric card: {e}")

        return key_metrics

    async def get_company_about(self):
        """
        Extracts and saves all information from the 'About' section of the company's page,
        including company details, subsidiaries, and associated legal entities.
        
        Returns:
            A dictionary containing the structured about section details.
        """
        try:
            # Main locator for the entire "About" section
            about_section = self.page.locator("#a\\:about")
            await about_section.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"About section not found or timed out: {e}")
            return {"section": "about", "data": {}}

        # Initialize the main data dictionary with default empty values
        about_data = {
            "description": None,
            "sectors": [],
            "company_details": {
                "website": None,
                "social": [],
                "key_people": [],
                "first_covered_on": None,
            },
            "mobile_applications": [],
            "subsidiaries": [],
            "associated_legal_entities": []
        }

        # --- Description ---
        try:
            # A more precise locator for the description paragraph
            desc_element = about_section.locator('div[style*="width: 575px;"] > span > span').first
            about_data['description'] = await desc_element.text_content()
        except Exception as e:
            self.log.debug(f"Could not extract description: {e}")

        # --- Sectors ---
        try:
            sectors_container = about_section.locator('div:has(> .txn--dp-subheader:has-text("Sectors")) + div')
            sectors_elements = sectors_container.locator('.comp-txn-pill')
            for i in range(await sectors_elements.count()):
                sector = await sectors_elements.nth(i).inner_text()
                about_data['sectors'].append(sector.strip())
        except Exception as e:
            self.log.debug(f"Could not extract sectors: {e}")

        # --- Company Details Grid ---
        details_grid = about_section.locator(".txn--common-text-key-metrics-grid-wrapper")
        if await details_grid.count() > 0:
            # Website
            try:
                website_value = details_grid.locator("div:has-text('Website') + div a")
                about_data['company_details']['website'] = await website_value.get_attribute('href')
            except Exception as e:
                self.log.debug(f"Could not extract website: {e}")

            # Social Links
            try:
                social_links_elements = details_grid.locator("div:has-text('Social') + div a")
                for i in range(await social_links_elements.count()):
                    link = await social_links_elements.nth(i).get_attribute('href')
                    about_data['company_details']['social'].append(link)
            except Exception as e:
                self.log.debug(f"Could not extract social links: {e}")

            # Key People
            try:
                people_elements = details_grid.locator("div:has-text('Key People') + div .employeeCard__wrapper")
                for i in range(await people_elements.count()):
                    person_element = people_elements.nth(i)
                    name = await person_element.locator("a").first.inner_text()
                    linkedin = ""
                    linkedin_element = person_element.locator("a:has(i.fa-linkedin-in)")
                    if await linkedin_element.count() > 0:
                        linkedin = await linkedin_element.get_attribute('href')
                    about_data['company_details']['key_people'].append({"name": name.strip(), "linkedin": linkedin})
            except Exception as e:
                self.log.debug(f"Could not extract key people: {e}")
            
            # First Covered On
            try:
                covered_on_value = details_grid.locator("div:has-text('First Covered On') + div")
                about_data['company_details']['first_covered_on'] = await covered_on_value.inner_text()
            except Exception as e:
                self.log.debug(f"Could not extract 'First Covered On' date: {e}")

            # Mobile Applications
            try:
                apps_container = details_grid.locator("div:has-text('Mobile Applications') + div")
                app_elements = apps_container.locator("div:has(a)")
                for i in range(await app_elements.count()):
                    app_element = app_elements.nth(i)
                    app_info = {
                        "name": await app_element.locator("a").inner_text(),
                        "link": await app_element.locator("a").get_attribute("href"),
                        "details": (await app_element.inner_text()).split('(', 1)[-1].replace(')', '')
                    }
                    about_data['mobile_applications'].append(app_info)
            except Exception as e:
                self.log.debug(f"Could not extract mobile applications: {e}")

        # --- Subsidiaries ---
        try:
            subsidiaries_container = about_section.locator('div:has(.txn--dp-subheader:has-text("Subsidiaries")) + div')
            subsidiary_elements = subsidiaries_container.locator("a[title]")
            for i in range(await subsidiary_elements.count()):
                element = subsidiary_elements.nth(i)
                about_data['subsidiaries'].append({
                    "name": await element.get_attribute("title"),
                    "link": await element.get_attribute("href")
                })
        except Exception as e:
            self.log.debug(f"Could not extract subsidiaries: {e}")

        # --- Associated Legal Entities Table ---
        try:
            table = about_section.locator('div.comp--gridtable__wrapper-v2')
            rows = table.locator('div.comp--gridtable__row')
            for i in range(await rows.count()):
                row = rows.nth(i)
                entity_data = {}
                
                # Cells are located by index as their class names are dynamically generated
                cells = row.locator('div.comp--gridtable__row-cell')
                
                # Legal Entity Name, CIN, and Address
                name_cell_texts = await cells.nth(0).all_inner_texts()
                entity_data['legal_entity_name'] = name_cell_texts[0][0] if name_cell_texts and name_cell_texts[0] else None
                entity_data['cin'] = name_cell_texts[0][1] if len(name_cell_texts[0]) > 1 else None
                entity_data['address'] = name_cell_texts[0][2] if len(name_cell_texts[0]) > 2 else None
                
                # Location, Date, Associations
                entity_data['location'] = await cells.nth(1).inner_text()
                entity_data['incorporation_date'] = await cells.nth(2).inner_text()
                entity_data['associated_company'] = await cells.nth(3).inner_text()

                # Financials (Revenue & Net Profit)
                financials_texts = await cells.nth(4).all_inner_texts()
                financials = {}
                for line in financials_texts[0]:
                    if 'Revenue:' in line:
                        financials['revenue'] = line.replace('Revenue:', '').strip()
                    elif 'Net Profit:' in line:
                        financials['net_profit'] = line.replace('Net Profit:', '').strip()
                entity_data['latest_financials'] = financials if financials else None
                
                about_data['associated_legal_entities'].append(entity_data)
        except Exception as e:
            self.log.debug(f"Could not extract associated legal entities: {e}")

        return about_data

    async def get_coverage_areas(self):
        """
        Extracts and saves all the information from the 'Coverage Areas' section.

        Returns:
            A dictionary containing the coverage area details.
        """
        coverage_data = {}
        
        # Wait for the coverage areas section to be visible
        try:
            coverage_section = self.page.locator("#a\\:coverage-areas")
            await coverage_section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Coverage Areas section not found: {e}")
            return coverage_data

        # Extract primary coverage path
        try:
            path_elements = coverage_section.locator("div.txn--flex-align-center > div > div > span a")
            path = []
            for i in range(await path_elements.count()):
                path.append(await path_elements.nth(i).inner_text())
            coverage_data['primary_coverage'] = " > ".join(path)
        except Exception as e:
            coverage_data['primary_coverage'] = None
            self.log.debug(f"Could not extract primary coverage path: {e}")

        # Extract other coverage areas
        other_coverage = {}
        try:
            grid = coverage_section.locator(".txn--common-text-key-metrics-grid-wrapper")
            
            # Get all labels and their corresponding value containers
            labels = await grid.locator("div.txn--font-medium").all()
            
            for label_element in labels:
                label_text = (await label_element.inner_text()).strip()
                # The value is in the next sibling div
                values_container = grid.locator(f"div:has-text('{label_text}') + div")
                value_nodes = values_container.locator(".comp-bmtree-list__node")
                
                values = []
                for i in range(await value_nodes.count()):
                    values.append(await value_nodes.nth(i).inner_text())
                
                other_coverage[label_text] = values
            coverage_data['other_coverage_areas'] = other_coverage
        except Exception as e:
            coverage_data['other_coverage_areas'] = {}
            self.log.debug(f"Could not extract other coverage areas: {e}")

        # Extract Special Flags
        try:
            flags_container = coverage_section.locator("div:has-text('Special Flags') + span")
            flag_elements = flags_container.locator("a")
            flags = []
            for i in range(await flag_elements.count()):
                flags.append((await flag_elements.nth(i).inner_text()).strip())
            coverage_data['special_flags'] = flags
        except Exception as e:
            coverage_data['special_flags'] = []
            self.log.debug(f"Could not extract special flags: {e}")

        return coverage_data

    async def get_funding_and_investors(self):
        """
        Extracts and saves all information from the 'Funding & Investors' section,
        including summary cards, all funding rounds, and the list of investors.

        Returns:
            A dictionary containing structured funding and investor details.
        """
        try:
            # Main locator for the entire "Funding & Investors" section
            funding_section = self.page.locator("#a\\:funding-and-investors")
            await funding_section.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"Funding & Investors section not found or timed out: {e}")
            return {"section": "funding_and_investors", "data": {}}

        # Initialize the main data dictionary
        funding_data = {
            "summary": {},
            "funding_rounds": [],
            "investors": []
        }

        # --- 1. Extract Summary Cards ---
        try:
            summary_cards_data = {}
            summary_cards = funding_section.locator(".txn--common-key-metrics-card")
            for i in range(await summary_cards.count()):
                card = summary_cards.nth(i)
                title = await card.locator("div.txn--font-12").first.inner_text()
                value = await card.locator(".txn--common-key-metrics-card--stat-value").inner_text()
                # The details text is the last div in the card's main content area
                details = await card.locator("div > div").last.inner_text()
                
                # Clean up the key and ensure details are not the same as the value
                title_key = title.strip()
                if title_key:
                    summary_cards_data[title_key] = {
                        "value": value.strip(),
                        "details": details.strip() if details.strip() != value.strip() else "-"
                    }
            funding_data['summary'] = summary_cards_data
        except Exception as e:
            self.log.debug(f"Could not extract funding summary cards: {e}")

        # --- 2. Extract All Funding Rounds Table ---
        try:
            # Using a stable locator based on a unique column header
            funding_table = funding_section.locator('.comp--gridtable-v2:has-text("Round Name")')
            rows = funding_table.locator(".comp--gridtable__row")
            for i in range(await rows.count()):
                row = rows.nth(i)
                cells = row.locator('div.comp--gridtable__row-cell')

                # Extracting data by cell index for simplicity and robustness
                date = await cells.nth(0).inner_text()
                name = await cells.nth(1).inner_text()
                amount = await cells.nth(2).inner_text()
                
                investors_cell = cells.nth(4)
                investor_links = investors_cell.locator("a")
                investors = []
                for j in range(await investor_links.count()):
                    investors.append(await investor_links.nth(j).inner_text())

                funding_data['funding_rounds'].append({
                    "date": date,
                    "name": name,
                    "amount": amount,
                    "investors": investors
                })
        except Exception as e:
            self.log.debug(f"Could not extract funding rounds table: {e}")

        # --- 3. Extract Investors Table ---
        try:
            # **FIX:** The original locator was missing "(s)" in "Representative(s)".
            investors_table = funding_section.locator('.comp--gridtable-v2:has-text("Investor Representative(s)")')
            rows = investors_table.locator(".comp--gridtable__row")
            for i in range(await rows.count()):
                row = rows.nth(i)
                
                # Using more specific locators based on the stable `data-walk-through-id` attribute
                name_cell = row.locator('div[data-walk-through-id$="-cell-name"]')
                lead_cell = row.locator('div[data-walk-through-id$="-cell-lead"]')
                total_cell = row.locator('div[data-walk-through-id$="-cell-total"]')
                first_investment_cell = row.locator('div[data-walk-through-id$="-cell-all-firstInvestedDate"]')
                status_cell = row.locator('div[data-walk-through-id$="-cell-investmentStatus"]')
                
                investor_data = {
                    "name": await name_cell.locator('span[title]').get_attribute('title'),
                    "rounds_lead": await lead_cell.inner_text(),
                    "rounds_total": await total_cell.inner_text(),
                    "first_investment": await first_investment_cell.inner_text(),
                    "status": await status_cell.inner_text(),
                }
                funding_data['investors'].append(investor_data)
        except Exception as e:
            self.log.debug(f"Could not extract investors table: {e}")

        return funding_data

    async def get_people_data(self):
        """
        Extracts and saves all information from the 'People' section.

        This includes employee count statistics, a list of founders and key people,
        and a list of senior management personnel.

        Returns:
            A dictionary containing all extracted data from the people section.
        """
        people_data = {}

        # Define the main locator for the entire "People" section
        try:
            people_section = self.page.locator("#a\\:people")
            await people_section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"People section not found: {e}")
            return people_data
        
        # --- 1. Extract Employee Count Information ---
        employee_count_info = {}
        try:
            # Locate the specific container for the employee count chart and table
            employee_count_container = people_section.locator("div.txn--display-flex-row:has(div.recharts-wrapper)")

            # Extract the source of the data
            source_text = await people_section.locator(":text('Source:') + div").inner_text()
            employee_count_info['source'] = source_text.strip()

            # Extract the latest Year-over-Year growth percentage from the chart's footer
            yoy_growth_text = await employee_count_container.locator(":text('Latest YOY Growth')").inner_text()
            employee_count_info['latest_yoy_growth'] = yoy_growth_text.split('=')[-1].strip()

            # Extract the historical employee count data from the table
            history_table = employee_count_container.locator('.comp--gridtable-v2:has-text("YOY Growth")')
            history_rows = []
            rows = history_table.locator(".comp--gridtable__row")
            for i in range(await rows.count()):
                row = rows.nth(i)
                date = await row.locator('[data-walk-through-id$="-cell-prettyTimestamp"]').inner_text()
                count = await row.locator('[data-walk-through-id$="-cell-value"]').inner_text()
                growth = await row.locator('[data-walk-through-id$="-cell-yoyGrowth"]').inner_text()
                history_rows.append({
                    "date": date.strip(),
                    "employee_count": count.strip(),
                    "yoy_growth": growth.strip()
                })
            employee_count_info['history'] = history_rows

        except Exception as e:
            self.log.debug(f"Could not extract employee count section: {e}")

        people_data['employee_count'] = employee_count_info

        # --- Helper Function to Extract People from Tables ---
        async def _extract_people_from_table(table_locator):
            """A nested helper to parse tables with a consistent structure."""
            people_list = []
            rows = table_locator.locator(".comp--gridtable__row")
            for i in range(await rows.count()):
                row = rows.nth(i)
                try:
                    name_cell = row.locator('[data-walk-through-id$="-cell-name"]')
                    # Check if a profile link exists to get the name
                    if await name_cell.locator("a span").count() > 0:
                        name = await name_cell.locator("a span").inner_text()
                    else: # Fallback for names without a profile link
                        name = await name_cell.inner_text()
                        # Clean the numeric prefix like "4."
                        if '.' in name:
                            name = name.split('.', 1)[-1].strip()


                    linkedin_url = None
                    if await name_cell.locator('a[href*="linkedin.com"]').count() > 0:
                        linkedin_url = await name_cell.locator('a[href*="linkedin.com"]').get_attribute('href')

                    designation = await row.locator('[data-walk-through-id$="-cell-designation"]').inner_text()
                    description = await row.locator('[data-walk-through-id$="-cell-description"]').inner_text()

                    people_list.append({
                        "name": name.strip(),
                        "linkedin_url": linkedin_url,
                        "designation": designation.strip(),
                        "description": description.strip()
                    })
                except Exception as e:
                    self.log.debug(f"Could not extract a person's row data: {e}")
            return people_list

        # --- 2. Extract Founders & Key People Table ---
        try:
            founders_header = people_section.locator("div.txn--dp-subheader:has-text('Founders & Key People')")
            founders_table = founders_header.locator("xpath=./following-sibling::div[1]//div[contains(@class, 'comp--gridtable-v2')]")
            people_data['founders_and_key_people'] = await _extract_people_from_table(founders_table)
        except Exception as e:
            self.log.debug(f"Could not extract Founders & Key People table: {e}")
            people_data['founders_and_key_people'] = []

        # --- 3. Extract Senior Management Table ---
        try:
            management_header = people_section.locator("div.txn--dp-subheader:has-text('Senior Management')")
            management_table = management_header.locator("xpath=./following-sibling::div[1]//div[contains(@class, 'comp--gridtable-v2')]")
            people_data['senior_management'] = await _extract_people_from_table(management_table)
        except Exception as e:
            self.log.debug(f"Could not extract Senior Management table: {e}")
            people_data['senior_management'] = []

        return people_data

    async def get_next_round_investment_data(self):
        """
        Extracts data from the 'Next Round Investment' section.

        This includes funding benchmarks based on selected filters and a categorized
        list of probable next round investors.

        Returns:
            A dictionary containing the scraped benchmark and investor data.
        """
        next_round_data = {}
        
        # Locate the main section using its unique ID
        try:
            section = self.page.locator("#a\\:next-round-investment")
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Next Round Investment section not found: {e}")
            return next_round_data

        # --- 1. Extract Next Round Funding Benchmarks ---
        try:
            benchmarks_data = {}
            benchmarks_section = section.locator(":has-text('Next Round Funding Benchmarks')").first

            # Extract current filter values
            filters = {}
            filter_container = benchmarks_section.locator(".txn--display-flex-row:has-text('View:')")
            
            # Helper to safely extract filter text
            async def get_filter_value(label):
                try:
                    return await filter_container.locator(f":text('{label}') + div .comp--dropdown__selected-text").get_attribute('title')
                except Exception:
                    return None

            filters['view'] = await get_filter_value('View:')
            filters['sectors'] = await get_filter_value('Sectors:')
            filters['locations'] = await get_filter_value('Locations:')
            filters['period'] = await get_filter_value('Period:')
            benchmarks_data['filters'] = filters

            # Extract benchmark table data
            table_rows = []
            table = benchmarks_section.locator(".comp--gridtable-v2")
            rows = table.locator(".comp--gridtable__row")
            for i in range(await rows.count()):
                row = rows.nth(i)
                # Helper to parse complex cells with a main value and subtext
                async def parse_value_cell(cell_locator):
                    main_value = await cell_locator.locator(".txn--font-bold").inner_text()
                    sub_text = ""
                    if await cell_locator.locator(".txn--font-10").count() > 0:
                        sub_text = await cell_locator.locator(".txn--font-10").inner_text()
                    return {"value": main_value.strip(), "details": sub_text.strip()}
                
                round_name = await row.locator('[data-walk-through-id$="-cell-round"]').inner_text()
                round_size = await parse_value_cell(row.locator('[data-walk-through-id$="-cell-roundSize"]'))
                pre_money_valuation = await parse_value_cell(row.locator('[data-walk-through-id$="-cell-preMoneyValuation"]'))
                revenue_multiple = await row.locator('[data-walk-through-id$="-cell-fundingMultiple"]').inner_text()
                time_to_round = await parse_value_cell(row.locator('[data-walk-through-id$="-cell-timeToRound"]'))

                table_rows.append({
                    "round": round_name.strip(),
                    "median_round_size": round_size,
                    "median_pre_money_valuation": pre_money_valuation,
                    "median_revenue_multiple": revenue_multiple.strip(),
                    "median_time_to_round": time_to_round
                })
            benchmarks_data['rounds'] = table_rows
            next_round_data['funding_benchmarks'] = benchmarks_data
        except Exception as e:
            self.log.debug(f"Could not extract next round funding benchmarks: {e}")
            next_round_data['funding_benchmarks'] = {}


        # --- 2. Extract Probable Next Round Investors ---
        try:
            investors_data = {}
            investors_section = section.locator("[data-metrics-sub-feature='Next Round Investor']")

            # Extract summary cards
            summary = {}
            cards = investors_section.locator(".txn--common-key-metrics-card")
            for i in range(await cards.count()):
                card = cards.nth(i)
                title = await card.locator(".txn--font-12 .txn--text-truncate").inner_text()
                value = await card.locator(".txn--common-key-metrics-card--stat-value").inner_text()
                summary[title.strip()] = int(value.strip())
            investors_data['summary'] = summary

            # Extract categorized lists of investors
            investor_lists = {}
            category_headers = investors_section.locator(".txn--background-color-black-haze")
            for i in range(await category_headers.count()):
                header = category_headers.nth(i)
                category_title = await header.inner_text()
                
                # The investor cards are in the next sibling div
                investor_container = header.locator("xpath=./following-sibling::div[1]")
                investor_cards = investor_container.locator(".bvcard__wrapper")
                
                category_investors = []
                for j in range(await investor_cards.count()):
                    card = investor_cards.nth(j)
                    name = await card.locator(".bvcard__title").get_attribute('title')
                    meta = await card.locator(".bvcard__meta-info").inner_text()
                    score_text = await card.locator(".comp-score__number p").inner_text()

                    category_investors.append({
                        "name": name.strip(),
                        "meta": meta.strip(),
                        "score": int(score_text.strip())
                    })
                investor_lists[category_title.strip()] = category_investors
            investors_data['investor_lists'] = investor_lists
            next_round_data['probable_investors'] = investors_data
        except Exception as e:
            self.log.debug(f"Could not extract probable investors: {e}")
            next_round_data['probable_investors'] = {}

        return next_round_data
    
    async def get_competitor_summary(self):
        """
        Extracts the data from the competitor summary section.

        This includes the summary text, the total number of competitors, and the
        company's rank in different categories like Overall, Size, and Execution.

        Returns:
            A dictionary containing the competitor summary and ranks.
        """
        competitor_data = {}

        # Locate the main section by its unique ID
        try:
            section = self.page.locator("#a\\:competitor-summary")
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Competitor Summary section not found: {e}")
            return competitor_data
        try:
            # --- 1. Extract Summary Text and Competitor Count ---
            header_text_locator = section.locator(".comp-txn-panel__title")
            header_text = await header_text_locator.inner_text()
            competitor_data['summary_text'] = header_text.strip()

            # Use regular expression to find the number of competitors in the text
            match = re.search(r'\d+', header_text)
            if match:
                competitor_data['total_competitors'] = int(match.group(0))
            else:
                competitor_data['total_competitors'] = None

            # --- 2. Extract All Rank Cards ---
            ranks = {}
            # Locate all the metric cards within the section
            rank_cards = section.locator(".txn--common-key-metrics-card")
            
            for i in range(await rank_cards.count()):
                card = rank_cards.nth(i)
                
                # Extract the title of the rank (e.g., "Overall Rank")
                title = await card.locator(".txn--font-12").inner_text()
                
                # Extract the rank value (e.g., "4th")
                value = await card.locator("span").inner_text()
                
                ranks[title.strip()] = value.strip()
                
            competitor_data['ranks'] = ranks

        except Exception as e:
            self.log.debug(f"Could not extract competitor summary section: {e}")
            # Ensure a default structure is returned on error
            competitor_data['summary_text'] = "Error extracting data."
            competitor_data['total_competitors'] = None
            competitor_data['ranks'] = {}

        return competitor_data

    async def get_competitor_list(self):
        """
        Extracts the detailed list of competitors from the main table.

        This function captures the title, currently active view filters (like 'Active'),
        and then iterates through the competitor table to scrape data for each company.

        Returns:
            A dictionary containing the title, filters, and a list of competitor details.
        """
        competitor_data = {}

        # Locate the main section for the competitor list
        try:
            section = self.page.locator("#a\\:competitor-list")
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Competitor List section not found: {e}")
            return competitor_data
        try:
            # --- 1. Extract Title ---
            title = await section.locator(".comp-txn-panel__title").inner_text()
            competitor_data['title'] = title.strip()

            # --- 2. Extract Active View Filters ---
            active_filters = []
            # Find all checked checkboxes and get their associated label text
            filter_labels = section.locator("input[type='checkbox']:checked + label")
            for i in range(await filter_labels.count()):
                label_text = await filter_labels.nth(i).inner_text()
                active_filters.append(label_text.strip())
            competitor_data['active_filters'] = active_filters

            # --- 3. Extract Competitor Table Data ---
            competitors_list = []
            table = section.locator(".comp--gridtable-v2")
            rows = table.locator(".comp--gridtable__row")

            for i in range(await rows.count()):
                row = rows.nth(i)
                try:
                    # The 'Name' cell contains both rank and name
                    name_cell = row.locator('[data-walk-through-id$="-cell-name"]')
                    
                    rank_text = await name_cell.locator("span.txn--margin-right-16").inner_text()
                    rank = int(rank_text.replace('.', '').strip())
                    
                    # The company name is in the first link with a specific class
                    name = await name_cell.locator("a.txn--text-truncate").first.inner_text()
                    
                    # Extract data from the other cells using their specific locators
                    score = await row.locator('[data-walk-through-id$="-cell-tracxnScore"]').inner_text()
                    location = await row.locator('[data-walk-through-id$="-cell-locations"]').inner_text()
                    year = await row.locator('[data-walk-through-id$="-cell-foundedYear"]').inner_text()
                    stage = await row.locator('[data-walk-through-id$="-cell-stage"]').inner_text()
                    equity = await row.locator('[data-walk-through-id$="-cell-totalEquityFunding"]').inner_text()
                    description = await row.locator('[data-walk-through-id$="-cell-shortDescription"]').inner_text()
                    
                    competitors_list.append({
                        "rank": rank,
                        "name": name.strip(),
                        "tracxn_score": int(score.strip()),
                        "location": location.strip(),
                        "year": int(year.strip()),
                        "company_stage": stage.strip(),
                        "total_equity": equity.strip(),
                        "description": description.strip()
                    })
                except Exception as e:
                    self.log.debug(f"Could not parse data for a competitor row: {e}")
            
            competitor_data['competitors'] = competitors_list

        except Exception as e:
            self.log.debug(f"Could not extract the competitor list section: {e}")
            # Return a default empty structure on failure
            competitor_data = {
                'title': 'Error extracting data.',
                'active_filters': [],
                'competitors': []
            }
        
        return competitor_data

    async def get_competitor_distribution(self):
        """
        Extracts data from the competitor distribution charts.

        This includes the distribution of competitors by location and by stage
        (e.g., Minicorn, Soonicorn, Acquired).

        Returns:
            A dictionary containing data for both distribution charts.
        """
        distribution_data = {}

        # Locate the main section containing both charts using its unique ID
        try:
            section = self.page.locator("#a\\:competitor-distribution")
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Competitor Distribution section not found: {e}")
            return distribution_data
        
        # Helper function to parse the common structure of the bar charts
        async def _parse_bar_chart(svg_container):
            chart_data = {}
            try:
                # More specific locators targeting text elements within the chart's SVG structure
                y_axis_labels = svg_container.locator("g.recharts-yAxis g.recharts-cartesian-axis-tick text")
                value_labels = svg_container.locator("g.recharts-bar g.recharts-label-list text")
                
                count = await y_axis_labels.count()
                
                # Ensure the number of labels and values match before processing
                if count == 0:
                    self.log.debug("No chart labels found in the specified container.")
                    return {}
                if count != await value_labels.count():
                    self.log.debug("Mismatch between chart axis labels and value labels.")
                    return {}

                for i in range(count):
                    # Use text_content() for SVG elements, which is more reliable than inner_text()
                    key = await y_axis_labels.nth(i).text_content()
                    value = await value_labels.nth(i).text_content()
                    
                    # Clean the key by removing ellipses and asterisks
                    clean_key = key.replace('..', '').replace('*', '').strip()
                    # Ensure value is not empty before converting to int
                    if value and value.strip().isdigit():
                        chart_data[clean_key] = int(value.strip())
                    
            except Exception as e:
                self.log.debug(f"Could not parse competitor distribution bar chart: {e}")
                
            return chart_data

        try:
            # --- 1. Parse "Top active competitors by Location" chart ---
            location_chart_svg = section.locator("#compsByGeo-cdp_comp_year_graph")
            distribution_data['by_location'] = await _parse_bar_chart(location_chart_svg)

            # --- 2. Parse "Distribution of Top Competitors" chart ---
            stage_chart_svg = section.locator("#topComps-cdp_comp_year_graph")
            distribution_data['by_stage'] = await _parse_bar_chart(stage_chart_svg)
            
            # --- 3. Extract the note below the second chart ---
            # FIX: Use :text() for an exact match instead of :text-matches() for a regex match.
            note_locator = section.locator("div:text('* Anomali is in Soonicorn')")
            if await note_locator.count() > 0:
                note_text = await note_locator.inner_text()
                distribution_data['note'] = note_text.replace('*', '').strip()
            else:
                distribution_data['note'] = None

        except Exception as e:
            self.log.debug(f"Could not extract competitor distribution section: {e}")
            # Return a default empty structure on failure
            distribution_data = {
                'by_location': {},
                'by_stage': {},
                'note': None
            }

        return distribution_data

    async def get_competitor_comparison_data(self):
        """
        Extracts all data from the "Compare Competitors" section.

        This includes data from the funding bar chart, funding scatter plot,
        employee count line chart, and the detailed comparison table.

        Returns:
            A dictionary containing all the comparison data.
        """
        comparison_data = {}
        
        # Locate the main section for all competitor comparisons
        try:
            section = self.page.locator("#a\\:compare-competitors")
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Compare Competitors section not found: {e}")
            return comparison_data
        try:
            # --- 2. Extract Chart Data ---
            charts_data = {}

            # 2a. Top Competitors By Funding (Bar Chart)
            try:
                funding_bar_chart = section.locator("div.txn--flex-1").filter(has_text="Top Competitors By Funding").first
                bar_chart_data = {}
                # FIX: Use text_content() for SVG text elements and a more specific locator
                y_labels = funding_bar_chart.locator(".recharts-yAxis .recharts-cartesian-axis-tick g text")
                value_labels = funding_bar_chart.locator(".recharts-label-list text")
                for i in range(await y_labels.count()):
                    company = await y_labels.nth(i).text_content()
                    total_funding = await value_labels.nth(i).text_content()
                    bar_chart_data[company.replace('..', '').strip()] = total_funding.strip()
                charts_data['funding_bar_chart'] = bar_chart_data
            except Exception as e:
                self.log.debug(f"Could not parse funding bar chart: {e}")
                charts_data['Top_Competitors_By_Funding_chart'] = {}

            comparison_data['charts'] = charts_data
            
           # --- 3. Extract Detailed Comparison Table (FINAL FIX) ---
            table_data = {'metrics': {}}
            try:
                table = section.locator(".comp--gridtable-v2:has-text('Basic Details')")
                await table.wait_for(state="visible", timeout=10000)

                # Get company names from column headers (skipping the first "Metrics" column)
                headers = table.locator(".comp--gridtable__column-cell")
                companies = []
                for i in range(1, await headers.count()):
                    company_name = await headers.nth(i).locator(".comp--Multi-line-truncate--webkit-line-clamp").inner_text()
                    companies.append(company_name.strip())
                table_data['companies'] = companies
                
                rows = table.locator(".comp--gridtable__row")
                current_category = ""
                for i in range(await rows.count()):
                    row = rows.nth(i)
                    
                    # Check if it's a category header row
                    if await row.locator(".comp--gridtable__row-cell-highlight").count() > 0:
                        category_p = row.locator("p[title]")
                        if await category_p.count() > 0:
                            current_category = (await category_p.get_attribute("title")).strip()
                            table_data['metrics'][current_category] = {}
                    # It's a standard metric data row
                    else:
                        metric_p = row.locator("[class*='metricName'] p[title]")
                        if await metric_p.count() > 0 and current_category:
                            metric_name = (await metric_p.get_attribute("title")).strip()
                            
                            metric_values = {}
                            all_cells_in_row = row.locator(".comp--gridtable__row-cell")
                            
                            for j, company in enumerate(companies):
                                cell = all_cells_in_row.nth(j + 1)
                                data = {}
                                final_value = None

                                # FIX: Use a more specific locator for the change span to avoid ambiguity.
                                # This targets the span with the specific color class (like 'txn--text-color-fern').
                                value_div = cell.locator("div.txn--text-body")
                                change_span = cell.locator("span[class*='txn--text-color-']:has(i[class*='fa-caret'])")
                                date_span = cell.locator("span.txn--text-color-dark-gray")
                                extra_span = cell.locator("div:has-text('[+]')")

                                full_text = (await cell.text_content()).strip()
                                final_value = full_text

                                if full_text and full_text != "-":
                                    value_text = await value_div.text_content() if await value_div.count() > 0 else None
                                    change_text = await change_span.text_content() if await change_span.count() > 0 else None
                                    date_text = await date_span.text_content() if await date_span.count() > 0 else None
                                    extra_text = await extra_span.text_content() if await extra_span.count() > 0 else None

                                    # PRIORITY 1: Cell with a dedicated value div (e.g., Latest Revenue)
                                    if value_text:
                                        data['value'] = value_text.strip()
                                        if change_text:
                                            data['change'] = change_text.strip()
                                        if date_text:
                                            data['date'] = date_text.strip().replace("as on ", "")
                                        final_value = data
                                    # PRIORITY 2: Cell with only a change indicator (e.g., CAGR)
                                    elif change_text:
                                        data['value'] = change_text.strip()
                                        final_value = data
                                    # PRIORITY 3: Cell with extra bracketed info (e.g., Investors)
                                    elif extra_text:
                                        main_value = full_text.replace(extra_text, "").strip()
                                        data['value'] = main_value
                                        data['extra'] = extra_text.strip()
                                        final_value = data
                                    # PRIORITY 4: Any other simple text that should be in a dict
                                    else:
                                        final_value = {'value': full_text}

                                metric_values[company] = final_value
                            
                            table_data['metrics'][current_category][metric_name] = metric_values

            except Exception as e:
                self.log.debug(f"Could not parse competitor comparison table: {e}")
                table_data = {'metrics': {}, 'companies': []}

            comparison_data['comparison_table'] = table_data

        except Exception as e:
            self.log.debug(f"Could not extract 'Compare Competitors' section: {e}")
            return {}
            
        return comparison_data

    async def get_competition_set_funding_data(self):
        """
        Extracts data from the 'Funding & Investors in Competition Set' section.

        This includes investment trends over time, a list of recent funding rounds,
        and a table of top investors in the competitive landscape.

        Returns:
            A dictionary containing all extracted data from this section.
        """
        competition_funding_data = {}
        
        # Locate the main section by its ID
        try:
            section = self.page.locator("#a\\:funding-and-investors-in-competition-set")
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Funding & Investors in Competition Set section not found: {e}")
            return competition_funding_data
        try:
            # --- 1. Investment Trends Chart ---
            trends_data = []
            try:
                trends_chart = section.locator(":has-text('Investment Trends')").first
                data_table = trends_chart.locator(".chart--data-open .comp--gridtable-v2")
                rows = data_table.locator(".comp--gridtable__row")
                for i in range(await rows.count()):
                    row = rows.nth(i)
                    year = await row.locator("[data-walk-through-id$='-cell-prettyTimestamp']").inner_text()
                    rounds = await row.locator("[data-walk-through-id*='_competitorsFundingRounds_line']").inner_text()
                    amount = await row.locator("[data-walk-through-id*='_competitorsFundingAmount_bar']").inner_text()
                    
                    trends_data.append({
                        "year": (year.strip()),
                        "funding_rounds": (rounds.strip()),
                        "total_equity_funding_usd": (amount.replace(',', '').strip())
                    })
            except Exception as e:
                self.log.debug(f"Could not parse investment trends chart data: {e}")
            competition_funding_data['investment_trends_in_competing_markets'] = trends_data

            # --- 2. Recent Funding Rounds Table ---
            recent_rounds = []
            try:
                # FIX: Use a precise locator to isolate the correct panel.
                # This finds a panel that HAS 'Recent Funding Rounds' but does NOT have 'Investment Trends',
                # which excludes the larger parent container that was causing the error.
                rounds_panel = self.page.locator(
                    ".comp-txn-panel:has-text('Recent Funding Rounds'):not(:has-text('Investment Trends'))"
                )

                # Click the header of this specific panel to expand it
                await rounds_panel.locator(".comp-txn-panel__header").click()
                
                # The table is inside this specific panel
                rounds_table = rounds_panel.locator(".comp--gridtable__wrapper-v2")
                await rounds_table.wait_for(state="visible", timeout=5000)

                rows = rounds_table.locator(".comp--gridtable__row")
                for i in range(await rows.count()):
                    row = rows.nth(i)
                    date = await row.locator("[data-walk-through-id$='-cell-fundingDate']").inner_text()
                    company = await row.locator("[data-walk-through-id$='-cell-companyDetails'] a").inner_text()
                    round_type = await row.locator("[data-walk-through-id$='-cell-name']").inner_text()
                    amount = await row.locator("[data-walk-through-id$='-cell-amount']").inner_text()

                    investor_cell = row.locator("[data-walk-through-id$='-cell-investorList']")
                    investors = []
                    
                    if await investor_cell.inner_text() != "-":
                        investor_links = investor_cell.locator("a")
                        investors = [await link.inner_text() for link in await investor_links.all()]
                        if await investor_cell.locator("i").count() > 0:
                            more_text = await investor_cell.locator("i").inner_text()
                            investors.append(more_text.strip())

                    recent_rounds.append({
                        "date": date.strip(),
                        "company": company.strip(),
                        "round": round_type.strip(),
                        "amount": amount.strip(),
                        "investors": [inv.strip() for inv in investors]
                    })
            except Exception as e:
                self.log.debug(f"Could not parse recent funding rounds table: {e}")
            competition_funding_data['recent_funding_rounds_in_competition_set'] = recent_rounds

            # --- 3. Investors in Competition Set Table ---
            top_investors = []
            try:
                # Using a similar specific locator for the Investors panel
                investors_panel = self.page.locator(
                    ".comp-txn-panel:has-text('Investors in Anomali'):not(:has-text('Recent Funding Rounds'))"
                )
                investors_table = investors_panel.locator(".comp--gridtable-v2")
                rows = investors_table.locator(".comp--gridtable__row")

                for i in range(await rows.count()):
                    row = rows.nth(i)
                    name_cell = row.locator("[data-walk-through-id$='-cell-name']")
                    rank = await name_cell.locator("span").first.inner_text()
                    name = await name_cell.locator("a > div").last.inner_text()
                    
                    rounds_count = await row.locator("[data-walk-through-id$='-cell-investmentsCount']").inner_text()
                    
                    portfolio_cell = row.locator("[data-walk-through-id$='-cell-portfoliocompanies']")
                    company_links = portfolio_cell.locator("a span")
                    portfolio = [await link.inner_text() for link in await company_links.all()]
                    
                    location = await row.locator("[data-walk-through-id$='-cell-locations']").inner_text()
                    inv_type = await row.locator("[data-walk-through-id$='-cell-investorType']").inner_text()
                    score = await row.locator(".comp-score__number p").inner_text()

                    top_investors.append({
                        "rank": (rank.replace('.', '').strip()),
                        "name": name.strip(),
                        "rounds_count": rounds_count.strip(),
                        "portfolio_companies": [p.strip() for p in portfolio],
                        "location": location.strip(),
                        "type": inv_type.strip(),
                        "score": (score.strip())
                    })
            except Exception as e:
                self.log.debug(f"Could not parse investors in competition set table: {e}")
            competition_funding_data['top_investors'] = top_investors

        except Exception as e:
            self.log.debug(f"Could not extract 'Funding & Investors in Competition Set' section: {e}")
            return {}
            
        return competition_funding_data

    async def get_market_share_data(self):
        """
        Extracts data from the Market Share section.

        This includes summary metrics, the latest market share distribution from the
        doughnut chart, and the detailed time-series data from the table view.

        Returns:
            A dictionary containing all scraped market share information.
        """
        market_share_data = {}
        
        # Locate the main section panel
        try:
            section = self.page.locator(".comp-txn-panel__body").first
            await section.wait_for(state="visible")
        except Exception as e:
            self.log.error(f"Market Share section not found: {e}")
            return market_share_data
        try:
            # --- 1. Extract Summary Cards ---
            summary_data = {}
            try:
                summary_container = section.locator("div.txn--common-key-metrics-wrapper-box")
                cards = summary_container.locator(".txn--common-key-metrics-card")
                
                for i in range(await cards.count()):
                    card = cards.nth(i)
                    # Handles cases where info icon is part of the title
                    title_element = card.locator(".txn--font-12 .txn--text-truncate")
                    title = (await title_element.inner_text()).split('\n')[0]
                    value = await card.locator(".txn--common-key-metrics-card--stat-value").inner_text()
                    
                    summary_data[title.strip()] = value.strip()

                    # Special handling for "Latest Market Share" to get the MOM change
                    if "Latest Market Share" in title:
                        if await card.locator(".txn--text-color-monsoon").count() > 0:
                            mom_change = await card.locator(".txn--text-color-monsoon").inner_text()
                            summary_data["Latest Market Share MOM"] = mom_change.strip()
            except Exception as e:
                self.log.debug(f"Could not parse market share summary cards: {e}")
            market_share_data['summary'] = summary_data

            # --- 3. Extract Market Share over time (Table View) ---
            over_time_data = {}
            try:
                # Find the container for the "Market Share over time" section
                

                # Click the "Table" button to ensure the table is visible
                table_button = section.get_by_role("button", name=" Table")
                await table_button.click()
                
                # Wait for the table wrapper to be rendered
                table_wrapper = section.locator(".comp--gridtable__wrapper-v2")
                await table_wrapper.wait_for(state="visible", timeout=5000)

                # Get header columns (months), skipping the first "Competitors" header
                header_elements = table_wrapper.locator(".comp--gridtable__column-cell .txn--font-medium")
                month_headers = (await header_elements.all_inner_texts())[1:]

                # Get all data rows
                rows = table_wrapper.locator(".comp--gridtable__row")
                for i in range(await rows.count()):
                    row = rows.nth(i)
                    
                    # First cell in the row is the company name
                    company_name = await row.locator(".comp--gridtable__row-cell").first.inner_text()
                    company_data = {}
                    
                    # Subsequent cells are the monthly data points
                    data_cells = row.locator(".comp--gridtable__row-cell")
                    
                    # Iterate through months and map them to the corresponding cell value
                    for j, month in enumerate(month_headers):
                        # Add 1 to j because data_cells includes the company name cell
                        cell_value = await data_cells.nth(j + 1).inner_text()
                        company_data[month] = cell_value.strip()
                        
                    over_time_data[company_name.strip()] = company_data
            
            except Exception as e:
                self.log.debug(f"Could not parse market share over time table: {e}")
            
            market_share_data['market_share_over_time'] = over_time_data

        except Exception as e:
            self.log.debug(f"Could not extract 'Market Share' section: {e}")
            return {}
            
        return market_share_data



    async def get_portfolio_leaderboard(self):
        """
        Extracts the detailed list of investments from the main table,
        capturing all available columns.

        This function iterates through the investment table rows and scrapes
        data for each company listed using their specific data-walk-through-id
        attributes for each cell.

        Returns:
            A list of dictionaries, where each dictionary contains
            the full details for one company.
        """
        investments_list = []

        # Locate the main table wrapper
        try:
            # This selector comes from your provided DOM
            table = self.page.locator(".comp--gridtable-v2").first
            await table.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"Investment table not found: {e}")
            return investments_list

        try:
            # Get all rows
            rows = table.locator(".comp--gridtable__row")
            row_count = await rows.count()
            self.log.info(f"Found {row_count} rows to scrape.")

            for i in range(row_count):
                row = rows.nth(i)
                company_data = {}
                
                try:
                    # --- Scrape data for each column based on its unique ID ---
                    
                    # 1. Company Name (and Rank)
                    name_cell = row.locator('[data-walk-through-id$="-cell-name"]')
                    rank_text = await name_cell.locator(".comp--gridtable__row-serial-number").inner_text()
                    company_data["rank"] = int(rank_text.replace('.', '').strip())
                    company_data["company_name"] = await name_cell.locator("a.txn--text-truncate").first.inner_text()

                    # 2. Tracxn Score
                    score_text = await row.locator('[data-walk-through-id$="-cell-tracxnScore"] p').inner_text()
                    company_data["tracxn_score"] = int(score_text.strip())

                    # 3. Portfolio Type
                    company_data["portfolio_type"] = (await row.locator('[data-walk-through-id$="-cell-portfolioType"]').inner_text()).strip()

                    # 4. Founded Year
                    year_text = await row.locator('[data-walk-through-id$="-cell-foundedYear"]').inner_text()
                    company_data["founded_year"] = int(year_text.strip())

                    # 5. Location
                    company_data["location"] = (await row.locator('[data-walk-through-id$="-cell-locations"]').inner_text()).strip()

                    # 6. Stage
                    company_data["stage"] = (await row.locator('[data-walk-through-id$="-cell-stage"]').inner_text()).strip()

                    # 7. Investment Status
                    company_data["investment_status"] = (await row.locator('[data-walk-through-id$="-cell-investmentStatus"]').inner_text()).strip()

                    # 8. Total Equity Funding USD
                    company_data["total_equity_funding"] = (await row.locator('[data-walk-through-id$="-cell-totalEquityFunding"]').inner_text()).strip()

                    # 9. Marquee Customer Mentions
                    company_data["marquee_customer_mentions"] = (await row.locator('[data-walk-through-id$="-cell-numberOfMarqueeCustomerMentions"]').inner_text()).strip()

                    # 10. Latest Revenue
                    company_data["latest_revenue"] = (await row.locator('[data-walk-through-id$="-cell-latestRevenue"]').inner_text()).strip()

                    # 11. Latest Employee Count
                    company_data["latest_employee_count"] = (await row.locator('[data-walk-through-id$="-cell-latestEmployeeCount"]').inner_text()).strip()

                    # 12. App Rating (DOM ID: weightedRatings)
                    company_data["app_rating"] = (await row.locator('[data-walk-through-id$="-cell-weightedRatings"]').inner_text()).strip()

                    # 13. Mobile Downloads
                    company_data["mobile_downloads"] = (await row.locator('[data-walk-through-id$="-cell-totalDownloads"]').inner_text()).strip()

                    # 14. Mobile Reviews
                    company_data["mobile_reviews"] = (await row.locator('[data-walk-through-id$="-cell-totalReviews"]').inner_text()).strip()

                    # 15. News Articles (All Time) (DOM ID: totalMentionsCount)
                    company_data["news_articles_all_time"] = (await row.locator('[data-walk-through-id$="-cell-totalMentionsCount"]').inner_text()).strip()

                    # 16. Mobile Reviews (%)
                    company_data["mobile_reviews_growth"] = (await row.locator('[data-walk-through-id$="-cell-mobileReviewGrowth"]').inner_text()).strip()

                    # 17. News Articles (%)
                    company_data["news_articles_growth"] = (await row.locator('[data-walk-through-id$="-cell-newsMention12MonthGrowth"]').inner_text()).strip()

                    # 18. Latest Employee Growth (%)
                    company_data["latest_employee_growth"] = (await row.locator('[data-walk-through-id$="-cell-latestEmployeeCountGrowth"]').inner_text()).strip()

                    investments_list.append(company_data)
                    
                except Exception as e:
                    self.log.debug(f"Could not parse data for one investment row (index {i}): {e}")
        
        except Exception as e:
            self.log.error(f"Could not extract the investment list: {e}")
            return investments_list
        
        self.log.info(f"Successfully scraped {len(investments_list)} investment rows.")
        return investments_list
    
    async def get_incubator_programs(self):
        """
        Extracts the detailed list of programs from the accelerator/incubator table.

        This function iterates through the program table rows and scrapes
        data for each batch/year listed.

        Returns:
            A list of dictionaries, where each dictionary contains
            the details for one program row.
        """
        program_list = []

        # Locate the main table
        try:
            await self.page.keyboard.press('End')
            await self.page.keyboard.press('End')
            await self.page.keyboard.press('End')
            await self.page.keyboard.press('End')
            # This selector is based on the unique class in your DOM
            table = self.page.locator(".comp--gridtable-v2").first
            await table.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"Program table not found: {e}")
            return program_list

        try:
            # --- Extract Program Table Data ---
            rows = table.locator(".comp--gridtable__row")
            row_count = await rows.count()
            self.log.info(f"Found {row_count} program rows to scrape.")

            for i in range(row_count):
                row = rows.nth(i)
                program_data = {}
                
                try:
                    # --- 1. Program Name (and Rank) ---
                    name_cell = row.locator('[data-walk-through-id$="-cell-name"]')
                    
                    # Extract Rank/Number
                    rank_text = await name_cell.locator(".comp--gridtable__row-serial-number").inner_text()
                    program_data["rank"] = int(rank_text.replace('.', '').strip())
                    
                    # Extract Program Name
                    program_name = await name_cell.locator("span.txn--text-truncate").inner_text()
                    program_data["program_name"] = program_name.strip()

                    # --- 2. # of Batches ---
                    batches_text = await row.locator('[data-walk-through-id$="-cell-totalBatches"]').inner_text()
                    program_data["num_batches"] = batches_text.strip()

                    # --- 3. # of Incubated Cos. ---
                    incubated_text = await row.locator('[data-walk-through-id$="-cell-totalCompanies"]').inner_text()
                    program_data["num_incubated_cos"] = incubated_text.strip()

                    # --- 4. # of Funded Cos. ---
                    funded_text = await row.locator('[data-walk-through-id$="-cell-totalFundCompanies"]').inner_text()
                    program_data["num_funded_cos"] = funded_text.strip()

                    # --- 5. Notable Companies ---
                    # This cell can have multiple links, so we find all 'a' tags
                    notable_links = row.locator('[data-walk-through-id$="-cell-notableCompanies"] a')
                    companies = []
                    for j in range(await notable_links.count()):
                        company_name = await notable_links.nth(j).inner_text()
                        companies.append(company_name.strip())
                    
                    # Join them with a comma and space
                    program_data["notable_companies"] = ", ".join(companies)

                    program_list.append(program_data)
                    
                except Exception as e:
                    self.log.debug(f"Could not parse data for program row (index {i}): {e}")
        
        except Exception as e:
            self.log.error(f"Could not extract the program list: {e}")
            return program_list
        
        self.log.info(f"Successfully scraped {len(program_list)} program rows.")
        return program_list

    async def get_incubator_batches(self):
        """
        Extracts the detailed list of accelerator batches from the table.

        This function iterates through the batch table rows and scrapes
        data for each batch listed.

        Returns:
            A list of dictionaries, where each dictionary contains
            the details for one batch row.
        """
        batch_list = []

        # Locate the main table
        try:
            await self.page.keyboard.press('End')
            await self.page.keyboard.press('End')
            await self.page.keyboard.press('End')
            await self.page.keyboard.press('End')
            # This selector is based on the unique class in your DOM
            table = self.page.locator(".comp--gridtable-v2").first
            await table.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"Batch table not found: {e}")
            return batch_list

        try:
            # --- Extract Batch Table Data ---
            rows = table.locator(".comp--gridtable__row")
            row_count = await rows.count()
            self.log.info(f"Found {row_count} batch rows to scrape.")

            for i in range(row_count):
                row = rows.nth(i)
                batch_data = {}
                
                try:
                    # --- 1. Batch ---
                    batch_name = await row.locator('[data-walk-through-id$="-cell-name"] p').inner_text()
                    batch_data["batch"] = batch_name.strip()

                    # --- 2. Program ---
                    program = await row.locator('[data-walk-through-id$="-cell-programName"]').inner_text()
                    batch_data["program"] = program.strip()

                    # --- 3. Start Date ---
                    start_date = await row.locator('[data-walk-through-id$="-cell-startDate"]').inner_text()
                    batch_data["start_date"] = start_date.strip()

                    # --- 4. End Date ---
                    end_date = await row.locator('[data-walk-through-id$="-cell-endDate"]').inner_text()
                    batch_data["end_date"] = end_date.strip()

                    # --- 5. # of Incubated Cos. ---
                    incubated_cos = await row.locator('[data-walk-through-id$="-cell-totalCompanies"]').inner_text()
                    batch_data["num_incubated_cos"] = incubated_cos.strip()

                    # --- 6. # of Funded Cos. ---
                    funded_cos = await row.locator('[data-walk-through-id$="-cell-totalFundCompanies"]').inner_text()
                    batch_data["num_funded_cos"] = funded_cos.strip()

                    # --- 7. Notable Companies ---
                    notable_links = row.locator('[data-walk-through-id$="-cell-notableCompanies"] a')
                    companies = []
                    for j in range(await notable_links.count()):
                        company_name = await notable_links.nth(j).inner_text()
                        companies.append(company_name.strip())
                    
                    batch_data["notable_companies"] = ", ".join(companies)

                    # Add to list only if the row is not empty
                    if batch_data["batch"] or batch_data["program"] != "-":
                        batch_list.append(batch_data)
                    
                except Exception as e:
                    self.log.debug(f"Could not parse data for batch row (index {i}): {e}")
        
        except Exception as e:
            self.log.error(f"Could not extract the batch list: {e}")
            return batch_list
        
        self.log.info(f"Successfully scraped {len(batch_list)} batch rows.")
        return batch_list

    async def get_incubated_companies(self):
        """
        Extracts the detailed list of companies from an accelerator's batch table.

        This function iterates through the company table rows and scrapes
        all 12 columns of data for each company listed.

        Returns:
            A list of dictionaries, where each dictionary contains
            the details for one company row.
        """
        company_list = []

        # Locate the main table
        try:
            # This selector is based on the unique class in your DOM
            table = self.page.locator(".comp--gridtable-v2").first
            await table.wait_for(state="visible", timeout=10000)
        except Exception as e:
            self.log.error(f"Accelerator company table not found: {e}")
            return company_list

        try:
            # --- Extract Company Table Data ---
            rows = table.locator(".comp--gridtable__row")
            row_count = await rows.count()
            self.log.info(f"Found {row_count} company rows to scrape.")

            for i in range(row_count):
                row = rows.nth(i)
                company_data = {}
                
                try:
                    # --- 1. Tracxn Score ---
                    score_text = await row.locator('[data-walk-through-id$="-cell-tracxnScore"] p').inner_text()
                    company_data["tracxn_score"] = int(score_text.strip())

                    # --- 2. Company Name ---
                    company_name = await row.locator('[data-walk-through-id$="-cell-companyName"] a.txn--text-truncate').first.inner_text()
                    company_data["company_name"] = company_name.strip()

                    # --- 3. Short Description ---
                    description = await row.locator('[data-walk-through-id$="-cell-shortDescription"] .txn--text-truncate').inner_text()
                    company_data["short_description"] = description.strip()

                    # --- 4. Program ---
                    program = await row.locator('[data-walk-through-id$="-cell-programName"]').inner_text()
                    company_data["program"] = program.strip()

                    # --- 5. Batch ---
                    batch = await row.locator('[data-walk-through-id$="-cell-batchName"]').inner_text()
                    company_data["batch"] = batch.strip()

                    # --- 6. Sector ---
                    # Gets the first listed sector. 
                    # Use .all_inner_texts() if you need all sectors in a list.
                    sector = await row.locator('[data-walk-through-id$="-cell-sectorsList"] a').first.inner_text()
                    company_data["sector"] = sector.strip()

                    # --- 7. Total Equity Funding ---
                    funding = await row.locator('[data-walk-through-id$="-cell-totalEquityFunding"]').inner_text()
                    company_data["total_equity_funding"] = funding.strip()
                    
                    # --- 8. Founded Year ---
                    founded_year = await row.locator('[data-walk-through-id$="-cell-foundedYear"]').inner_text()
                    company_data["founded_year"] = founded_year.strip()

                    # --- 9. Location ---
                    location = await row.locator('[data-walk-through-id$="-cell-locations"]').inner_text()
                    company_data["location"] = location.strip()
                    
                    # --- 10. Company Stage ---
                    stage = await row.locator('[data-walk-through-id$="-cell-stage"]').inner_text()
                    company_data["company_stage"] = stage.strip()
                    
                    # --- 11. Latest Valuation ---
                    valuation = await row.locator('[data-walk-through-id$="-cell-latestValuation"]').inner_text()
                    company_data["latest_valuation"] = valuation.strip()
                    
                    # --- 12. Latest Revenue ---
                    revenue = await row.locator('[data-walk-through-id$="-cell-latestRevenue"]').inner_text()
                    company_data["latest_revenue"] = revenue.strip()

                    company_list.append(company_data)
                    
                except Exception as e:
                    self.log.debug(f"Could not parse data for company row (index {i}): {e}")
        
        except Exception as e:
            self.log.error(f"Could not extract the company list: {e}")
            return company_list
        
        self.log.info(f"Successfully scraped {len(company_list)} company rows.")
        return company_list
    