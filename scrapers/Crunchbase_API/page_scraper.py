import asyncio
import json
import sqlite3
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from config import SLEEP_DELAY, TEST_JSON_OUTPUT
import random
import os

async def scrape_company_page2(url):
    pass

async def scrape_company_page(page):
    """
    Scrapes all the detailed information from a company's profile page.
    If something can't be scraped, it safely returns 'N/A' or an empty list.
    """
    data = {}

    # Helper: safely extract text
    async def get_text(selector, default="N/A"):
        try:
            return await page.locator(selector).first.inner_text(timeout=2000)
        except Exception:
            return default

    # Helper: safely extract text_content
    async def get_content(selector, default="N/A"):
        try:
            return await page.locator(selector).first.text_content(timeout=2000)
        except Exception:
            return default

    # Helper: safe click
    async def safe_click(selector):
        try:
            await page.locator(selector).first.click(timeout=2000)
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        except Exception:
            pass

    # ========== BASIC COMPANY DETAILS ==========
    data['Company Name'] = await get_text('span.entity-name')
    data['Legal Name'] = await get_text('tile-field:has-text("Legal Name") field-formatter')
    data['Also Known As'] = await get_text('tile-field:has-text("Also Known As") field-formatter')
    data['Operating Status'] = await get_text('tile-field:has-text("Operating Status") field-formatter')
    data['Company Type'] = await get_text('tile-field:has-text("Company Type") field-formatter')
    data['About'] = await get_content("#overview_details div.description tile-description")
    
    # Company Website
    try:
        # Try multiple selectors to find the website link
        website_link = None
        
        # Try 1: Look for link in label-with-icon with external link icon
        try:
            website_link = await page.locator('label-with-icon[iconkey="icon_external_link"] link-formatter a[href^="http"]').first.get_attribute('href', timeout=2000)
        except Exception:
            pass
        
        # Try 2: Look for any link with "www." or domain pattern in the overview section
        if not website_link:
            try:
                website_link = await page.locator('.overview-row link-formatter a[href^="http"]:not([href*="facebook"]):not([href*="linkedin"]):not([href*="twitter"]):not([href*="instagram"])').first.get_attribute('href', timeout=2000)
            except Exception:
                pass
        
        data['Website'] = website_link if website_link else "N/A"
    except Exception:
        data['Website'] = "N/A"
    
    # Facebook Link
    try:
        facebook_link = await page.locator('a[href*="facebook.com"]').first.get_attribute('href', timeout=2000)
        data['Facebook'] = facebook_link if facebook_link else "N/A"
    except Exception:
        data['Facebook'] = "N/A"
    
    # LinkedIn Link
    try:
        linkedin_link = await page.locator('a[href*="linkedin.com"]').first.get_attribute('href', timeout=2000)
        data['LinkedIn'] = linkedin_link if linkedin_link else "N/A"
    except Exception:
        data['LinkedIn'] = "N/A"
    
    # Industry Tags/Categories
    try:
        tags = []
        chip_elements = await page.locator('chips-container chip div.chip-text').all()
        for chip in chip_elements:
            tag_text = await chip.inner_text(timeout=1000)
            if tag_text:
                tags.append(tag_text.strip())
        data['Industry Tags'] = tags if tags else []
    except Exception:
        data['Industry Tags'] = []

    # try to extend "About" if Read More exists
    try:
        read_more = page.locator("#overview_details text='Read More'")
        if await read_more.is_visible(timeout=1000):
            extra = await get_content("span.overflow-description.ng-star-inserted > p", "")
            data['About'] = (data['About'] or "") + extra
    except Exception:
        pass

    # ========== PREDICTIONS & INSIGHTS ==========
    data['Growth Score'] = await get_text('div.chip-container > div.chip-text')
    data['Growth Score update date'] = await get_text('mat-card#growth_insight header > div.meta > h3')
    data['heat score'] = await get_text('score-and-trend-big-value.heat-color > span.score')
    data['Growth Prediction'] = await get_content('svg.circular-progress > text.display-value.ng-star-inserted')
    data['Growth Prediction update date'] = await get_text('mat-card#growth_prediction header > div.meta > h3')
    data['Growth Insight'] = await get_text('div.body > .summary.truncated.ng-star-inserted')

    # ========== FINANCIAL DETAILS ==========
    try:
        read_more = page.locator("#company_funding footer a.mdc-button")
        if await read_more.is_visible(timeout=1000):
            await safe_click('mat-card#company_funding footer a.mdc-button')
            data['Number of Funding Rounds'] = await get_text('tile-field:has-text("Number of Funding Rounds") field-formatter')
            data['Total Funding Amount'] = await get_text('tile-field:has-text("Total Funding Amount") field-formatter')
            data['Funding Prediction'] = await get_content('funding-prediction-statement')
            data['Acquisition Prediction'] = await get_content('mat-card#acquisition_prediction confidence-gauge text')
            data['IPO Prediction'] = await get_content('mat-card#ipo_prediction confidence-gauge text')
            data['Number of Lead Investors'] = await get_text('tile-field:has-text("Number of Lead Investors") field-formatter')
            data['Number of Investors'] = await get_text('tile-field:has-text("Number of Investors") field-formatter')

            # Funding table
            funding_table = []
            try:
                read_more = page.locator("#funding_rounds tile-table-more-results")
                if await read_more.is_visible(timeout=1000):
                    # Using a more specific locator for the "View All" button
                    await page.locator("#funding_rounds a.mdc-button:has-text('View All')").click()
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                    
                    try:
                        # Select all rows inside the specific table
                        rows = await page.locator('table.card-grid > tbody > tr.ng-star-inserted').all()
                        for row in rows:
                            # --- FIX IS HERE ---
                            # Use row.locator() to find elements *within* the current row
                            funding_table.append({
                                "Announced Date": await row.locator('td:nth-child(1)').inner_text(),
                                "Transaction Name": await row.locator('td:nth-child(2)').inner_text(),
                                "Number of Investors": await row.locator('td:nth-child(3)').inner_text(),
                                "Money Raised": await row.locator('td:nth-child(4)').inner_text(),
                                "Lead Investors": await row.locator('td:nth-child(5)').inner_text(),
                            })
                    except Exception as e:
                        print(f"Error scraping 'View All' table: {e}")
                        
                    await page.go_back()
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                    
                else:
                    try:
                        # Select all rows from the table on the main page
                        rows = await page.locator('#funding_rounds table.card-grid > tbody > tr.ng-star-inserted').all()
                        for row in rows:
                            # --- FIX IS HERE ---
                            # Use row.locator() to find elements *within* the current row
                            funding_table.append({
                                "Announced Date": await row.locator('td:nth-child(1)').inner_text(),
                                "Transaction Name": await row.locator('td:nth-child(2)').inner_text(),
                                "Number of Investors": await row.locator('td:nth-child(3)').inner_text(),
                                "Money Raised": await row.locator('td:nth-child(4)').inner_text(),
                                "Lead Investors": await row.locator('td:nth-child(5)').inner_text(),
                            })
                    except Exception as e:
                        print(f"Error scraping main page table: {e}")

            except Exception as e:
                print(f"Error finding funding table: {e}")
                
            data['Funding Table'] = funding_table


            # Investors table
            investors_table = []
            try:
                read_more = page.locator("#investors tile-table-more-results")
                if await read_more.is_visible(timeout=1000):
                    await safe_click("#investors a.mdc-button:has-text('View All')")
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                    try:
                        rows = await page.locator('table.card-grid > tbody > tr.ng-star-inserted').all()
                        for row in rows:
                            investors_table.append({
                                "Investor Name": await row.locator('td:nth-child(1)').inner_text(),
                                "Lead Investor": await row.locator('td:nth-child(2)').inner_text(),
                                "Funding Round": await row.locator('td:nth-child(3)').inner_text(),
                                "Partners": await row.locator('td:nth-child(4)').inner_text(),
                            })
                    except Exception:
                        pass
                    await page.go_back()
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                else:
                    try:
                        rows = await page.locator('#investors tbody > tr.ng-star-inserted').all()
                        for row in rows:
                            investors_table.append({
                                "Investor Name": await row.locator('td:nth-child(1)').inner_text(),
                                "Lead Investor": await row.locator('td:nth-child(2)').inner_text(),
                                "Funding Round": await row.locator('td:nth-child(3)').inner_text(),
                                "Partners": await row.locator('td:nth-child(4)').inner_text(),
                            })
                    except Exception:
                        pass
            except Exception:
                pass
            data['Investors Table'] = investors_table
            await page.go_back()
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        else:
            data['Number of Funding Rounds'] = "N/A"
            data['Total Funding Amount'] = "N/A"
            data['Funding Prediction'] = "N/A"
            data['Acquisition Prediction'] = "N/A"
            data['IPO Prediction'] = "N/A"
            data['Number of Lead Investors'] = "N/A"
            data['Number of Investors'] = "N/A"
            data['Funding Table'] = []
            data['Investors Table'] = []
    except Exception:
        pass
    # ========== PEOPLE ==========
    data['Headcount'] = await get_text('#people tile-highlight[label="Headcount"] field-formatter a')
    data['Employee Profiles count'] = await get_text('#people tile-highlight[label="Employee Profiles"] field-formatter a')
    data['Investor Profiles count'] = await get_text('#people tile-highlight[label="Investor Profiles"] field-formatter a')
    data['Contacts count'] = await get_text('#people tile-highlight[label="Contacts"] field-formatter a')
    try:
        read_more = page.locator("#people div.section-header a.mdc-button")
        if await read_more.is_visible(timeout=1000):
            await safe_click("#people div.section-header a.mdc-button")
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))

            # Current employees table
            current_employees_table = []
            try:
                read_more = page.locator("#people_employees footer a.mdc-button.mat-mdc-button")
                if await read_more.is_visible(timeout=1000):
                    await safe_click("#people_employees footer a.mdc-button")
                    try:
                        rows = await page.locator('ul.two-column.ng-star-inserted > li.ng-star-inserted').all()
                        for row in rows:
                            current_employees_table.append({
                                "Employee Name": await row.locator('div.fields > a.accent').inner_text(),
                                "Employee Job": await row.locator('field-formatter span.component--field-formatter').inner_text()
                            })
                    except Exception:
                        pass
                    await page.go_back()
                    await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
                else:
                    try:
                        rows = await page.locator('#people_employees people-profiles-detailed > div.ng-star-inserted').all()
                        for row in rows:
                            current_employees_table.append({
                                "Employee Name": await row.locator('div.details > a.accent.ng-star-inserted').inner_text(),
                                "Employee Job": await row.locator('div.details > div.ng-star-inserted').inner_text()
                            })
                    except Exception:
                        pass
            except Exception:
                pass

            data['Current Employees Table'] = current_employees_table

            # Board members
            board_members_table = []
            try:
                rows = await page.locator('#people_advisors people-profiles-detailed > div.ng-star-inserted').all()
                for row in rows:
                    board_members_table.append({
                        "Board Member Name": await row.locator('div.details > a.accent.ng-star-inserted').inner_text(),
                        "Board Member Primary Job": (
                            (await row.locator('div.details div.item span.identifier.ng-star-inserted').inner_text()) +
                            (await row.locator('div.details div.item span.label.ng-star-inserted').inner_text())
                        )
                    })
            except Exception:
                pass
            data['Board Members Table'] = board_members_table
            await page.go_back()
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
        else:
            data['Current Employees Table'] = []
            data['Board Members Table'] = []
    except Exception:
        pass

    # ========== TECH DETAILS ==========
    try:
        read_more = page.locator("#technology div.section-header a.mdc-button")
        if await read_more.is_visible(timeout=1000):
            await safe_click("#technology div.section-header a.mdc-button")
            await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
            data['Tech Details summary'] = await get_text('#technology_highlights div.body > div.summary')
            data['Total Products Active'] = await get_text('#technology_highlights tile-field:has-text("Total Products Active") field-formatter')
            data['Active Tech Count'] = await get_text('#technology_highlights tile-field:has-text("Active Tech Count") field-formatter')
            data['Monthly Visits'] = await get_text('#technology_highlights tile-field:has-text("Monthly Visits") field-formatter')
            data['Monthly Visits Growth'] = await get_text('#technology_highlights tile-field:has-text("Monthly Visits Growth") field-formatter')

            # Web traffic table
            traffic_table = []
            try:
                await page.locator('#semrush_traffic tbody.ng-star-inserted > tr.ng-star-inserted').first.wait_for(timeout=5000)
                rows = await page.locator('#semrush_traffic tbody.ng-star-inserted > tr.ng-star-inserted').all()
                for row in rows:
                    traffic_table.append({
                        "Country": await row.locator('td:nth-child(1)').inner_text(),
                        "Share of Monthly Visits": await row.locator('td:nth-child(2)').inner_text(),
                        "Monthly Visits Growth": await row.locator('td:nth-child(3)').inner_text(),
                        "Site Rank in Country": await row.locator('td:nth-child(4)').inner_text(),
                        "Monthly Rank Growth": await row.locator('td:nth-child(5)').inner_text(),
                    })
            except Exception:
                pass
            data['Web Traffic Table'] = traffic_table

            # Engagement tab
            await safe_click("text=Engagement")
            data['Global Traffic Rank'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Global Traffic Rank") field-formatter')
            data['Monthly Rank Growth'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Monthly Rank Growth") field-formatter')
            data['Visit Duration'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Visit Duration") field-formatter')
            data['Visit Duration Growth'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Visit Duration Growth") field-formatter')
            data['Page Views / Visit'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Page Views / Visit") field-formatter')
            data['Page Views / Visit Growth'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Page Views / Visit Growth") field-formatter')
            data['Bounce Rate'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Bounce Rate") field-formatter')
            data['Bounce Rate Growth'] = await get_text('mat-tab-body[aria-hidden="false"] tile-field:has-text("Bounce Rate Growth") field-formatter')
        else:
            data['Tech Details summary'] = "N/A"
            data['Total Products Active'] = "N/A"
            data['Active Tech Count'] = "N/A"
            data['Monthly Visits'] = "N/A"
            data['Monthly Visits Growth'] = "N/A"
            data['Web Traffic Table'] = []
            data['Global Traffic Rank'] = "N/A"
            data['Monthly Rank Growth'] = "N/A"
            data['Visit Duration'] = "N/A"
            data['Visit Duration Growth'] = "N/A"
            data['Page Views / Visit'] = "N/A"
            data['Page Views / Visit Growth'] = "N/A"
            data['Bounce Rate'] = "N/A"
            data['Bounce Rate Growth'] = "N/A"
    except Exception:
        pass
    return data


# # ========== SAVE TO JSON ==========
# def save_to_json(data, file):
#     os.makedirs(os.path.dirname(file), exist_ok=True) if os.path.dirname(file) else None

#     try:
#         with open(file, "r") as f:
#             existing = json.load(f)
#             if not isinstance(existing, list):  # force list
#                 existing = []
#     except (FileNotFoundError, json.JSONDecodeError):
#         existing = []

#     existing.append(data)

#     with open(file, "w") as f:
#         json.dump(existing, f, indent=4)



# async def main():
#     async with async_playwright() as p:
#         if not os.path.exists(STATE_PATH):
#             return

#         browser = await p.chromium.launch(headless=DEBUG, slow_mo=100)
#         context = await browser.new_context(
#             storage_state=STATE_PATH,
#             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
#         )
#         page = await context.new_page()
#         await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

#         await page.goto("https://www.crunchbase.com/organization/may-mobility", wait_until='domcontentloaded')
#         await asyncio.sleep(random.uniform(SLEEP_DELAY, 2 * SLEEP_DELAY))
#         print("Scraping company page...")
#         company_data = await scrape_company_page(page)
#         print(company_data)
#         save_to_json(company_data, file=TEST_JSON_OUTPUT)

#         await browser.close()

# if __name__ == "__main__":
#     asyncio.run(main())