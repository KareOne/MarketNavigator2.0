import os
import asyncio
import random
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from config import SLEEP_DELAY
from page_scraper import scrape_company_page,scrape_company_page2
from browser_manager import get_browser_manager
from database import save_company, already_scraped_urls, get_company
from datetime import datetime, timedelta


async def _perform_search(page, search_hashtag, use_ai_search=True):
    """
    Performs a search on Crunchbase.
    
    Two modes:
    - AI Search (use_ai_search=True): Uses the main search bar - simpler and more reliable
    - Filter Search (use_ai_search=False): Uses the Description Keywords filter via Overview popup
    
    Args:
        page: Playwright page instance
        search_hashtag: The search keyword/phrase
        use_ai_search: If True, use AI search bar. If False, use Description Keywords filter.
        
    Returns:
        True if search was successful, False otherwise
    """
    import asyncio
    import random
    from config import SLEEP_DELAY
    
    print(f"🔍 Searching for: {search_hashtag}")
    
    try:
        # Wait for page to be fully loaded
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        
        if use_ai_search:
            # AI Search: Use the main search bar - simpler and more reliable
            search_bar = page.get_by_placeholder("Search for companies, investors, and more")
            await search_bar.wait_for(timeout=30000)
            await search_bar.fill(search_hashtag)
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
            await search_bar.press("Enter")
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
            return True
        else:
            # Filter Search: Use the Description Keywords filter via Overview popup
            # Step 1: Click on Overview filter button
            overview_selectors = [
                'button:has-text("Overview")',
                'button.filter-group-button:has-text("Overview")',
            ]
            
            overview_clicked = False
            for selector in overview_selectors:
                try:
                    overview_element = page.locator(selector).first
                    if await overview_element.is_visible(timeout=2000):
                        await overview_element.click()
                        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                        overview_clicked = True
                        break
                except Exception:
                    continue
            
            # If Overview not found, try expanding the search builder first
            if not overview_clicked:
                expand_selectors = [
                    'button[aria-label="Edit Search"]',
                    'expand-toggle-button button',
                ]
                
                for selector in expand_selectors:
                    try:
                        expand_button = page.locator(selector).first
                        if await expand_button.is_visible(timeout=3000):
                            await expand_button.click()
                            await asyncio.sleep(3)  # Wait for expansion
                            break
                    except Exception:
                        continue
                
                # Try finding Overview button again after expansion
                for selector in overview_selectors:
                    try:
                        overview_element = page.locator(selector).first
                        if await overview_element.is_visible(timeout=2000):
                            await overview_element.click()
                            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                            overview_clicked = True
                            break
                    except Exception:
                        continue
            
            if not overview_clicked:
                print("❌ Could not find Overview filter button")
                return False
            
            # Step 2: Find and fill the Description Keywords input field
            keywords_input_selectors = [
                'advanced-filter:has(h4:text("Description Keywords")) input',
                'div.filter:has(h4:text("Description Keywords")) input',
                'input[placeholder*="RegTech"]',
            ]
            
            keywords_input = None
            for selector in keywords_input_selectors:
                try:
                    inputs = page.locator(selector)
                    count = await inputs.count()
                    if count > 0:
                        inp = inputs.first
                        if await inp.is_visible(timeout=3000):
                            keywords_input = inp
                            break
                except Exception:
                    continue
            
            if keywords_input:
                await keywords_input.fill(search_hashtag)
                await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                await keywords_input.press("Enter")
                await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                return True
            else:
                print("❌ Could not find Description Keywords input")
                return False
            
    except Exception as e:
        print(f"❌ Error performing search: {e}")
        return False


