import time
from search_tag import collect_companies_with_rank
import asyncio
import json

async def main():
    collection_time = 0
    start_time = time.time()
    try:
        keyword="ai"
        num_companies=5
        companies_data = await collect_companies_with_rank(
            keyword,
            num_companies=num_companies
        )
        elapsed_time = time.time() - start_time
        collection_time += elapsed_time
        companies_data_json = json.dumps(companies_data)
        print(f"companies_data_json: {companies_data_json}")
        print(f"collection_time: {collection_time}")
    except Exception as ex:
        print(ex)

asyncio.run(main())