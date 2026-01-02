import asyncio
import time
import json
import sys
import os
from fastapi import FastAPI, Query, HTTPException, Body
from typing import Dict, List

from search_tag import run_scraper, collect_companies_with_descriptions, collect_companies_with_rank, scrape_top_companies
from database import get_all_companies, get_companies_by_names, get_companies_summary, delete_all_companies, delete_company

# Add Crunchbase Data folder to path for similarity_search import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Crunchbase Data"))
try:
    from similarity_search import find_similar_companies
    SIMILARITY_SEARCH_AVAILABLE = True
except ImportError:
    SIMILARITY_SEARCH_AVAILABLE = False
    print("Warning: similarity_search module not available. /search/crunchbase/top-similar endpoint will be disabled.")

app = FastAPI()

# Status callback URL for progress updates
# In local deployment, calls backend directly
# In remote deployment with worker agent, calls the worker agent's status proxy
STATUS_CALLBACK_URL = os.getenv('STATUS_CALLBACK_URL', 'http://worker_agent:9099')

# Global dictionary to track active requests and cancellation flags
active_requests = {}


@app.get("/health")
async def health_check():
    """Health check endpoint for worker agent to verify API is ready."""
    return {"status": "healthy", "api": "crunchbase"}

@app.post("/cancel/{request_id}")
async def cancel_request(request_id: str):
    """Cancel an active scraping request."""
    if request_id in active_requests:
        active_requests[request_id]["cancelled"] = True
        print(f"🛑 Request {request_id} marked for cancellation")
        return {"status": "cancelled", "request_id": request_id}
    else:
        print(f"⚠️ Request {request_id} not found in active requests")
        return {"status": "not_found", "request_id": request_id}

@app.get("/search/crunchbase")
async def search_hashtag(
    hashtag: str = Query(..., description="Hashtag or keyword to search"),
    num_companies: int = Query(5, description="Number of companies to scrape"),
    days_threshold: int = Query(15, description="Days threshold to skip recently scraped companies")
) -> Dict:
    try:
        result = await run_scraper(
            hashtag,
            num_companies=num_companies,
            days_threshold=days_threshold
        )
        return {"data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail={"error": "Scraper timed out"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/search/crunchbase/batch")