async def _collect_companies_with_descriptions_impl(search_hashtag, num_companies=5, use_ai_search=True):
    """
    Internal implementation of collect_companies_with_descriptions.
    This function is queued to prevent concurrent browser operations.
    
    Args:
        search_hashtag: The search keyword/phrase
        num_companies: Number of companies to collect
        use_ai_search: If True, use AI keyword search. If False, use standard search bar.
    """
    browser_mgr = await get_browser_manager()
    page = await browser_mgr.new_page()
    
    companies_data = []
    
    try:
        # Navigate to login page to check authentication
        await page.goto("https://www.crunchbase.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        
        # Ensure we're logged in
        if not await browser_mgr.ensure_logged_in(page):
            print("❌ Failed to login")
            return companies_data
        
        # Create a new page after login (old page was closed in ensure_logged_in if login happened)
        if page.is_closed():
            page = await browser_mgr.new_page()

        # Go to discovery search
        await page.goto("https://www.crunchbase.com/discover/organization.companies", wait_until='domcontentloaded')
        
        # Use the search helper (supports both standard and AI search)
        await _perform_search(page, search_hashtag, use_ai_search)

        await page.wait_for_selector('grid-row', timeout=60000)
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))

        # Track consecutive pages without finding companies to prevent infinite loops
        consecutive_empty_pages = 0
        max_empty_pages = 3  # Stop after 3 consecutive pages with no companies found
        
        # Collect company data with pagination
        while len(companies_data) < num_companies:
            companies_found_this_page = 0
            
            # Check if still logged in before each page
            if not await browser_mgr.is_logged_in(page):
                print("⚠️ Session expired during collection, re-logging in...")
                await browser_mgr.ensure_logged_in(page)
                if page.is_closed():
                    page = await browser_mgr.new_page()
                # Navigate back to search results
                await page.goto("https://www.crunchbase.com/discover/organization.companies", wait_until='domcontentloaded')
                await _perform_search(page, search_hashtag, use_ai_search)
                await page.wait_for_selector('grid-row', timeout=60000)
                await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                
            company_rows = page.locator('grid-row')
            count = await company_rows.count()
            
            for i in range(count):
                if len(companies_data) >= num_companies:
                    break
                try:
                    row = company_rows.nth(i)
                    
                    # Get URL from identifier column
                    relative_url = await row.locator(
                        'grid-cell[data-columnid="identifier"] a'
                    ).get_attribute('href')
                    
                    if not relative_url:
                        continue
                    
                    full_url = "https://www.crunchbase.com" + relative_url
                    
                    # Skip person URLs - they don't have company data
                    if '/person/' in full_url:
                        print(f"⏭️ Skipping person URL: {full_url}")
                        continue
                    
                    # Check if already collected
                    if any(c['url'] == full_url for c in companies_data):
                        continue
                    
                    # Get full description from description column (not short_description)
                    description = ""
                    try:
                        description_element = row.locator('grid-cell[data-columnid="description"] span.field-type-text_long')
                        description = await description_element.inner_text(timeout=5000)
                        description = description.strip()
                    except Exception as e:
                        print(f"⚠️ Could not extract description for {full_url}: {e}")
                        # Try to get title attribute as fallback
                        try:
                            description = await description_element.get_attribute('title', timeout=5000)
                            description = description.strip() if description else ""
                        except:
                            pass
                    
                    if description:
                        companies_data.append({
                            'url': full_url,
                            'description': description
                        })
                        companies_found_this_page += 1
                        print(f"✅ Collected: {full_url} (desc length: {len(description)})")
                    else:
                        print(f"⚠️ No description found for {full_url}, skipping")
                        
                except Exception as e:
                    print(f"❌ Error extracting row {i}: {e}")
                    continue

            # Track consecutive empty pages
            if companies_found_this_page == 0:
                consecutive_empty_pages += 1
                print(f"⚠️ No companies found on this page ({consecutive_empty_pages}/{max_empty_pages} consecutive empty pages)")
                if consecutive_empty_pages >= max_empty_pages:
                    print(f"⚠️ Stopping search: {max_empty_pages} consecutive pages with no companies. Collected {len(companies_data)} companies.")
                    break
            else:
                consecutive_empty_pages = 0  # Reset counter when we find companies

            # Pagination
            if len(companies_data) < num_companies:
                try:
                    next_button = page.locator('a.page-button-next.mdc-button.mat-mdc-button')
                    if await next_button.is_enabled():
                        await next_button.click()
                        await page.wait_for_selector('grid-row', timeout=30000)
                        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                    else:
                        print(f"⚠️ No more pages available. Collected {len(companies_data)} companies.")
                        break
                except PlaywrightTimeoutError:
                    print(f"⚠️ Pagination timeout. Collected {len(companies_data)} companies.")
                    break
                    
    except Exception as e:
        print(f"❌ Critical error in collect_companies_with_descriptions: {e}")
    finally:
        # Close the tab when done
        if not page.is_closed():
            await page.close()

    return companies_data


