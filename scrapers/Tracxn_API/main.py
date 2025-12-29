import asyncio
from playwright.async_api import async_playwright
from tracxn_scrapper import TracxnBot

async def main(debug: bool = True):
    search_term = input("Search term: ")
    num = int(input("Number of companies (≤100): "))
    freshness = input("Database freshness (in days): ")
    sort = input("Sorting order: ")

    async with async_playwright() as playwright:
        # Step 1: Use one bot to perform search
        bot = TracxnBot(playwright, debug=debug)
        await bot.login()
        companies = await bot.search_companies(query=search_term, sort_by=sort)
        await bot.close()

        # Limit number of companies
        companies = companies[:num]

        # Step 2: Split into chunks of 5
        chunks = [companies[i:i+5] for i in range(0, len(companies), 5)]

        async def scrape_batch(batch):
            """Scrape one batch of up to 5 companies using a separate bot."""
            b = TracxnBot(playwright, debug=debug)
            await b.login()
            results = []
            for item in batch:
                r = await b.scrape_company(item)
                results.append(r)
            await b.close()
            return results

        # Step 3: Run all bots concurrently
        all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])

        # Flatten results
        result = [r for batch in all_results for r in batch]
        print(result)

if __name__ == "__main__":
    asyncio.run(main())