async def search_hashtags_batch(
    keywords: List[str] = Body(..., description="List of keywords/hashtags to search"),
    num_companies: int = Body(5, description="Number of companies to scrape per keyword"),
    days_threshold: int = Body(15, description="Days threshold to skip recently scraped companies")
) -> Dict:
    """
    Search for companies using multiple keywords in batch.
    Each keyword will be processed sequentially to scrape companies.
    Returns results organized by keyword with metadata.
    """
    try:
        keyword_results = []
        total_companies = 0
        total_time = 0
        
        for keyword in keywords:
            start_time = time.time()
            try:
                result = await run_scraper(
                    keyword,
                    num_companies=num_companies,
                    days_threshold=days_threshold
                )
                elapsed_time = time.time() - start_time
                
                keyword_data = {
                    "keyword": keyword,
                    "companies": result,
                    "count": len(result),
                    "time_taken_seconds": round(elapsed_time, 2),
                    "status": "success"
                }
                keyword_results.append(keyword_data)
                total_companies += len(result)
                total_time += elapsed_time
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"Error processing keyword '{keyword}': {e}")
                keyword_data = {
                    "keyword": keyword,
                    "companies": [],
                    "count": 0,
                    "time_taken_seconds": round(elapsed_time, 2),
                    "status": "failed",
                    "error": str(e)
                }
                keyword_results.append(keyword_data)
                total_time += elapsed_time
        
        return {
            "results": keyword_results,
            "summary": {
                "total_keywords": len(keywords),
                "successful_keywords": sum(1 for r in keyword_results if r["status"] == "success"),
                "failed_keywords": sum(1 for r in keyword_results if r["status"] == "failed"),
                "total_companies_found": total_companies,
                "total_time_seconds": round(total_time, 2)
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/search/crunchbase/top")
async def search_top_companies(
    keywords: List[str] = Body(..., description="List of keywords/hashtags to search"),
    num_companies: int = Body(10, description="Number of companies to scrape per keyword"),
    days_threshold: int = Body(15, description="Days threshold to skip recently scraped companies"),
    top_count: int = Body(10, description="Number of top companies to return")
) -> Dict:
    """
    Search for companies using multiple keywords and return top companies by appearance frequency.
    
    This endpoint:
    1. Searches each keyword for the specified number of companies
    2. Aggregates all results and counts appearances (identified by unique URL)
    3. Returns top N companies sorted by number of appearances across all keyword searches
    4. Includes metadata about which keywords each company appeared in
    
    Example: If searching 10 keywords for 10 companies each, companies appearing in multiple
    keyword searches will be ranked higher.
    """
    try:
        # Dictionary to track company appearances: {url: {data, keywords, count}}
        company_tracker = {}
        total_time = 0
        successful_keywords = 0
        failed_keywords = 0
        
        for keyword in keywords:
            start_time = time.time()
            try:
                result = await run_scraper(
                    keyword,
                    num_companies=num_companies,
                    days_threshold=days_threshold
                )
                elapsed_time = time.time() - start_time
                total_time += elapsed_time
                successful_keywords += 1
                
                # Track each company found in this keyword search
                for company in result:
                    url = company.get("url")
                    if not url:
                        continue
                        
                    if url in company_tracker:
                        # Company already seen - increment count and add keyword
                        company_tracker[url]["appearance_count"] += 1
                        company_tracker[url]["keywords"].append(keyword)
                    else:
                        # First time seeing this company
                        company_tracker[url] = {
                            "company_data": company,
                            "appearance_count": 1,
                            "keywords": [keyword],
                            "url": url
                        }
                
                print(f"✅ Processed keyword '{keyword}': {len(result)} companies in {elapsed_time:.2f}s")
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                total_time += elapsed_time
                failed_keywords += 1
                print(f"❌ Error processing keyword '{keyword}': {e}")
        
        # Sort companies by appearance count (descending)
        sorted_companies = sorted(
            company_tracker.values(),
            key=lambda x: x["appearance_count"],
            reverse=True
        )
        
        # Get top N companies
        top_companies = sorted_companies[:top_count]
        
        # Format the response
        formatted_top_companies = [
            {
                "company_data": company["company_data"],
                "appearance_count": company["appearance_count"],
                "keywords": company["keywords"],
                "url": company["url"]
            }
            for company in top_companies
        ]
        
        return {
            "top_companies": formatted_top_companies,
            "metadata": {
                "total_keywords_searched": len(keywords),
                "successful_keywords": successful_keywords,
                "failed_keywords": failed_keywords,
                "total_unique_companies": len(company_tracker),
                "top_count_requested": top_count,
                "top_count_returned": len(formatted_top_companies),
                "total_time_seconds": round(total_time, 2)
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/search/crunchbase/top-similar")
async def search_top_similar_companies(
    keywords: List[str] = Body(..., description="List of keywords/hashtags to search"),
    num_companies: int = Body(10, description="Number of companies to collect per keyword from search table"),
    days_threshold: int = Body(15, description="Days threshold to skip recently scraped companies"),
    top_count: int = Body(10, description="Number of top similar companies to scrape and return"),
    target_description: str = Body(..., description="Target description to compare companies against for similarity")
) -> Dict:
    """
    NEW WORKFLOW: Search for companies using multiple keywords, rank by similarity, then scrape top companies.
    
    This endpoint:
    1. For each keyword, collects company URLs and full descriptions from search table (without scraping pages)
    2. Aggregates all unique companies (identified by unique URL)
    3. Uses AI-powered similarity search to compare each company's description against the target description
    4. Sorts all companies by similarity score (highest first)
    5. Scrapes only the top N companies (if not fresh in database)
    6. Returns scraped company data with similarity scores and metadata
    
    Benefits of this approach:
    - Much faster: only scrapes top companies after similarity ranking
    - More efficient: uses descriptions from search table for similarity comparison
    - Better results: ranks ALL found companies before deciding which to scrape
    
    The similarity search uses sentence transformers to generate embeddings and calculate
    cosine similarity between company descriptions and the target description.
    """
    if not SIMILARITY_SEARCH_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={"error": "Similarity search functionality is not available. Please ensure the similarity_search module is installed."}
        )
    
    try:
        # Dictionary to track companies: {url: {description, keywords, count}}
        company_tracker = {}
        collection_time = 0
        successful_keywords = 0
        failed_keywords = 0
        
        # Step 1: Collect company URLs and descriptions from search tables
        print(f"\n=== Step 1: Collecting companies from {len(keywords)} keywords ===")
        for keyword in keywords:
            start_time = time.time()
            try:
                companies_data = await collect_companies_with_descriptions(
                    keyword,
                    num_companies=num_companies
                )
                elapsed_time = time.time() - start_time
                collection_time += elapsed_time
                successful_keywords += 1
                
                # Track each company found in this keyword search
                for company in companies_data:
                    url = company.get("url")
                    description = company.get("description", "")
                    
                    if not url or not description:
                        continue
                        
                    if url in company_tracker:
                        # Company already seen - increment count and add keyword
                        company_tracker[url]["appearance_count"] += 1
                        if keyword not in company_tracker[url]["keywords"]:
                            company_tracker[url]["keywords"].append(keyword)
                    else:
                        # First time seeing this company
                        company_tracker[url] = {
                            "description": description,
                            "appearance_count": 1,
                            "keywords": [keyword],
                            "url": url
                        }
                
                print(f"✅ Collected from '{keyword}': {len(companies_data)} companies in {elapsed_time:.2f}s")
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                collection_time += elapsed_time
                failed_keywords += 1
                print(f"❌ Error collecting from keyword '{keyword}': {e}")
        
        # Check if we found any companies
        if not company_tracker:
            return {
                "top_companies": [],
                "metadata": {
                    "total_keywords_searched": len(keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_unique_companies": 0,
                    "top_count_requested": top_count,
                    "top_count_returned": 0,
                    "collection_time_seconds": round(collection_time, 2),
                    "similarity_time_seconds": 0,
                    "scraping_time_seconds": 0,
                    "total_time_seconds": round(collection_time, 2)
                }
            }
        
        print(f"\n=== Step 2: Ranking {len(company_tracker)} unique companies by similarity ===")
        
        # Prepare companies for similarity search
        companies_for_similarity = []
        for url, tracker_data in company_tracker.items():
            companies_for_similarity.append({
                "url": url,
                "description": tracker_data["description"]
            })
        
        # Perform similarity search
        similarity_start = time.time()
        companies_json = json.dumps(companies_for_similarity)
        
        try:
            similar_companies = find_similar_companies(
                companies_json=companies_json,
                target_description=target_description,
                top_k=None  # Get all, we'll filter to top_count for scraping
            )
            similarity_time = time.time() - similarity_start
            
            print(f"✅ Similarity ranking completed in {similarity_time:.2f}s")
            
            # Get top N URLs to scrape
            top_urls_to_scrape = [comp["url"] for comp in similar_companies[:top_count]]
            
            print(f"\n=== Step 3: Scraping top {len(top_urls_to_scrape)} companies ===")
            
            # Step 3: Scrape only the top companies
            scraping_start = time.time()
            scraped_companies = await scrape_top_companies(
                top_urls_to_scrape,
                days_threshold=days_threshold
            )
            scraping_time = time.time() - scraping_start
            
            print(f"✅ Scraping completed in {scraping_time:.2f}s")
            
            # Combine scraped data with similarity scores
            # Create URL to scraped data mapping
            scraped_map = {comp.get("url"): comp for comp in scraped_companies if comp}
            
            # Build final results
            final_results = []
            for i, similar_comp in enumerate(similar_companies[:top_count]):
                url = similar_comp["url"]
                tracker_data = company_tracker.get(url, {})
                scraped_data = scraped_map.get(url)
                
                if scraped_data:
                    final_results.append({
                        "company_data": scraped_data,
                        "similarity_score": similar_comp["similarity_score"],
                        "similarity_rank": i + 1,
                        "appearance_count": tracker_data.get("appearance_count", 1),
                        "keywords": tracker_data.get("keywords", []),
                        "url": url
                    })
                else:
                    # Company wasn't scraped (might have failed)
                    print(f"⚠️ Company {url} was not scraped")
            
            total_time = collection_time + similarity_time + scraping_time
            
            return {
                "top_companies": final_results,
                "metadata": {
                    "total_keywords_searched": len(keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_unique_companies": len(company_tracker),
                    "top_count_requested": top_count,
                    "top_count_returned": len(final_results),
                    "target_description": target_description,
                    "collection_time_seconds": round(collection_time, 2),
                    "similarity_time_seconds": round(similarity_time, 2),
                    "scraping_time_seconds": round(scraping_time, 2),
                    "total_time_seconds": round(total_time, 2)
                }
            }
            
        except Exception as e:
            print(f"Error in similarity search: {e}")
            raise HTTPException(
                status_code=500,
                detail={"error": f"Similarity search failed: {str(e)}"}
            )
            
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/search/crunchbase/top-similar-full")
async def search_top_similar_companies_full(
    keywords: List[str] = Body(..., description="List of keywords/hashtags to search"),
    num_companies: int = Body(10, description="Number of companies to collect per keyword from search table"),
    days_threshold: int = Body(15, description="Days threshold to skip recently scraped companies"),
    top_count: int = Body(10, description="Number of top similar companies to scrape and return full data"),
    target_description: str = Body(..., description="Target description to compare companies against for similarity")
) -> Dict:
    """
    Enhanced similarity search that returns ALL companies sorted by similarity, plus full data for top companies.
    
    This endpoint:
    1. For each keyword, collects company URLs and descriptions from search table
    2. Aggregates all unique companies (identified by URL)
    3. Uses AI-powered similarity search to compare each company's description against target description
    4. Returns ALL companies sorted by similarity score (with descriptions and metadata)
    5. Additionally scrapes and returns full company data for the top N most similar companies
    
    Response structure:
    - all_companies: List of ALL companies sorted by similarity (includes description, similarity_score, keywords, appearance_count)
    - top_companies_full_data: Full scraped data for the top N most similar companies
    - metadata: Statistics about the search process
    
    This gives you both the complete ranked list AND detailed information about the most relevant companies.
    """
    if not SIMILARITY_SEARCH_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={"error": "Similarity search functionality is not available. Please ensure the similarity_search module is installed."}
        )
    
    try:
        # Dictionary to track companies: {url: {description, keywords, count}}
        company_tracker = {}
        collection_time = 0
        successful_keywords = 0
        failed_keywords = 0
        
        # Step 1: Collect company URLs and descriptions from search tables
        print(f"\n=== Step 1: Collecting companies from {len(keywords)} keywords ===")
        for keyword in keywords:
            start_time = time.time()
            try:
                companies_data = await collect_companies_with_descriptions(
                    keyword,
                    num_companies=num_companies
                )
                elapsed_time = time.time() - start_time
                collection_time += elapsed_time
                successful_keywords += 1
                
                # Track each company found in this keyword search
                for company in companies_data:
                    url = company.get("url")
                    description = company.get("description", "")
                    
                    if not url or not description:
                        continue
                        
                    if url in company_tracker:
                        # Company already seen - increment count and add keyword
                        company_tracker[url]["appearance_count"] += 1
                        if keyword not in company_tracker[url]["keywords"]:
                            company_tracker[url]["keywords"].append(keyword)
                    else:
                        # First time seeing this company
                        company_tracker[url] = {
                            "description": description,
                            "appearance_count": 1,
                            "keywords": [keyword],
                            "url": url
                        }
                
                print(f"✅ Collected from '{keyword}': {len(companies_data)} companies in {elapsed_time:.2f}s")
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                collection_time += elapsed_time
                failed_keywords += 1
                print(f"❌ Error collecting from keyword '{keyword}': {e}")
        
        # Check if we found any companies
        if not company_tracker:
            return {
                "all_companies": [],
                "top_companies_full_data": [],
                "metadata": {
                    "total_keywords_searched": len(keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_unique_companies": 0,
                    "all_companies_count": 0,
                    "top_count_requested": top_count,
                    "top_count_returned": 0,
                    "collection_time_seconds": round(collection_time, 2),
                    "similarity_time_seconds": 0,
                    "scraping_time_seconds": 0,
                    "total_time_seconds": round(collection_time, 2)
                }
            }
        
        print(f"\n=== Step 2: Ranking {len(company_tracker)} unique companies by similarity ===")
        
        # Prepare companies for similarity search
        companies_for_similarity = []
        for url, tracker_data in company_tracker.items():
            companies_for_similarity.append({
                "url": url,
                "description": tracker_data["description"]
            })
        
        # Perform similarity search on ALL companies
        similarity_start = time.time()
        companies_json = json.dumps(companies_for_similarity)
        
        try:
            similar_companies = find_similar_companies(
                companies_json=companies_json,
                target_description=target_description,
                top_k=None  # Get ALL companies sorted
            )
            similarity_time = time.time() - similarity_start
            
            print(f"✅ Similarity ranking completed in {similarity_time:.2f}s")
            
            # Build the ALL companies response with similarity scores
            all_companies_response = []
            for i, similar_comp in enumerate(similar_companies):
                url = similar_comp["url"]
                tracker_data = company_tracker.get(url, {})
                
                all_companies_response.append({
                    "url": url,
                    "description": similar_comp["description"],
                    "similarity_score": similar_comp["similarity_score"],
                    "similarity_rank": i + 1,
                    "appearance_count": tracker_data.get("appearance_count", 1),
                    "keywords": tracker_data.get("keywords", [])
                })
            
            # Get top N URLs to scrape for full data
            top_urls_to_scrape = [comp["url"] for comp in similar_companies[:top_count]]
            
            print(f"\n=== Step 3: Scraping top {len(top_urls_to_scrape)} companies for full data ===")
            
            # Step 3: Scrape only the top companies
            scraping_start = time.time()
            scraped_companies = await scrape_top_companies(
                top_urls_to_scrape,
                days_threshold=days_threshold
            )
            scraping_time = time.time() - scraping_start
            
            print(f"✅ Scraping completed in {scraping_time:.2f}s")
            
            # Create URL to scraped data mapping
            scraped_map = {comp.get("url"): comp for comp in scraped_companies if comp}
            
            # Build full data results for top companies
            top_companies_full_data = []
            for i, similar_comp in enumerate(similar_companies[:top_count]):
                url = similar_comp["url"]
                tracker_data = company_tracker.get(url, {})
                scraped_data = scraped_map.get(url)
                
                if scraped_data:
                    top_companies_full_data.append({
                        "company_data": scraped_data,
                        "similarity_score": similar_comp["similarity_score"],
                        "similarity_rank": i + 1,
                        "appearance_count": tracker_data.get("appearance_count", 1),
                        "keywords": tracker_data.get("keywords", []),
                        "url": url
                    })
                else:
                    # Company wasn't scraped (might have failed)
                    print(f"⚠️ Company {url} was not scraped")
            
            total_time = collection_time + similarity_time + scraping_time
            
            return {
                "all_companies": all_companies_response,
                "top_companies_full_data": top_companies_full_data,
                "metadata": {
                    "total_keywords_searched": len(keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_unique_companies": len(company_tracker),
                    "all_companies_count": len(all_companies_response),
                    "top_count_requested": top_count,
                    "top_count_returned": len(top_companies_full_data),
                    "target_description": target_description,
                    "collection_time_seconds": round(collection_time, 2),
                    "similarity_time_seconds": round(similarity_time, 2),
                    "scraping_time_seconds": round(scraping_time, 2),
                    "total_time_seconds": round(total_time, 2)
                }
            }
            
        except Exception as e:
            print(f"Error in similarity search: {e}")
            raise HTTPException(
                status_code=500,
                detail={"error": f"Similarity search failed: {str(e)}"}
            )
            
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/search/crunchbase/top-similar-with-rank")
async def search_top_similar_companies_with_rank(
    keywords: List[str] = Body(..., description="List of keywords/hashtags to search"),
    num_companies: int = Body(10, description="Number of companies to collect per keyword from search table"),
    days_threshold: int = Body(15, description="Days threshold to skip recently scraped companies"),
    top_count: int = Body(10, description="Number of top companies to scrape and return full data"),
    target_description: str = Body(..., description="Target description to compare companies against for similarity"),
    similarity_weight: float = Body(0.75, description="Weight for similarity score (0-1)"),
    rank_weight: float = Body(0.25, description="Weight for rank score (0-1)"),
    request_id: str = Body(None, description="Request ID for tracking and cancellation"),
    report_id: str = Body(None, description="Report ID (UUID) for real-time status updates to backend")
) -> Dict:
    """
    Enhanced similarity search that combines AI-powered similarity scoring with Crunchbase rank scoring.
    
    This endpoint:
    1. For each keyword, collects company URLs, descriptions, and CB rank from search table
    2. Aggregates all unique companies (identified by URL)
    3. Uses AI-powered similarity search to compare each company's description against target description
    4. Normalizes CB rank to a score between 0-1 (where smallest rank = 1.0, largest rank = 0.0)
    5. Combines similarity and rank scores using weighted formula: combined_score = (similarity * similarity_weight) + (rank_score * rank_weight)
    6. Returns ALL companies sorted by combined score (with description, similarity_score, rank_score, cb_rank, combined_score)
    7. Additionally scrapes and returns full company data for the top N most relevant companies
    
    Scoring details:
    - Similarity score: 0-1 (higher = more similar to target description)
    - Rank score: 0-1 (1.0 for lowest CB rank number, 0.0 for highest CB rank number)
    - Combined score: weighted sum of similarity and rank scores
    
    Default weights: 75% similarity, 25% rank (configurable via parameters)
    
    Response structure:
    - all_companies: List of ALL companies sorted by combined score
    - top_companies_full_data: Full scraped data for the top N companies
    - metadata: Statistics including rank range, weights used, and timing information
    """
    if not SIMILARITY_SEARCH_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={"error": "Similarity search functionality is not available. Please ensure the similarity_search module is installed."}
        )
    
    # Validate weights
    if not (0 <= similarity_weight <= 1) or not (0 <= rank_weight <= 1):
        raise HTTPException(
            status_code=400,
            detail={"error": "Weights must be between 0 and 1"}
        )
    
    if abs((similarity_weight + rank_weight) - 1.0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Weights must sum to 1.0. Current sum: {similarity_weight + rank_weight}"}
        )
    
    # Helper function to send status updates via HTTP callback to backend
    # Uses TRUE fire-and-forget pattern - creates background task, doesn't wait
    async def _do_status_update(step_key: str, detail_type: str, message: str, data: dict = None):
        """Internal function that actually sends the HTTP request."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "report_id": report_id,
                    "step_key": step_key,
                    "detail_type": detail_type,
                    "message": message,
                    "data": data or {}
                }
                response = await client.post(
                    f"{STATUS_CALLBACK_URL}/api/reports/status-update/",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code != 200:
                    print(f"⚠️ Status callback returned {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"⚠️ Status callback failed: {type(e).__name__}: {e}")
    
    def send_status_update(step_key: str, detail_type: str, message: str, data: dict = None):
        """Fire-and-forget status update - creates background task, returns immediately."""
        if not report_id:
            return
        # Create task in background, don't await - truly non-blocking
        import asyncio
        asyncio.create_task(_do_status_update(step_key, detail_type, message, data))
    
    # Track request for cancellation
    if request_id:
        active_requests[request_id] = {"cancelled": False, "created_at": time.time()}
        print(f"📝 Tracking request {request_id}")
    
    try:
        # Note: Keywords are already shown in the init step, so we skip showing them again
        # Just log locally that we're starting the search
        print(f"\n=== Step 1: Collecting companies with CB rank from {len(keywords)} keywords ===")
        
        # Dictionary to track companies: {url: {description, cb_rank, keywords, count}}
        company_tracker = {}
        # Dictionary to track per-keyword results: {keyword: {count: int, top_companies: [{name, cb_rank}]}}
        keyword_results = {}
        collection_time = 0
        successful_keywords = 0
        failed_keywords = 0
        
        # Step 1: Collect company URLs, descriptions, and CB ranks from search tables
        print(f"\n=== Step 1: Collecting companies with CB rank from {len(keywords)} keywords ===")
        for idx, keyword in enumerate(keywords, 1):
            # Check for cancellation
            if request_id and request_id in active_requests and active_requests[request_id]["cancelled"]:
                print(f"🛑 Request {request_id} cancelled during company collection")
                return {"error": "Request was cancelled", "cancelled": True}
            
            # Log locally (no pre-search callback - we send result after search completes)
            print(f"🔍 Searching keyword {idx}/{len(keywords)}: '{keyword}'...")
            
            start_time = time.time()
            try:
                companies_data = await collect_companies_with_rank(
                    keyword,
                    num_companies=num_companies
                )
                elapsed_time = time.time() - start_time
                collection_time += elapsed_time
                successful_keywords += 1
                
                # Track each company found in this keyword search
                for company in companies_data:
                    url = company.get("url")
                    description = company.get("description", "")
                    cb_rank = company.get("cb_rank")
                    
                    if not url or not description or cb_rank is None:
                        continue
                        
                    if url in company_tracker:
                        # Company already seen - increment count and add keyword
                        company_tracker[url]["appearance_count"] += 1
                        if keyword not in company_tracker[url]["keywords"]:
                            company_tracker[url]["keywords"].append(keyword)
                        # Keep the best (lowest) rank if company appears multiple times
                        if cb_rank < company_tracker[url]["cb_rank"]:
                            company_tracker[url]["cb_rank"] = cb_rank
                    else:
                        # First time seeing this company
                        company_tracker[url] = {
                            "description": description,
                            "cb_rank": cb_rank,
                            "appearance_count": 1,
                            "keywords": [keyword],
                            "url": url
                        }
                
                print(f"✅ Collected from '{keyword}': {len(companies_data)} companies in {elapsed_time:.2f}s")
                
                # Sort companies by CB rank (ascending - lower is better) and get top 5
                sorted_companies = sorted(
                    [c for c in companies_data if c.get("cb_rank") is not None],
                    key=lambda x: x.get("cb_rank", float('inf'))
                )[:5]
                
                # Build top 5 companies list with name and CB rank
                top_5_companies = []
                for company in sorted_companies:
                    url = company.get("url", "")
                    name = url.split("/")[-1].replace("-", " ").title() if url else "Unknown"
                    top_5_companies.append({
                        "name": name,
                        "cb_rank": company.get("cb_rank")
                    })
                
                # Store in keyword_results for metadata
                keyword_results[keyword] = {
                    "count": len(companies_data),
                    "top_companies": top_5_companies
                }
                
                send_status_update(
                    "api_search",
                    "search_result",
                    f"'{keyword}' → {len(companies_data)} companies found",
                    {
                        "keyword": keyword,
                        "company_count": len(companies_data),
                        "top_companies": top_5_companies,
                        "index": idx,
                        "total": len(keywords)
                    }
                )
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                collection_time += elapsed_time
                failed_keywords += 1
                print(f"❌ Error collecting from keyword '{keyword}': {e}")
        
        # Check if we found any companies
        if not company_tracker:
            return {
                "all_companies": [],
                "top_companies_full_data": [],
                "metadata": {
                    "total_keywords_searched": len(keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_unique_companies": 0,
                    "all_companies_count": 0,
                    "top_count_requested": top_count,
                    "top_count_returned": 0,
                    "similarity_weight": similarity_weight,
                    "rank_weight": rank_weight,
                    "collection_time_seconds": round(collection_time, 2),
                    "similarity_time_seconds": 0,
                    "scraping_time_seconds": 0,
                    "total_time_seconds": round(collection_time, 2)
                }
            }
        
        # Send status: Sorting companies
        send_status_update(
            "sorting",
            "sorting_start",
            f"Sorting {len(company_tracker)} companies by relevance",
            {"total_companies": len(company_tracker)}
        )
        
        print(f"\n=== Step 2: Calculating similarity and rank scores for {len(company_tracker)} unique companies ===")
        
        # Find min and max CB rank for normalization
        all_ranks = [tracker_data["cb_rank"] for tracker_data in company_tracker.values()]
        min_rank = min(all_ranks)
        max_rank = max(all_ranks)
        rank_range = max_rank - min_rank
        
        print(f"CB Rank range: {min_rank} (best) to {max_rank} (worst)")
        
        # Prepare companies for similarity search
        companies_for_similarity = []
        for url, tracker_data in company_tracker.items():
            companies_for_similarity.append({
                "url": url,
                "description": tracker_data["description"]
            })
        
        # Perform similarity search on ALL companies
        similarity_start = time.time()
        companies_json = json.dumps(companies_for_similarity)
        
        try:
            similar_companies = find_similar_companies(
                companies_json=companies_json,
                target_description=target_description,
                top_k=None  # Get ALL companies sorted
            )
            similarity_time = time.time() - similarity_start
            
            # Check for cancellation after similarity calculation
            if request_id and request_id in active_requests and active_requests[request_id]["cancelled"]:
                print(f"🛑 Request {request_id} cancelled after similarity calculation")
                return {"error": "Request was cancelled", "cancelled": True}
            
            print(f"✅ Similarity ranking completed in {similarity_time:.2f}s")
            
            # Send status: Companies ranked
            send_status_update(
                "sorting",
                "top_companies",
                f"Top {top_count} companies selected",
                {"total_companies": len(similar_companies)}
            )
            
            # Calculate rank scores and combined scores
            all_companies_with_scores = []
            for similar_comp in similar_companies:
                url = similar_comp["url"]
                tracker_data = company_tracker.get(url, {})
                cb_rank = tracker_data.get("cb_rank")
                
                # Calculate rank score (0-1, where 1 is best rank, 0 is worst rank)
                if rank_range > 0:
                    rank_score = 1.0 - ((cb_rank - min_rank) / rank_range)
                else:
                    # All ranks are the same
                    rank_score = 1.0
                
                similarity_score = similar_comp["similarity_score"]
                
                # Calculate combined score using weights
                combined_score = (similarity_score * similarity_weight) + (rank_score * rank_weight)
                
                all_companies_with_scores.append({
                    "url": url,
                    "description": similar_comp["description"],
                    "similarity_score": similarity_score,
                    "cb_rank": cb_rank,
                    "rank_score": round(rank_score, 4),
                    "combined_score": round(combined_score, 4),
                    "appearance_count": tracker_data.get("appearance_count", 1),
                    "keywords": tracker_data.get("keywords", [])
                })
            
            # Sort by combined score (descending)
            all_companies_with_scores.sort(key=lambda x: x["combined_score"], reverse=True)
            
            # Add ranks
            for i, company in enumerate(all_companies_with_scores):
                company["combined_rank"] = i + 1
            
            # Get top N URLs to scrape for full data (based on combined score)
            top_urls_to_scrape = [comp["url"] for comp in all_companies_with_scores[:top_count]]
            
            # Extract company names for status update
            top_company_names = [comp["url"].split("/")[-1].replace("-", " ").title() for comp in all_companies_with_scores[:top_count]]
            
            # Send status: Top companies selected
            send_status_update(
                "fetching_details",
                "company_found",
                f"Scraping top {len(top_urls_to_scrape)} companies",
                {"companies": top_company_names[:10]}
            )
            
            print(f"\n=== Step 3: Scraping top {len(top_urls_to_scrape)} companies for full data ===")
            
            # Step 3: Scrape only the top companies
            scraping_start = time.time()
            scraped_companies = await scrape_top_companies(
                top_urls_to_scrape,
                days_threshold=days_threshold,
                status_callback=send_status_update
            )
            scraping_time = time.time() - scraping_start
            
            # Send final scraping complete status
            send_status_update(
                "fetching_details",
                "company_processing",
                f"Completed scraping {len(scraped_companies)} companies",
                {"companies_scraped": len(scraped_companies)}
            )
            
            print(f"✅ Scraping completed in {scraping_time:.2f}s")
            
            # Create URL to scraped data mapping
            scraped_map = {comp.get("url"): comp for comp in scraped_companies if comp}
            
            # Build full data results for top companies
            top_companies_full_data = []
            for comp_data in all_companies_with_scores[:top_count]:
                url = comp_data["url"]
                scraped_data = scraped_map.get(url)
                
                if scraped_data:
                    top_companies_full_data.append({
                        "company_data": scraped_data,
                        "similarity_score": comp_data["similarity_score"],
                        "cb_rank": comp_data["cb_rank"],
                        "rank_score": comp_data["rank_score"],
                        "combined_score": comp_data["combined_score"],
                        "combined_rank": comp_data["combined_rank"],
                        "appearance_count": comp_data["appearance_count"],
                        "keywords": comp_data["keywords"],
                        "url": url
                    })
                else:
                    # Company wasn't scraped (might have failed)
                    print(f"⚠️ Company {url} was not scraped")
            
            total_time = collection_time + similarity_time + scraping_time
            
            # Build sorted top companies list for UI display (with cb_rank and full description)
            sorted_top_companies = []
            for comp in all_companies_with_scores[:top_count]:
                name = comp["url"].split("/")[-1].replace("-", " ").title()
                sorted_top_companies.append({
                    "name": name,
                    "cb_rank": comp["cb_rank"],
                    "description": comp.get("description", ""),  # Full description, no truncation
                    "combined_score": comp["combined_score"]
                })
            
            return {
                "all_companies": all_companies_with_scores,
                "top_companies_full_data": top_companies_full_data,
                "metadata": {
                    "total_keywords_searched": len(keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_unique_companies": len(company_tracker),
                    "all_companies_count": len(all_companies_with_scores),
                    "top_count_requested": top_count,
                    "top_count_returned": len(top_companies_full_data),
                    "target_description": target_description,
                    "keyword_results": keyword_results,  # Per-keyword results with top 5 companies
                    "sorted_top_companies": sorted_top_companies,  # Final sorted top companies for step 3
                    "cb_rank_range": {
                        "min_rank": min_rank,
                        "max_rank": max_rank,
                        "range": rank_range
                    },
                    "weights": {
                        "similarity_weight": similarity_weight,
                        "rank_weight": rank_weight
                    },
                    "collection_time_seconds": round(collection_time, 2),
                    "similarity_time_seconds": round(similarity_time, 2),
                    "scraping_time_seconds": round(scraping_time, 2),
                    "total_time_seconds": round(total_time, 2)
                }
            }
            
        except Exception as e:
            print(f"Error in similarity search: {e}")
            raise HTTPException(
                status_code=500,
                detail={"error": f"Similarity search failed: {str(e)}"}
            )
            
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})
    finally:
        # Clean up request tracking
        if request_id and request_id in active_requests:
            del active_requests[request_id]
            print(f"🗑️ Cleaned up request {request_id}")


@app.get("/companies/all")
async def get_all_companies_endpoint() -> Dict:
    """
    Retrieve all companies stored in the database.
    """
    try:
        companies = get_all_companies()
        return {
            "data": companies,
            "total": len(companies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/companies/by-names")
async def get_companies_by_names_endpoint(
    company_names: List[str] = Body(..., description="List of company names to retrieve")
) -> Dict:
    """
    Retrieve specific companies from the database by their names.
    Only returns companies that are available in the database.
    """
    try:
        companies = get_companies_by_names(company_names)
        return {
            "data": companies,
            "requested": len(company_names),
            "found": len(companies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.get("/companies/summary")
async def get_companies_summary_endpoint() -> Dict:
    """
    Retrieve all companies from the database with only URL, About section, and creation timestamp.
    Results are sorted by the freshest (most recently added) first.
    """
    try:
        companies = get_companies_summary()
        return {
            "data": companies,
            "total": len(companies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.delete("/companies/all")
async def delete_all_companies_endpoint() -> Dict:
    """
    Delete all companies from the database.
    WARNING: This action cannot be undone!
    """
    try:
        deleted_count = delete_all_companies()
        return {
            "message": "All companies deleted successfully",
            "deleted_count": deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.delete("/companies/delete")
async def delete_company_endpoint(
    url: str = Query(None, description="Company URL to delete"),
    name: str = Query(None, description="Company name to delete")
) -> Dict:
    """
    Delete a specific company from the database by URL or name.
    Provide either 'url' or 'name' parameter (not both).
    """
    try:
        if url and name:
            raise HTTPException(
                status_code=400, 
                detail={"error": "Provide either 'url' or 'name', not both"}
            )
        
        if not url and not name:
            raise HTTPException(
                status_code=400, 
                detail={"error": "Must provide either 'url' or 'name' parameter"}
            )
        
        if url:
            deleted_count = delete_company(url, by="url")
            identifier_type = "URL"
            identifier = url
        else:
            deleted_count = delete_company(name, by="name")
            identifier_type = "name"
            identifier = name
        
        if deleted_count > 0:
            return {
                "message": f"Company deleted successfully",
                "deleted_count": deleted_count,
                "identifier_type": identifier_type,
                "identifier": identifier
            }
        else:
            raise HTTPException(
                status_code=404,
                detail={"error": f"No company found with {identifier_type}: {identifier}"}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_handler:app", host="0.0.0.0", port=8003, reload=True)