async def collect_companies_with_descriptions(search_hashtag, num_companies=5, use_ai_search=True):
    """
    Collects company URLs and full descriptions from the search table.
    Uses persistent browser manager with queuing for concurrent request safety.
    
    Args:
        search_hashtag: The search keyword/phrase
        num_companies: Number of companies to collect
        use_ai_search: If True, use AI keyword search. If False, use standard search bar.
    
    Returns a list of dicts with 'url' and 'description' keys.
    """
    browser_mgr = await get_browser_manager()
    status = browser_mgr.get_queue_status()
    
    if status["queue_size"] > 0 or status["active_operations"] > 0:
        print(f"⏳ Request queued. Queue: {status['queue_size']}, Active: {status['active_operations']}")
    
    # Queue the operation to prevent concurrent browser access
    return await browser_mgr.queue_operation(
        _collect_companies_with_descriptions_impl,
        search_hashtag,
        num_companies,
        use_ai_search
    )


async def _collect_companies_with_rank_impl(search_hashtag, num_companies=5, use_ai_search=True):
    """
    Internal implementation of collect_companies_with_rank.
    This function is queued to prevent concurrent browser operations.
    Collects company URLs, descriptions, and CB rank from search results.
    
    Args:
        search_hashtag: The search keyword/phrase
        num_companies: Number of companies to collect
        use_ai_search: If True, use AI keyword search. If False, use standard search bar.
    """
    browser_mgr = await get_browser_manager()
    page = await browser_mgr.new_page()
    
    companies_data = []
    
    try:
        # Navigate to login page to check authentication
        await page.goto("https://www.crunchbase.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        
        # Ensure we're logged in
        if not await browser_mgr.ensure_logged_in(page):
            print("❌ Failed to login")
            return companies_data
        
        # Create a new page after login (old page was closed in ensure_logged_in if login happened)
        if page.is_closed():
            page = await browser_mgr.new_page()

        # Go to discovery search
        await page.goto("https://www.crunchbase.com/discover/organization.companies", wait_until='domcontentloaded')
        
        # Use the search helper (supports both standard and AI search)
        await _perform_search(page, search_hashtag, use_ai_search)

        await page.wait_for_selector('grid-row', timeout=60000)
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))

        # Track consecutive pages without finding companies to prevent infinite loops
        consecutive_empty_pages = 0
        max_empty_pages = 3  # Stop after 3 consecutive pages with no companies found
        
        # Collect company data with pagination
        while len(companies_data) < num_companies:
            companies_found_this_page = 0
            
            # Check if still logged in before each page
            if not await browser_mgr.is_logged_in(page):
                print("⚠️ Session expired during collection, re-logging in...")
                await browser_mgr.ensure_logged_in(page)
                if page.is_closed():
                    page = await browser_mgr.new_page()
                # Navigate back to search results
                await page.goto("https://www.crunchbase.com/discover/organization.companies", wait_until='domcontentloaded')
                await _perform_search(page, search_hashtag, use_ai_search)
                await page.wait_for_selector('grid-row', timeout=60000)
                await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                
            company_rows = page.locator('grid-row')
            count = await company_rows.count()
            
            for i in range(count):
                if len(companies_data) >= num_companies:
                    break
                try:
                    row = company_rows.nth(i)
                    
                    # Get URL from identifier column
                    relative_url = await row.locator(
                        'grid-cell[data-columnid="identifier"] a'
                    ).get_attribute('href')
                    
                    if not relative_url:
                        continue
                    
                    full_url = "https://www.crunchbase.com" + relative_url
                    
                    # Skip person URLs - they don't have company data
                    if '/person/' in full_url:
                        print(f"⏭️ Skipping person URL: {full_url}")
                        continue
                    
                    # Check if already collected
                    if any(c['url'] == full_url for c in companies_data):
                        continue
                    
                    # Get full description from description column (not short_description)
                    description = ""
                    try:
                        description_element = row.locator('grid-cell[data-columnid="description"] span.field-type-text_long')
                        description = await description_element.inner_text(timeout=5000)
                        description = description.strip()
                    except Exception as e:
                        print(f"⚠️ Could not extract description for {full_url}: {e}")
                        # Try to get title attribute as fallback
                        try:
                            description = await description_element.get_attribute('title', timeout=5000)
                            description = description.strip() if description else ""
                        except:
                            pass
                    
                    # Get CB rank from rank_org_company column
                    cb_rank = None
                    try:
                        rank_element = row.locator('grid-cell[data-columnid="rank_org_company"] a')
                        rank_text = await rank_element.inner_text(timeout=5000)
                        rank_text = rank_text.strip()
                        # Convert to integer, handle commas if present
                        cb_rank = int(rank_text.replace(',', ''))
                    except Exception as e:
                        print(f"⚠️ Could not extract CB rank for {full_url}: {e}")
                        # Try alternative selectors
                        try:
                            rank_element = row.locator('grid-cell[data-columnid="rank_org_company"] span')
                            rank_text = await rank_element.inner_text(timeout=5000)
                            rank_text = rank_text.strip()
                            if rank_text and rank_text != '—':
                                cb_rank = int(rank_text.replace(',', ''))
                        except:
                            pass
                    
                    # Only add if we have both description and rank
                    if description and cb_rank is not None:
                        companies_data.append({
                            'url': full_url,
                            'description': description,
                            'cb_rank': cb_rank
                        })
                        companies_found_this_page += 1
                        print(f"✅ Collected: {full_url} (desc length: {len(description)}, CB rank: {cb_rank})")
                    else:
                        missing = []
                        if not description:
                            missing.append("description")
                        if cb_rank is None:
                            missing.append("CB rank")
                        print(f"⚠️ Missing {', '.join(missing)} for {full_url}, skipping")
                        
                except Exception as e:
                    print(f"❌ Error extracting row {i}: {e}")
                    continue

            # Track consecutive empty pages
            if companies_found_this_page == 0:
                consecutive_empty_pages += 1
                print(f"⚠️ No companies found on this page ({consecutive_empty_pages}/{max_empty_pages} consecutive empty pages)")
                if consecutive_empty_pages >= max_empty_pages:
                    print(f"⚠️ Stopping search: {max_empty_pages} consecutive pages with no companies. Collected {len(companies_data)} companies.")
                    break
            else:
                consecutive_empty_pages = 0  # Reset counter when we find companies

            # Pagination
            if len(companies_data) < num_companies:
                try:
                    next_button = page.locator('a.page-button-next.mdc-button.mat-mdc-button')
                    if await next_button.is_enabled():
                        await next_button.click()
                        await page.wait_for_selector('grid-row', timeout=30000)
                        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                    else:
                        print(f"⚠️ No more pages available. Collected {len(companies_data)} companies.")
                        break
                except PlaywrightTimeoutError:
                    print(f"⚠️ Pagination timeout. Collected {len(companies_data)} companies.")
                    break
                    
    except Exception as e:
        print(f"❌ Critical error in collect_companies_with_rank: {e}")
    finally:
        # Close the tab when done
        if not page.is_closed():
            await page.close()

    return companies_data


async def collect_companies_with_rank(search_hashtag, num_companies=5, use_ai_search=True):
    """
    Collects company URLs, full descriptions, and CB rank from the search table.
    Uses persistent browser manager with queuing for concurrent request safety.
    
    Args:
        search_hashtag: The search keyword/phrase
        num_companies: Number of companies to collect
        use_ai_search: If True, use AI keyword search. If False, use standard search bar.
    
    Returns a list of dicts with 'url', 'description', and 'cb_rank' keys.
    """
    browser_mgr = await get_browser_manager()
    status = browser_mgr.get_queue_status()
    
    if status["queue_size"] > 0 or status["active_operations"] > 0:
        print(f"⏳ Request queued. Queue: {status['queue_size']}, Active: {status['active_operations']}")
    
    # Queue the operation to prevent concurrent browser access
    return await browser_mgr.queue_operation(
        _collect_companies_with_rank_impl,
        search_hashtag,
        num_companies,
        use_ai_search
    )


async def _run_scraper_impl(search_hashtag, num_companies=5, days_threshold=0, use_ai_search=True):
    """
    Internal implementation of run_scraper.
    This function is queued to prevent concurrent browser operations.
    
    Args:
        search_hashtag: The search keyword/phrase
        num_companies: Number of companies to collect
        days_threshold: Number of days before considering data stale
        use_ai_search: If True, use AI keyword search. If False, use standard search bar.
    """
    scraped_info = already_scraped_urls()
    browser_mgr = await get_browser_manager()
    page = await browser_mgr.new_page()
    
    company_links = []
    results = []
    
    try:
        # Navigate to login page to check authentication
        await page.goto("https://www.crunchbase.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        
        # Ensure we're logged in
        if not await browser_mgr.ensure_logged_in(page):
            print("❌ Failed to login")
            return results
        
        # Create a new page after login if needed
        if page.is_closed():
            page = await browser_mgr.new_page()

        # Go to discovery search
        await page.goto("https://www.crunchbase.com/discover/organization.companies", wait_until='domcontentloaded')
        
        # Use the search helper (supports both standard and AI search)
        await _perform_search(page, search_hashtag, use_ai_search)

        await page.wait_for_selector('grid-row', timeout=60000)
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))

        # Track consecutive pages without finding companies to prevent infinite loops
        consecutive_empty_pages = 0
        max_empty_pages = 3  # Stop after 3 consecutive pages with no companies found
        
        # Collect links with pagination
        while len(company_links) < num_companies:
            companies_found_this_page = 0
            company_rows = page.locator('grid-row')
            count = await company_rows.count()
            for i in range(count):
                if len(company_links) >= num_companies:
                    break
                try:
                    relative_url = await company_rows.nth(i).locator(
                        'grid-cell[data-columnid="identifier"] a'
                    ).get_attribute('href')
                    if relative_url:
                        full_url = "https://www.crunchbase.com" + relative_url
                        # Skip person URLs - they don't have company data
                        if '/person/' in full_url:
                            print(f"⏭️ Skipping person URL: {full_url}")
                            continue
                        if full_url not in company_links:
                            company_links.append(full_url)
                            companies_found_this_page += 1
                except Exception:
                    continue

            # Track consecutive empty pages
            if companies_found_this_page == 0:
                consecutive_empty_pages += 1
                print(f"⚠️ No companies found on this page ({consecutive_empty_pages}/{max_empty_pages} consecutive empty pages)")
                if consecutive_empty_pages >= max_empty_pages:
                    print(f"⚠️ Stopping search: {max_empty_pages} consecutive pages with no companies. Collected {len(company_links)} company links.")
                    break
            else:
                consecutive_empty_pages = 0  # Reset counter when we find companies

            if len(company_links) < num_companies:
                try:
                    next_button = page.locator('a.page-button-next.mdc-button.mat-mdc-button')
                    if await next_button.is_enabled():
                        await next_button.click()
                        await page.wait_for_selector('grid-row', timeout=30000)
                        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                    else:
                        print(f"⚠️ No more pages available. Collected {len(company_links)} company links.")
                        break
                except PlaywrightTimeoutError:
                    print(f"⚠️ Pagination timeout. Collected {len(company_links)} company links.")
                    break

        # Scrape companies
        # Handle days_threshold=0 to always re-scrape
        if days_threshold == 0:
            expiry_time = datetime.max  # All companies will be considered stale
        else:
            expiry_time = datetime.now() - timedelta(days=days_threshold)
            
        for i, url in enumerate(company_links[:num_companies], 1):
            last_scraped = scraped_info.get(url)

            if last_scraped and last_scraped > expiry_time:
                time_since_scrape = datetime.now() - last_scraped
                print(f"✅ Skipping (fresh in DB): {url}")
                print(f"   Last scraped: {last_scraped}")
                print(f"   Time since scrape: {time_since_scrape}")
                print(f"   Threshold: {days_threshold} days")
                results.append(get_company(url))
                continue

            print(f"\n--- Scraping {i}/{num_companies}: {url} ---")
            
            # Open new tab for each company
            company_page = await browser_mgr.new_page()

            try:
                try:
                    await company_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except PlaywrightTimeoutError:
                    pass
                    
                await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                
                # Check if still logged in
                if not await browser_mgr.is_logged_in(company_page):
                    print("⚠️ Session expired, re-logging in...")
                    await browser_mgr.ensure_logged_in(company_page)
                    # Retry the company page after login
                    if company_page.is_closed():
                        company_page = await browser_mgr.new_page()
                    await company_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))

                data = await scrape_company_page(company_page)
                if data:
                    data["url"] = url
                    save_company(data)
                    print(f"✅ Saved {data.get('Company Name', 'Unknown')}")
                    results.append(data)
                    
            except PlaywrightTimeoutError:
                print(f"❌ Timeout while loading {url}. Skipping.")
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
            finally:
                if not company_page.is_closed():
                    await company_page.close()
                    
    except Exception as e:
        print(f"❌ Critical error: {e}")
    finally:
        # Close the search page tab
        if not page.is_closed():
            await page.close()

    return results


async def run_scraper(search_hashtag, num_companies=5, days_threshold=0, use_ai_search=True):
    """
    Main scraper with MySQL storage and resume support.
    Uses persistent browser manager with queuing for concurrent request safety.
    
    Args:
        search_hashtag: The search keyword/phrase
        num_companies: Number of companies to collect
        days_threshold: Number of days before considering data stale
        use_ai_search: If True, use AI keyword search. If False, use standard search bar.
    """
    browser_mgr = await get_browser_manager()
    status = browser_mgr.get_queue_status()
    
    if status["queue_size"] > 0 or status["active_operations"] > 0:
        print(f"⏳ Request queued. Queue: {status['queue_size']}, Active: {status['active_operations']}")
    
    # Queue the operation to prevent concurrent browser access
    return await browser_mgr.queue_operation(
        _run_scraper_impl,
        search_hashtag,
        num_companies,
        days_threshold,
        use_ai_search
    )


async def _scrape_top_companies_impl(company_urls, days_threshold=0, status_callback=None):
    """
    Scrapes company pages for a list of URLs (already sorted by similarity).
    Only scrapes if the company is not fresh in the database.
    Uses persistent browser manager - opens new tab for each company.
    
    Args:
        company_urls: List of company URLs (already sorted by similarity)
        days_threshold: Number of days before considering data stale
        status_callback: Optional async function to call with status updates
        
    Returns:
        List of scraped company data
    """
    scraped_info = already_scraped_urls()
    browser_mgr = await get_browser_manager()
    
    # Create initial page for login check
    page = await browser_mgr.new_page()
    
    try:
        # Navigate to login page to check authentication
        await page.goto("https://www.crunchbase.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        
        # Ensure we're logged in
        if not await browser_mgr.ensure_logged_in(page):
            print("❌ Failed to login")
            return []
    finally:
        # Close the login check page
        if not page.is_closed():
            await page.close()

    results = []
    
    # Handle days_threshold=0 to always re-scrape
    if days_threshold == 0:
        expiry_time = datetime.max  # All companies will be considered stale
    else:
        expiry_time = datetime.now() - timedelta(days=days_threshold)
        
    try:
        for i, url in enumerate(company_urls, 1):
            last_scraped = scraped_info.get(url)

            if last_scraped and last_scraped > expiry_time:
                time_since_scrape = datetime.now() - last_scraped
                print(f"✅ Skipping (fresh in DB): {url}")
                print(f"   Last scraped: {last_scraped}")
                print(f"   Time since scrape: {time_since_scrape}")
                print(f"   Threshold: {days_threshold} days")
                results.append(get_company(url))
                continue

            print(f"\n--- Scraping {i}/{len(company_urls)}: {url} ---")
            
            # Send status update if callback provided
            if status_callback:
                company_name = url.split("/")[-1].replace("-", " ").title()
                try:
                    status_callback(
                        "fetching_details",
                        "company_processing",
                        f"Scraping: {company_name} ({i}/{len(company_urls)})",
                        {"company": company_name, "index": i, "total": len(company_urls)}
                    )
                except Exception as e:
                    print(f"⚠️ Status callback failed (non-blocking): {e}")
            
            # Open new tab for each company
            company_page = await browser_mgr.new_page()

            try:
                try:
                    await company_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except PlaywrightTimeoutError:
                    pass
                    
                await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                
                # Check if still logged in
                if not await browser_mgr.is_logged_in(company_page):
                    print("⚠️ Session expired, re-logging in...")
                    await browser_mgr.ensure_logged_in(company_page)
                    # Retry the company page after login
                    if company_page.is_closed():
                        company_page = await browser_mgr.new_page()
                    await company_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))

                data = await scrape_company_page(company_page)
                data2 = await scrape_company_page2(url)
                if data:
                    data["url"] = url
                    save_company(data)
                    print(f"✅ Saved {data.get('Company Name', 'Unknown')}")
                    results.append(data)
                    
            except PlaywrightTimeoutError:
                print(f"❌ Timeout while loading {url}. Skipping.")
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
            finally:
                if not company_page.is_closed():
                    await company_page.close()
                
    except Exception as e:
        print(f"❌ Critical error: {e}")

    return results


async def scrape_top_companies(company_urls, days_threshold=0, status_callback=None):
    """
    Scrapes company pages for a list of URLs (already sorted by similarity).
    Only scrapes if the company is not fresh in the database.
    Uses persistent browser manager with queuing for concurrent request safety.
    
    Args:
        company_urls: List of company URLs (already sorted by similarity)
        days_threshold: Number of days before considering data stale
        status_callback: Optional async function to call with status updates
        
    Returns:
        List of scraped company data
    """
    browser_mgr = await get_browser_manager()
    status = browser_mgr.get_queue_status()
    
    if status["queue_size"] > 0 or status["active_operations"] > 0:
        print(f"⏳ Request queued. Queue: {status['queue_size']}, Active: {status['active_operations']}")
    
    # Queue the operation to prevent concurrent browser access
    return await browser_mgr.queue_operation(
        _scrape_top_companies_impl,
        company_urls,
        days_threshold,
        status_callback
    )
