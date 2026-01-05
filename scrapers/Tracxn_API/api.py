#!/usr/bin/env python3
"""
FastAPI application for TracXN company scraper
Provides REST API endpoints for scraping and retrieving company data
"""

import asyncio
import json
import logging
import os
import sys
import time
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

from tracxn_scrapper import TracxnBot
from database import DatabaseManager
from config import DB_CONFIG

# Try to import similarity search module
try:
    from similarity_search import find_similar_companies
    SIMILARITY_SEARCH_AVAILABLE = True
except ImportError:
    SIMILARITY_SEARCH_AVAILABLE = False
    print("Warning: similarity_search module not available. /scrape-batch-api-with-rank endpoint will be disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Global database manager
db_manager = DatabaseManager()

# Global dictionary to track active requests and cancellation flags
active_requests = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        if db_manager.connect():
            db_manager.create_tables()
            logger.info("Database initialized successfully")
        else:
            logger.error("Failed to connect to database")
            raise Exception("Database connection failed")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    
    yield
    
    # Shutdown
    db_manager.disconnect()
    logger.info("Application shutdown complete")

# FastAPI app initialization
app = FastAPI(
    title="TracXN Company Scraper API",
    description="API for scraping and managing company data from TracXN platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Pydantic models for request/response
class SearchRequest(BaseModel):
    search_term: str = Field(..., description="Search term for companies")
    num_companies: int = Field(default=10, ge=1, le=100, description="Number of companies to scrape (max 100)")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")
    sort_by: str = Field(default="Total Equity Funding", description="Sorting criteria")

class BatchCompaniesRequest(BaseModel):
    company_names: List[str] = Field(..., description="List of company names to search and scrape")
    num_companies_per_search: int = Field(default=1, ge=1, le=100, description="Number of top companies to return per search term (max 100)")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")

class BatchCompaniesAPIRequest(BaseModel):
    company_names: List[str] = Field(..., description="List of company names to search and scrape via API")
    num_companies_per_search: int = Field(default=1, ge=1, le=100, description="Number of top companies to return per search term (max 100)")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")
    sort_by: str = Field(default="relevance", description="Sort field for API search (e.g., 'relevance', 'total_equity_funding')")

class BatchCompaniesAPIWithRankRequest(BaseModel):
    company_names: List[str] = Field(..., description="List of company names to search via API")
    num_companies_per_search: int = Field(default=10, ge=1, le=100, description="Number of companies to collect per keyword from API (max 100)")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")
    top_count: int = Field(..., ge=1, description="Number of top companies to scrape and return full data")
    target_description: str = Field(..., description="Target description to compare companies against for similarity")
    similarity_weight: float = Field(default=0.75, ge=0.0, le=1.0, description="Weight for similarity score (0-1)")
    score_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight for TracXN score (0-1)")
    sort_by: str = Field(default="relevance", description="Sort field for API search")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking and cancellation")
    project_id: Optional[int] = Field(default=None, description="Project ID for status updates (deprecated, use report_id)")
    report_id: Optional[str] = Field(default=None, description="Report ID for real-time status callbacks to ReportProgressTracker")

class BatchReferencesRequest(BaseModel):
    company_references: List[str] = Field(..., description="List of company reference links to scrape")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")

class BatchCompaniesWithYearFilterRequest(BaseModel):
    company_names: List[str] = Field(..., description="List of company names/keywords to search and scrape")
    from_year: int = Field(..., ge=1900, le=2100, description="Start year for founded year filter")
    to_year: int = Field(..., ge=1900, le=2100, description="End year for founded year filter")
    num_companies_per_search: int = Field(default=10, ge=1, le=100, description="Number of top companies to return per search term per year (max 100)")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")
    sort_by: str = Field(default="Total Equity Funding", description="Sorting criteria")

class ManualBulkScrapeRequest(BaseModel):
    page_url: str = Field(..., description="The TracXN page URL to navigate to and scrape companies from")
    email: Optional[str] = Field(None, description="Email for login (will prompt in terminal if not provided)")
    verification_code: Optional[str] = Field(None, description="Verification code (will prompt in terminal if not provided)")
    max_scrolls: int = Field(default=200, ge=10, le=500, description="Maximum number of scrolls to load companies")
    freshness_days: int = Field(default=180, ge=0, le=365, description="Database freshness in days")
    save_to_db: bool = Field(default=True, description="Whether to save scraped data to database")

class CompanyData(BaseModel):
    company_reference: str
    data: List[Dict[str, Any]]
    last_updated: datetime
    search_query: Optional[str] = None
    source: Optional[str] = None  # 'database' or 'scraped'
    scraping_duration_seconds: Optional[float] = None  # Time taken to scrape this company

class ScrapingResponse(BaseModel):
    message: str
    total_companies: int
    fresh_from_db: int
    newly_scraped: int
    companies: List[CompanyData]

class ExportResponse(BaseModel):
    message: str
    exported_count: int
    output_directory: str

async def scrape_companies_background(
    search_term: str,
    num_companies: int,
    freshness_days: int,
    sort_by: str
) -> Dict[str, Any]:
    """Background task for scraping companies"""
    try:
        # Ensure database connection is active
        if not db_manager.ensure_connection():
            logger.error("Failed to establish database connection")
            raise Exception("Failed to establish database connection")
        
        async with async_playwright() as playwright:
            # Step 1: Search for companies with retry logic
            company_references = []
            search_max_retries = 3
            search_retry_count = 0
            
            while search_retry_count < search_max_retries:
                search_bot = None
                try:
                    search_bot = TracxnBot(playwright, debug=False)
                    login_success = await search_bot.login()
                    
                    if not login_success:
                        logger.warning(f"Search bot login failed, attempt {search_retry_count + 1}/{search_max_retries}")
                        search_retry_count += 1
                        if search_retry_count < search_max_retries:
                            await asyncio.sleep(5)
                        continue
                    
                    # Login successful, perform search
                    company_references = await search_bot.search_companies(query=search_term, sort_by=sort_by)
                    logger.info(f"Search successful on attempt {search_retry_count + 1}, found {len(company_references)} companies")
                    break
                    
                except Exception as e:
                    logger.error(f"Error during search attempt {search_retry_count + 1}: {e}")
                    search_retry_count += 1
                    if search_retry_count < search_max_retries:
                        await asyncio.sleep(5)
                        
                finally:
                    # Always close search bot
                    if search_bot:
                        try:
                            await search_bot.close()
                        except Exception as e:
                            logger.error(f"Error closing search bot: {e}")
            
            # If search failed after all retries
            if search_retry_count >= search_max_retries or not company_references:
                raise Exception(f"Failed to search companies after {search_max_retries} attempts")
            
            # Limit number of companies
            company_references = company_references[:num_companies]
            
            # Step 2: Check which companies are fresh in database
            fresh_result = db_manager.get_fresh_companies(company_references, freshness_days)
            fresh_data = fresh_result['fresh_data']
            need_scraping = fresh_result['need_scraping']
            
            logger.info(f"Found {len(fresh_data)} fresh companies in DB, need to scrape {len(need_scraping)}")
            
            # Step 3: Scrape companies that need updating
            newly_scraped = {}
            if need_scraping:
                # Split into chunks of 4 for concurrent scraping (max 4 browsers)
                chunks = [need_scraping[i:i+4] for i in range(0, len(need_scraping), 4)]
                
                # Create semaphore to limit concurrent browsers to 4
                semaphore = asyncio.Semaphore(4)
                
                async def scrape_batch(batch):
                    """Scrape one batch of up to 4 companies with login retry logic"""
                    async with semaphore:  # Limit concurrent browsers
                        max_retries = 3
                        retry_count = 0
                        b = None
                        
                        while retry_count < max_retries:
                            login_success = False  # Initialize login_success
                            try:
                                # Create new bot instance for each retry
                                if b:
                                    try:
                                        await b.close()
                                    except Exception as e:
                                        logger.error(f"Error closing bot during retry: {e}")
                                    b = None
                                
                                b = TracxnBot(playwright, debug=False)
                                
                                # Attempt login
                                login_success = await b.login()
                                if not login_success:
                                    logger.warning(f"Login failed for batch, attempt {retry_count + 1}/{max_retries}")
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        await asyncio.sleep(5)  # Wait before retry
                                    continue
                                
                                # Login successful, proceed with scraping
                                logger.info(f"Login successful for batch on attempt {retry_count + 1}")
                                break
                                
                            except Exception as e:
                                logger.error(f"Error during login attempt {retry_count + 1}: {e}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(5)
                            finally:
                                # Always close bot if login failed and we're retrying
                                if retry_count < max_retries and b and not login_success:
                                    try:
                                        await b.close()
                                    except Exception as e:
                                        logger.error(f"Error closing failed login bot: {e}")
                                    b = None
                        
                        # If all login attempts failed, close bot and return empty results
                        if retry_count >= max_retries or not b:
                            logger.error(f"Failed to login after {max_retries} attempts, skipping batch")
                            if b:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing bot after failed login: {e}")
                            return []
                        
                        # Scrape companies in this batch
                        results = []
                        try:
                            for ref in batch:
                                try:
                                    data = await b.scrape_company(ref)
                                    
                                    # Validate data before saving
                                    if data and b.is_data_valid(data):
                                        # Save to database
                                        db_manager.save_company_data(ref, data, search_term)
                                        results.append({'reference': ref, 'data': data})
                                        logger.info(f"Successfully scraped and saved data for {ref}")
                                    else:
                                        logger.warning(f"Scraped data for {ref} is empty or invalid, not saving to database")
                                        results.append({'reference': ref, 'data': None, 'error': 'Empty or invalid data'})
                                        
                                except Exception as e:
                                    logger.error(f"Error scraping company {ref}: {e}")
                                    results.append({'reference': ref, 'data': None, 'error': str(e)})
                        finally:
                            # Always close the bot instance
                            if b:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing bot after scraping: {e}")
                        
                        return results
                
                # Run all batches concurrently with max 4 browsers
                all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])
                
                # Flatten results and only include valid data
                for batch in all_results:
                    for result in batch:
                        if result['data'] is not None:
                            newly_scraped[result['reference']] = result['data']
            
            # Step 4: Combine fresh and newly scraped data
            all_company_data = []
            
            # Add fresh data from database
            for ref, data in fresh_data.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'database'
                })
            
            # Add newly scraped data
            for ref, data in newly_scraped.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'scraped'
                })
            
            return {
                'total_companies': len(company_references),
                'fresh_from_db': len(fresh_data),
                'newly_scraped': len(newly_scraped),
                'companies': all_company_data
            }
            
    except Exception as e:
        logger.error(f"Error in background scraping task: {e}")
        raise

async def scrape_batch_companies_background(
    company_names: List[str],
    num_companies_per_search: int,
    freshness_days: int
) -> Dict[str, Any]:
    """Background task for scraping a batch of companies by name"""
    try:
        # Ensure database connection is active
        if not db_manager.ensure_connection():
            logger.error("Failed to establish database connection")
            raise Exception("Failed to establish database connection")
        
        async with async_playwright() as playwright:
            # Step 1: Search for each company and get their links
            company_references = []
            search_results = {}  # Track which search term led to which reference
            
            search_max_retries = 3
            search_retry_count = 0
            
            while search_retry_count < search_max_retries:
                search_bot = None
                try:
                    search_bot = TracxnBot(playwright, debug=False)
                    login_success = await search_bot.login()
                    
                    if not login_success:
                        logger.warning(f"Search bot login failed, attempt {search_retry_count + 1}/{search_max_retries}")
                        search_retry_count += 1
                        if search_retry_count < search_max_retries:
                            await asyncio.sleep(5)
                        continue
                    
                    # Login successful, search for each company
                    logger.info(f"Search bot login successful, searching for {len(company_names)} companies")
                    
                    for company_name in company_names:
                        try:
                            logger.info(f"Searching for company: {company_name}")
                            try:
                                results = await search_bot.search_companies(query=company_name, type="all", sort_by="Total Equity Funding")
                            except Exception as e:
                                logger.error(f"Error during search for '{company_name}': {e}")
                                results = []
                            if results and len(results) > 0:
                                # Take the top N results based on num_companies_per_search
                                top_results = results[:num_companies_per_search]
                                for idx, result in enumerate(top_results):
                                    if result:  # Check if not None
                                        company_references.append(result)
                                        search_results[result] = company_name
                                        logger.info(f"Found company reference #{idx+1} for '{company_name}': {result}")
                                    else:
                                        logger.warning(f"Invalid reference at position {idx} for '{company_name}'")
                                
                                if top_results:
                                    logger.info(f"Found {len(top_results)} company references for '{company_name}'")
                                else:
                                    logger.warning(f"No valid references found for '{company_name}'")
                            else:
                                logger.warning(f"No search results found for '{company_name}'")
                            
                            # Small delay between searches to be respectful
                            await asyncio.sleep(2)
                            
                        except Exception as e:
                            logger.error(f"Error searching for company '{company_name}': {e}")
                            continue
                    
                    logger.info(f"Search successful, found {len(company_references)} company references")
                    logger.info(f"Company references: {company_references}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error during search attempt {search_retry_count + 1}: {e}")
                    search_retry_count += 1
                    if search_retry_count < search_max_retries:
                        await asyncio.sleep(5)
                        
                finally:
                    # Always close search bot
                    if search_bot:
                        try:
                            await search_bot.close()
                        except Exception as e:
                            logger.error(f"Error closing search bot: {e}")
            
            # If search failed after all retries
            if search_retry_count >= search_max_retries:
                raise Exception(f"Failed to search companies after {search_max_retries} attempts")
            
            if not company_references:
                logger.warning("No company references found for any of the provided names")
                return {
                    'total_companies': 0,
                    'fresh_from_db': 0,
                    'newly_scraped': 0,
                    'companies': []
                }
            
            # Remove duplicates while preserving the first search term for each reference
            original_count = len(company_references)
            unique_references = []
            seen_references = set()
            unique_search_results = {}
            
            for ref in company_references:
                if ref not in seen_references:
                    seen_references.add(ref)
                    unique_references.append(ref)
                    # Keep the first search query that found this reference
                    if ref in search_results and ref not in unique_search_results:
                        unique_search_results[ref] = search_results[ref]
            
            company_references = unique_references
            search_results = unique_search_results
            
            if original_count > len(company_references):
                logger.info(f"Removed {original_count - len(company_references)} duplicate company references. Unique companies: {len(company_references)}")
            
            # Step 2: Scrape companies with per-company freshness check
            # This handles concurrent scraping across multiple servers
            newly_scraped = {}
            fresh_data = {}
            
            # Split into chunks of 4 for concurrent scraping (max 4 browsers)
            chunks = [company_references[i:i+4] for i in range(0, len(company_references), 4)]
            
            # Create semaphore to limit concurrent browsers to 4
            semaphore = asyncio.Semaphore(4)
            
            async def scrape_batch(batch):
                """Scrape one batch of up to 4 companies with per-company freshness check"""
                async with semaphore:  # Limit concurrent browsers
                    max_retries = 3
                    retry_count = 0
                    b = None
                    
                    while retry_count < max_retries:
                        login_success = False
                        try:
                            # Create new bot instance for each retry
                            if b:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing bot during retry: {e}")
                                b = None
                            
                            b = TracxnBot(playwright, debug=False)
                            
                            # Attempt login
                            login_success = await b.login()
                            if not login_success:
                                logger.warning(f"Login failed for batch, attempt {retry_count + 1}/{max_retries}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(5)
                                continue
                            
                            # Login successful, proceed with scraping
                            logger.info(f"Login successful for batch on attempt {retry_count + 1}")
                            break
                            
                        except Exception as e:
                            logger.error(f"Error during login attempt {retry_count + 1}: {e}")
                            retry_count += 1
                            if retry_count < max_retries:
                                await asyncio.sleep(5)
                        finally:
                            # Always close bot if login failed and we're retrying
                            if retry_count < max_retries and b and not login_success:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing failed login bot: {e}")
                                b = None
                    
                    # If all login attempts failed, close bot and return empty results
                    if retry_count >= max_retries or not b:
                        logger.error(f"Failed to login after {max_retries} attempts, skipping batch")
                        if b:
                            try:
                                await b.close()
                            except Exception as e:
                                logger.error(f"Error closing bot after failed login: {e}")
                        return []
                    
                    # Scrape companies in this batch
                    results = []
                    try:
                        for ref in batch:
                            # Check freshness before scraping each company
                            fresh_check = db_manager.get_fresh_companies([ref], freshness_days)
                            
                            if ref in fresh_check['fresh_data']:
                                # Company is fresh in database, use cached data
                                logger.info(f"Using fresh data from database for {ref}")
                                results.append({
                                    'reference': ref,
                                    'data': fresh_check['fresh_data'][ref],
                                    'duration': 0,
                                    'from_cache': True
                                })
                                continue
                            
                            # Company needs scraping
                            scrape_start_time = datetime.now()
                            try:
                                data = await b.scrape_company(ref)
                                scrape_duration = (datetime.now() - scrape_start_time).total_seconds()
                                
                                # Validate data before saving
                                if data and b.is_data_valid(data):
                                    # Get original search query for this reference
                                    search_query = search_results.get(ref, None)
                                    # Save to database
                                    db_manager.save_company_data(ref, data, search_query)
                                    results.append({
                                        'reference': ref, 
                                        'data': data,
                                        'duration': scrape_duration,
                                        'from_cache': False
                                    })
                                    logger.info(f"Successfully scraped and saved data for {ref} in {scrape_duration:.2f}s")
                                else:
                                    logger.warning(f"Scraped data for {ref} is empty or invalid, not saving to database")
                                    results.append({
                                        'reference': ref, 
                                        'data': None, 
                                        'error': 'Empty or invalid data',
                                        'duration': scrape_duration,
                                        'from_cache': False
                                    })
                                    
                            except Exception as e:
                                scrape_duration = (datetime.now() - scrape_start_time).total_seconds()
                                logger.error(f"Error scraping company {ref}: {e}")
                                results.append({
                                    'reference': ref, 
                                    'data': None, 
                                    'error': str(e),
                                    'duration': scrape_duration,
                                    'from_cache': False
                                })
                    finally:
                        # Always close the bot instance
                        if b:
                            try:
                                await b.close()
                            except Exception as e:
                                logger.error(f"Error closing bot after scraping: {e}")
                    
                    return results
            
            # Run all batches concurrently with max 4 browsers
            all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])
            
            # Flatten results and separate fresh vs newly scraped
            for batch in all_results:
                for result in batch:
                    if result['data'] is not None:
                        if result.get('from_cache', False):
                            fresh_data[result['reference']] = result['data']
                        else:
                            newly_scraped[result['reference']] = {
                                'data': result['data'],
                                'duration': result.get('duration', 0)
                            }
            
            logger.info(f"Scraping complete: {len(fresh_data)} from cache, {len(newly_scraped)} newly scraped")
            
            # Step 4: Combine fresh and newly scraped data
            all_company_data = []
            
            # Add fresh data from database
            for ref, data in fresh_data.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'database',
                    'search_query': search_results.get(ref, None),
                    'scraping_duration': 0  # No scraping time for cached data
                })
            
            # Add newly scraped data
            for ref, scraped_info in newly_scraped.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': scraped_info['data'],
                    'source': 'scraped',
                    'search_query': search_results.get(ref, None),
                    'scraping_duration': scraped_info.get('duration', 0)
                })
            
            return {
                'total_companies': len(company_references),
                'fresh_from_db': len(fresh_data),
                'newly_scraped': len(newly_scraped),
                'companies': all_company_data
            }
            
    except Exception as e:
        logger.error(f"Error in batch scraping task: {e}")
        raise

async def scrape_batch_companies_via_api_background(
    company_names: List[str],
    num_companies_per_search: int,
    freshness_days: int,
    sort_by: str
) -> Dict[str, Any]:
    """Background task for scraping a batch of companies using TracXN API (faster than UI scraping)"""
    try:
        # Ensure database connection is active
        if not db_manager.ensure_connection():
            logger.error("Failed to establish database connection")
            raise Exception("Failed to establish database connection")
        
        async with async_playwright() as playwright:
            # Step 1: Initialize bot and login once
            company_references = []
            search_results = {}  # Track which search term led to which reference
            
            search_max_retries = 3
            search_retry_count = 0
            
            while search_retry_count < search_max_retries:
                search_bot = None
                try:
                    logger.info(f"Initializing bot for API-based batch search (attempt {search_retry_count + 1}/{search_max_retries})")
                    search_bot = TracxnBot(playwright, debug=False)
                    
                    # Login (this handles: open page, email signup, captcha, verification)
                    login_success = await search_bot.login()
                    
                    if not login_success:
                        logger.warning(f"Login failed, attempt {search_retry_count + 1}/{search_max_retries}")
                        search_retry_count += 1
                        if search_retry_count < search_max_retries:
                            await asyncio.sleep(5)
                        continue
                    
                    logger.info("Login successful, starting API searches")
                    
                    # Search for each company using the API method
                    for idx, company_name in enumerate(company_names):
                        logger.info(f"Searching via API for '{company_name}' ({idx + 1}/{len(company_names)})...")
                        try:
                            # Use the new API-based search method
                            # Returns list of dicts with: reference, id, name, domain, tracxnScore, detailedDescription
                            company_data_list = await search_bot.search_companies_via_api(
                                query=company_name,
                                size=num_companies_per_search,
                                sort_by=sort_by
                            )
                            
                            if company_data_list:
                                # Extract references and track which search term found which companies
                                for company_data in company_data_list:
                                    # Handle both dict (new format) and string (old format) for backward compatibility
                                    if isinstance(company_data, dict):
                                        ref = company_data.get('reference')
                                        if not ref:
                                            logger.warning(f"Company data missing 'reference' key: {company_data}")
                                            continue
                                    else:
                                        # Old format - just a string reference
                                        ref = company_data
                                    
                                    company_references.append(ref)
                                    search_results[ref] = company_name
                                    
                                logger.info(f"Found {len(company_data_list)} companies for '{company_name}' via API")
                            else:
                                logger.warning(f"No companies found for '{company_name}' via API")
                            
                            # Small delay between searches to be polite to the API
                            await asyncio.sleep(random.uniform(0.5, 1.0))
                            
                        except Exception as e:
                            logger.error(f"Error searching for '{company_name}' via API: {e}")
                            continue
                    
                    # If we got here, searches were successful
                    break
                    
                except Exception as e:
                    logger.error(f"Error during API search attempt {search_retry_count + 1}: {e}")
                    search_retry_count += 1
                    await asyncio.sleep(2)
                        
                finally:
                    if search_bot:
                        await search_bot.close()
            
            # If search failed after all retries
            if search_retry_count >= search_max_retries:
                raise Exception(f"Failed to search companies via API after {search_max_retries} attempts")
            
            if not company_references:
                logger.warning("No company references found for any of the provided names via API")
                return {
                    'total_companies': 0,
                    'fresh_from_db': 0,
                    'newly_scraped': 0,
                    'companies': []
                }
            
            # Remove duplicates while preserving the first search term for each reference
            original_count = len(company_references)
            unique_references = []
            seen_references = set()
            unique_search_results = {}
            
            for ref in company_references:
                if ref not in seen_references:
                    seen_references.add(ref)
                    unique_references.append(ref)
                    unique_search_results[ref] = search_results[ref]
            
            company_references = unique_references
            search_results = unique_search_results
            
            if original_count > len(company_references):
                logger.info(f"Removed {original_count - len(company_references)} duplicate company references. Unique companies: {len(company_references)}")
            
            # Step 2: Scrape companies with per-company freshness check
            newly_scraped = {}
            fresh_data = {}
            
            # Split into chunks of 4 for concurrent scraping (max 4 browsers)
            chunks = [company_references[i:i+4] for i in range(0, len(company_references), 4)]
            
            # Create semaphore to limit concurrent browsers to 4
            semaphore = asyncio.Semaphore(4)
            
            async def scrape_batch(batch):
                """Scrape one batch of up to 4 companies with per-company freshness check"""
                async with semaphore:
                    results = []
                    scrape_bot = None
                    max_retries = 2
                    retry_count = 0
                    
                    while retry_count < max_retries:
                        try:
                            scrape_bot = TracxnBot(playwright, debug=False)
                            
                            # Login (this handles: open page, email signup, captcha, verification)
                            login_success = await scrape_bot.login()
                            
                            if not login_success:
                                logger.warning(f"Login failed for batch, retry {retry_count + 1}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(5)
                                continue
                            
                            # Check freshness for each company in the batch
                            for ref in batch:
                                try:
                                    # Check if company data is fresh in DB
                                    is_fresh = db_manager.is_company_fresh(ref, freshness_days)
                                    
                                    if is_fresh:
                                        # Get data from database
                                        company_data = db_manager.get_company_data(ref)
                                        if company_data:
                                            results.append({
                                                'reference': ref,
                                                'data': company_data['data'],
                                                'source': 'database',
                                                'search_query': search_results.get(ref)
                                            })
                                            logger.info(f"Using cached data for {ref}")
                                        continue
                                    
                                    # Need to scrape this company
                                    scrape_start = asyncio.get_event_loop().time()
                                    logger.info(f"Scraping company: {ref}")
                                    company_data = await scrape_bot.scrape_company(ref)
                                    scrape_duration = asyncio.get_event_loop().time() - scrape_start
                                    
                                    if scrape_bot.is_data_valid(company_data):
                                        # Save to database
                                        if db_manager.save_company_data(ref, company_data, search_results.get(ref)):
                                            results.append({
                                                'reference': ref,
                                                'data': company_data,
                                                'source': 'scraped',
                                                'search_query': search_results.get(ref),
                                                'scraping_duration': scrape_duration
                                            })
                                            logger.info(f"Successfully scraped and saved: {ref} (took {scrape_duration:.2f}s)")
                                        else:
                                            logger.error(f"Failed to save data for {ref}")
                                    else:
                                        logger.warning(f"Invalid data scraped for {ref}")
                                    
                                    await asyncio.sleep(random.uniform(1, 2))
                                    
                                except Exception as e:
                                    logger.error(f"Error processing company {ref}: {e}")
                                    continue
                            
                            break  # Success, exit retry loop
                            
                        except Exception as e:
                            logger.error(f"Error in scrape batch (retry {retry_count + 1}): {e}")
                            retry_count += 1
                            await asyncio.sleep(2)
                            
                        finally:
                            if scrape_bot:
                                await scrape_bot.close()
                    
                    return results
            
            # Run all batches concurrently with max 4 browsers
            all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])
            
            # Flatten results and separate fresh vs newly scraped
            for batch in all_results:
                for result in batch:
                    if result['source'] == 'database':
                        fresh_data[result['reference']] = result['data']
                    else:
                        newly_scraped[result['reference']] = {
                            'data': result['data'],
                            'search_query': result['search_query'],
                            'scraping_duration': result.get('scraping_duration', 0)
                        }
            
            logger.info(f"API-based scraping complete: {len(fresh_data)} from cache, {len(newly_scraped)} newly scraped")
            
            # Step 3: Combine fresh and newly scraped data
            all_company_data = []
            
            # Add fresh data from database
            for ref, data in fresh_data.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'database',
                    'search_query': search_results.get(ref)
                })
            
            # Add newly scraped data
            for ref, scraped_info in newly_scraped.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': scraped_info['data'],
                    'source': 'scraped',
                    'search_query': scraped_info['search_query'],
                    'scraping_duration_seconds': scraped_info['scraping_duration']
                })
            
            return {
                'total_companies': len(company_references),
                'fresh_from_db': len(fresh_data),
                'newly_scraped': len(newly_scraped),
                'companies': all_company_data
            }
            
    except Exception as e:
        logger.error(f"Error in API-based batch scraping task: {e}")
        raise

async def scrape_batch_companies_with_year_filter_background(
    company_names: List[str],
    from_year: int,
    to_year: int,
    num_companies_per_search: int,
    freshness_days: int,
    sort_by: str
) -> Dict[str, Any]:
    """Background task for scraping companies with year filters"""
    try:
        # Ensure database connection is active
        if not db_manager.ensure_connection():
            logger.error("Failed to establish database connection")
            raise Exception("Failed to establish database connection")
        
        async with async_playwright() as playwright:
            # Step 1: Search for each company across all years and get their links
            company_references = []
            search_results = {}  # Track which search term and year led to which reference
            
            search_max_retries = 3
            search_retry_count = 0
            
            # Validate year range
            if from_year > to_year:
                raise ValueError(f"from_year ({from_year}) cannot be greater than to_year ({to_year})")
            
            years_to_search = list(range(from_year, to_year + 1))
            logger.info(f"Will search {len(company_names)} keywords across {len(years_to_search)} years ({from_year}-{to_year})")
            
            while search_retry_count < search_max_retries:
                search_bot = None
                try:
                    search_bot = TracxnBot(playwright, debug=False)
                    login_success = await search_bot.login()
                    
                    if not login_success:
                        logger.warning(f"Search bot login failed, attempt {search_retry_count + 1}/{search_max_retries}")
                        search_retry_count += 1
                        if search_retry_count < search_max_retries:
                            await asyncio.sleep(5)
                        continue
                    
                    # Login successful, search for each company across all years
                    logger.info(f"Search bot login successful, searching for {len(company_names)} companies across {len(years_to_search)} years")
                    
                    for company_name in company_names:
                        for year in years_to_search:
                            try:
                                logger.info(f"Searching for company: '{company_name}' with year filter: {year}")
                                try:
                                    results = await search_bot.search_companies(
                                        query=company_name,
                                        type="none",
                                        sort_by=sort_by,
                                        filter="year",
                                        filter_value=str(year)
                                    )
                                except Exception as e:
                                    logger.error(f"Error during search for '{company_name}' (year {year}): {e}")
                                    results = []
                                
                                if results and len(results) > 0:
                                    # Take the top N results based on num_companies_per_search
                                    top_results = results[:num_companies_per_search]
                                    for idx, result in enumerate(top_results):
                                        if result:  # Check if not None
                                            company_references.append(result)
                                            search_results[result] = {"keyword": company_name, "year": year}
                                            logger.info(f"Found company reference #{idx+1} for '{company_name}' (year {year}): {result}")
                                        else:
                                            logger.warning(f"Invalid reference at position {idx} for '{company_name}' (year {year})")
                                    
                                    if top_results:
                                        logger.info(f"Found {len(top_results)} company references for '{company_name}' (year {year})")
                                    else:
                                        logger.warning(f"No valid references found for '{company_name}' (year {year})")
                                else:
                                    logger.warning(f"No search results found for '{company_name}' (year {year})")
                                
                                # Small delay between searches to be respectful
                                await asyncio.sleep(2)
                                
                            except Exception as e:
                                logger.error(f"Error searching for company '{company_name}' (year {year}): {e}")
                                continue
                    
                    logger.info(f"Search successful, found {len(company_references)} company references across all years")
                    logger.info(f"Company references: {company_references}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error during search attempt {search_retry_count + 1}: {e}")
                    search_retry_count += 1
                    if search_retry_count < search_max_retries:
                        await asyncio.sleep(5)
                        
                finally:
                    # Always close search bot
                    if search_bot:
                        try:
                            await search_bot.close()
                        except Exception as e:
                            logger.error(f"Error closing search bot: {e}")
            
            # If search failed after all retries
            if search_retry_count >= search_max_retries:
                raise Exception(f"Failed to search companies after {search_max_retries} attempts")
            
            if not company_references:
                logger.warning("No company references found for any of the provided names and years")
                return {
                    'total_companies': 0,
                    'fresh_from_db': 0,
                    'newly_scraped': 0,
                    'companies': []
                }
            
            # Remove duplicates while preserving the first search term for each reference
            original_count = len(company_references)
            unique_references = []
            seen_references = set()
            unique_search_results = {}
            
            for ref in company_references:
                if ref not in seen_references:
                    seen_references.add(ref)
                    unique_references.append(ref)
                    # Keep the first search query that found this reference
                    if ref in search_results and ref not in unique_search_results:
                        unique_search_results[ref] = search_results[ref]
            
            company_references = unique_references
            search_results = unique_search_results
            
            if original_count > len(company_references):
                logger.info(f"Removed {original_count - len(company_references)} duplicate company references. Unique companies: {len(company_references)}")
            
            # Step 2: Scrape companies with per-company freshness check
            newly_scraped = {}
            fresh_data = {}
            
            # Split into chunks of 4 for concurrent scraping (max 4 browsers)
            chunks = [company_references[i:i+4] for i in range(0, len(company_references), 4)]
            
            # Create semaphore to limit concurrent browsers to 4
            semaphore = asyncio.Semaphore(4)
            
            async def scrape_batch(batch):
                """Scrape one batch of up to 4 companies with per-company freshness check"""
                async with semaphore:  # Limit concurrent browsers
                    max_retries = 3
                    retry_count = 0
                    b = None
                    
                    while retry_count < max_retries:
                        login_success = False
                        try:
                            # Create new bot instance for each retry
                            if b:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing bot during retry: {e}")
                                b = None
                            
                            b = TracxnBot(playwright, debug=False)
                            
                            # Attempt login
                            login_success = await b.login()
                            if not login_success:
                                logger.warning(f"Login failed for batch, attempt {retry_count + 1}/{max_retries}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(5)
                                continue
                            
                            # Login successful, proceed with scraping
                            logger.info(f"Login successful for batch on attempt {retry_count + 1}")
                            break
                            
                        except Exception as e:
                            logger.error(f"Error during login attempt {retry_count + 1}: {e}")
                            retry_count += 1
                            if retry_count < max_retries:
                                await asyncio.sleep(5)
                        finally:
                            # Always close bot if login failed and we're retrying
                            if retry_count < max_retries and b and not login_success:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing failed login bot: {e}")
                                b = None
                    
                    # If all login attempts failed, close bot and return empty results
                    if retry_count >= max_retries or not b:
                        logger.error(f"Failed to login after {max_retries} attempts, skipping batch")
                        if b:
                            try:
                                await b.close()
                            except Exception as e:
                                logger.error(f"Error closing bot after failed login: {e}")
                        return []
                    
                    # Scrape companies in this batch
                    results = []
                    try:
                        for ref in batch:
                            # Check freshness before scraping each company
                            fresh_check = db_manager.get_fresh_companies([ref], freshness_days)
                            
                            if ref in fresh_check['fresh_data']:
                                # Company is fresh in database, use cached data
                                logger.info(f"Using fresh data from database for {ref}")
                                results.append({
                                    'reference': ref,
                                    'data': fresh_check['fresh_data'][ref],
                                    'duration': 0,
                                    'from_cache': True
                                })
                                continue
                            
                            # Company needs scraping
                            scrape_start_time = datetime.now()
                            try:
                                data = await b.scrape_company(ref)
                                scrape_duration = (datetime.now() - scrape_start_time).total_seconds()
                                
                                # Validate data before saving
                                if data and b.is_data_valid(data):
                                    # Get original search query for this reference
                                    search_info = search_results.get(ref, {})
                                    search_query = f"{search_info.get('keyword', 'unknown')}_{search_info.get('year', 'unknown')}"
                                    # Save to database
                                    db_manager.save_company_data(ref, data, search_query)
                                    results.append({
                                        'reference': ref, 
                                        'data': data,
                                        'duration': scrape_duration,
                                        'from_cache': False
                                    })
                                    logger.info(f"Successfully scraped and saved data for {ref} in {scrape_duration:.2f}s")
                                else:
                                    logger.warning(f"Scraped data for {ref} is empty or invalid, not saving to database")
                                    results.append({
                                        'reference': ref, 
                                        'data': None, 
                                        'error': 'Empty or invalid data',
                                        'duration': scrape_duration,
                                        'from_cache': False
                                    })
                                    
                            except Exception as e:
                                scrape_duration = (datetime.now() - scrape_start_time).total_seconds()
                                logger.error(f"Error scraping company {ref}: {e}")
                                results.append({
                                    'reference': ref, 
                                    'data': None, 
                                    'error': str(e),
                                    'duration': scrape_duration,
                                    'from_cache': False
                                })
                    finally:
                        # Always close the bot instance
                        if b:
                            try:
                                await b.close()
                            except Exception as e:
                                logger.error(f"Error closing bot after scraping: {e}")
                    
                    return results
            
            # Run all batches concurrently with max 4 browsers
            all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])
            
            # Flatten results and separate fresh vs newly scraped
            for batch in all_results:
                for result in batch:
                    if result['data'] is not None:
                        if result.get('from_cache', False):
                            fresh_data[result['reference']] = result['data']
                        else:
                            newly_scraped[result['reference']] = {
                                'data': result['data'],
                                'duration': result.get('duration', 0)
                            }
            
            logger.info(f"Scraping complete: {len(fresh_data)} from cache, {len(newly_scraped)} newly scraped")
            
            # Step 3: Combine fresh and newly scraped data
            all_company_data = []
            
            # Add fresh data from database
            for ref, data in fresh_data.items():
                search_info = search_results.get(ref, {})
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'database',
                    'search_query': f"{search_info.get('keyword', 'unknown')}_{search_info.get('year', 'unknown')}",
                    'scraping_duration': 0  # No scraping time for cached data
                })
            
            # Add newly scraped data
            for ref, scraped_info in newly_scraped.items():
                search_info = search_results.get(ref, {})
                all_company_data.append({
                    'company_reference': ref,
                    'data': scraped_info['data'],
                    'source': 'scraped',
                    'search_query': f"{search_info.get('keyword', 'unknown')}_{search_info.get('year', 'unknown')}",
                    'scraping_duration': scraped_info.get('duration', 0)
                })
            
            return {
                'total_companies': len(company_references),
                'fresh_from_db': len(fresh_data),
                'newly_scraped': len(newly_scraped),
                'companies': all_company_data
            }
            
    except Exception as e:
        logger.error(f"Error in batch scraping with year filter task: {e}")
        raise

async def scrape_references_background(
    company_references: List[str],
    freshness_days: int
) -> Dict[str, Any]:
    """Background task for scraping companies by direct reference links"""
    try:
        # Ensure database connection is active
        if not db_manager.ensure_connection():
            logger.error("Failed to establish database connection")
            raise Exception("Failed to establish database connection")
        
        async with async_playwright() as playwright:
            logger.info(f"Starting scrape for {len(company_references)} company references")
            
            # Step 1: Check which companies are fresh in database
            fresh_result = db_manager.get_fresh_companies(company_references, freshness_days)
            fresh_data = fresh_result['fresh_data']
            need_scraping = fresh_result['need_scraping']
            
            logger.info(f"Found {len(fresh_data)} fresh companies in DB, need to scrape {len(need_scraping)}")
            
            # Step 2: Scrape companies that need updating
            newly_scraped = {}
            if need_scraping:
                # Split into chunks of 4 for concurrent scraping (max 4 browsers)
                chunks = [need_scraping[i:i+4] for i in range(0, len(need_scraping), 4)]
                
                # Create semaphore to limit concurrent browsers to 4
                semaphore = asyncio.Semaphore(4)
                
                async def scrape_batch(batch):
                    """Scrape one batch of up to 4 companies with login retry logic"""
                    async with semaphore:  # Limit concurrent browsers
                        max_retries = 3
                        retry_count = 0
                        b = None
                        
                        while retry_count < max_retries:
                            login_success = False
                            try:
                                # Create new bot instance for each retry
                                if b:
                                    try:
                                        await b.close()
                                    except Exception as e:
                                        logger.error(f"Error closing bot during retry: {e}")
                                    b = None
                                
                                b = TracxnBot(playwright, debug=False)
                                
                                # Attempt login
                                login_success = await b.login()
                                if not login_success:
                                    logger.warning(f"Login failed for batch, attempt {retry_count + 1}/{max_retries}")
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        await asyncio.sleep(5)
                                    continue
                                
                                # Login successful, proceed with scraping
                                logger.info(f"Login successful for batch on attempt {retry_count + 1}")
                                break
                                
                            except Exception as e:
                                logger.error(f"Error during login attempt {retry_count + 1}: {e}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(5)
                            finally:
                                # Always close bot if login failed and we're retrying
                                if retry_count < max_retries and b and not login_success:
                                    try:
                                        await b.close()
                                    except Exception as e:
                                        logger.error(f"Error closing failed login bot: {e}")
                                    b = None
                        
                        # If all login attempts failed, close bot and return empty results
                        if retry_count >= max_retries or not b:
                            logger.error(f"Failed to login after {max_retries} attempts, skipping batch")
                            if b:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing bot after failed login: {e}")
                            return []
                        
                        # Scrape companies in this batch
                        results = []
                        try:
                            for ref in batch:
                                try:
                                    data = await b.scrape_company(ref)
                                    
                                    # Validate data before saving
                                    if data and b.is_data_valid(data):
                                        # Save to database (no search query for direct references)
                                        db_manager.save_company_data(ref, data, None)
                                        results.append({'reference': ref, 'data': data})
                                        logger.info(f"Successfully scraped and saved data for {ref}")
                                    else:
                                        logger.warning(f"Scraped data for {ref} is empty or invalid, not saving to database")
                                        results.append({'reference': ref, 'data': None, 'error': 'Empty or invalid data'})
                                        
                                except Exception as e:
                                    logger.error(f"Error scraping company {ref}: {e}")
                                    results.append({'reference': ref, 'data': None, 'error': str(e)})
                        finally:
                            # Always close the bot instance
                            if b:
                                try:
                                    await b.close()
                                except Exception as e:
                                    logger.error(f"Error closing bot after scraping: {e}")
                        
                        return results
                
                # Run all batches concurrently with max 4 browsers
                all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])
                
                # Flatten results and only include valid data
                for batch in all_results:
                    for result in batch:
                        if result['data'] is not None:
                            newly_scraped[result['reference']] = result['data']
            
            # Step 3: Combine fresh and newly scraped data
            all_company_data = []
            
            # Add fresh data from database
            for ref, data in fresh_data.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'database'
                })
            
            # Add newly scraped data
            for ref, data in newly_scraped.items():
                all_company_data.append({
                    'company_reference': ref,
                    'data': data,
                    'source': 'scraped'
                })
            
            return {
                'total_companies': len(company_references),
                'fresh_from_db': len(fresh_data),
                'newly_scraped': len(newly_scraped),
                'companies': all_company_data
            }
            
    except Exception as e:
        logger.error(f"Error in reference scraping task: {e}")
        raise

@app.post("/scrape", response_model=ScrapingResponse)
async def scrape_companies(request: SearchRequest):
    """
    Scrape companies based on search criteria
    
    This endpoint will:
    1. Search for companies using the provided term
    2. Check database for fresh data (within freshness_days)
    3. Scrape only companies that need updating
    4. Return combined results from database and fresh scraping
    """
    try:
        result = await scrape_companies_background(
            request.search_term,
            request.num_companies,
            request.freshness_days,
            request.sort_by
        )
        
        # Format response
        companies = []
        for company in result['companies']:
            companies.append(CompanyData(
                company_reference=company['company_reference'],
                data=company['data'],
                last_updated=datetime.now(),
                search_query=request.search_term
            ))
        
        return ScrapingResponse(
            message="Scraping completed successfully",
            total_companies=result['total_companies'],
            fresh_from_db=result['fresh_from_db'],
            newly_scraped=result['newly_scraped'],
            companies=companies
        )
        
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping failed: {str(e)}"
        )

@app.post("/scrape-batch", response_model=ScrapingResponse)
async def scrape_batch_companies(request: BatchCompaniesRequest):
    """
    Scrape multiple companies by name in batch
    
    This endpoint will:
    1. Search for each company name provided
    2. Take the top N results from each search (based on num_companies_per_search)
    3. Check database for fresh data (within freshness_days)
    4. Scrape only companies that need updating
    5. Return combined results from database and fresh scraping with detailed metadata
    """
    try:
        # Validate input
        if not request.company_names or len(request.company_names) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="company_names list cannot be empty"
            )
        
        # Validate per-company limit (100 companies max per search)
        if request.num_companies_per_search > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"num_companies_per_search cannot exceed 100 (requested: {request.num_companies_per_search})"
            )
        
        total_companies_requested = len(request.company_names) * request.num_companies_per_search
        logger.info(f"Starting batch scrape for {len(request.company_names)} company names, {request.num_companies_per_search} companies per search (total: {total_companies_requested} companies)")
        
        result = await scrape_batch_companies_background(
            request.company_names,
            request.num_companies_per_search,
            request.freshness_days
        )
        
        # Format response
        companies = []
        for company in result['companies']:
            companies.append(CompanyData(
                company_reference=company['company_reference'],
                data=company['data'],
                last_updated=datetime.now(),
                search_query=company.get('search_query', None),
                source=company.get('source', 'unknown'),
                scraping_duration_seconds=company.get('scraping_duration', 0)
            ))
        
        return ScrapingResponse(
            message=f"Batch scraping completed successfully for {len(request.company_names)} company names ({request.num_companies_per_search} companies per search)",
            total_companies=result['total_companies'],
            fresh_from_db=result['fresh_from_db'],
            newly_scraped=result['newly_scraped'],
            companies=companies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scrape-batch endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch scraping failed: {str(e)}"
        )

@app.post("/scrape-batch-api", response_model=ScrapingResponse)
async def scrape_batch_companies_api(request: BatchCompaniesAPIRequest):
    """
    Scrape multiple companies by name in batch using TracXN API (faster than UI scraping)
    
    This endpoint uses TracXN's internal API with dynamically extracted browser cookies
    and headers, making it significantly faster than the UI-based scraping approach.
    
    This endpoint will:
    1. Login once and extract browser cookies/headers
    2. Search for each company name using TracXN API directly
    3. Take the top N results from each search (based on num_companies_per_search)
    4. Check database for fresh data (within freshness_days)
    5. Scrape only companies that need updating
    6. Return combined results from database and fresh scraping with detailed metadata
    
    Benefits over /scrape-batch:
    - Much faster search (direct API vs UI automation)
    - More reliable (less prone to UI changes)
    - Better for large batches
    """
    try:
        # Validate input
        if not request.company_names or len(request.company_names) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="company_names list cannot be empty"
            )
        
        # Validate per-company limit (100 companies max per search)
        if request.num_companies_per_search > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"num_companies_per_search cannot exceed 100 (requested: {request.num_companies_per_search})"
            )
        
        total_companies_requested = len(request.company_names) * request.num_companies_per_search
        logger.info(f"Starting API-based batch scrape for {len(request.company_names)} company names, {request.num_companies_per_search} companies per search (total: {total_companies_requested} companies)")
        
        result = await scrape_batch_companies_via_api_background(
            request.company_names,
            request.num_companies_per_search,
            request.freshness_days,
            request.sort_by
        )
        
        # Format response
        companies = []
        for company in result['companies']:
            companies.append(CompanyData(
                company_reference=company['company_reference'],
                data=company['data'],
                last_updated=datetime.now(),
                search_query=company.get('search_query', None),
                source=company.get('source', 'unknown'),
                scraping_duration_seconds=company.get('scraping_duration_seconds', 0)
            ))
        
        return ScrapingResponse(
            message=f"API-based batch scraping completed successfully for {len(request.company_names)} company names ({request.num_companies_per_search} companies per search)",
            total_companies=result['total_companies'],
            fresh_from_db=result['fresh_from_db'],
            newly_scraped=result['newly_scraped'],
            companies=companies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scrape-batch-api endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API-based batch scraping failed: {str(e)}"
        )

@app.post("/scrape-batch-with-year-filter", response_model=ScrapingResponse)
async def scrape_batch_companies_with_year_filter(request: BatchCompaniesWithYearFilterRequest):
    """
    Scrape multiple companies by name with year filters in batch
    
    This endpoint will:
    1. Search for each company name across a range of years (from_year to to_year)
    2. For each keyword and year combination, search with year filter
    3. Take the top N results from each search (based on num_companies_per_search)
    4. Remove duplicates across all searches
    5. Check database for fresh data (within freshness_days)
    6. Scrape only companies that need updating
    7. Return combined results from database and fresh scraping with detailed metadata
    
    Example:
    - company_names: ["artificial intelligence", "machine learning"]
    - from_year: 2020
    - to_year: 2022
    - This will search each keyword for years 2020, 2021, and 2022 (6 searches total)
    """
    try:
        # Validate input
        if not request.company_names or len(request.company_names) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="company_names list cannot be empty"
            )
        
        # Validate year range
        if request.from_year > request.to_year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"from_year ({request.from_year}) cannot be greater than to_year ({request.to_year})"
            )
        
        # Validate per-company limit (100 companies max per search)
        if request.num_companies_per_search > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"num_companies_per_search cannot exceed 100 (requested: {request.num_companies_per_search})"
            )
        
        years_count = request.to_year - request.from_year + 1
        total_searches = len(request.company_names) * years_count
        max_possible_companies = total_searches * request.num_companies_per_search
        
        logger.info(f"Starting batch scrape with year filter for {len(request.company_names)} keywords, "
                   f"{years_count} years ({request.from_year}-{request.to_year}), "
                   f"{request.num_companies_per_search} companies per search "
                   f"(total searches: {total_searches}, max companies: {max_possible_companies})")
        
        result = await scrape_batch_companies_with_year_filter_background(
            request.company_names,
            request.from_year,
            request.to_year,
            request.num_companies_per_search,
            request.freshness_days,
            request.sort_by
        )
        
        # Format response
        companies = []
        for company in result['companies']:
            companies.append(CompanyData(
                company_reference=company['company_reference'],
                data=company['data'],
                last_updated=datetime.now(),
                search_query=company.get('search_query', None),
                source=company.get('source', 'unknown'),
                scraping_duration_seconds=company.get('scraping_duration', 0)
            ))
        
        return ScrapingResponse(
            message=f"Batch scraping with year filter completed successfully for {len(request.company_names)} keywords "
                   f"across {years_count} years ({request.from_year}-{request.to_year})",
            total_companies=result['total_companies'],
            fresh_from_db=result['fresh_from_db'],
            newly_scraped=result['newly_scraped'],
            companies=companies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scrape-batch-with-year-filter endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch scraping with year filter failed: {str(e)}"
        )

@app.post("/scrape-references", response_model=ScrapingResponse)
async def scrape_by_references(request: BatchReferencesRequest):
    """
    Scrape companies by direct reference links in batch
    
    This endpoint will:
    1. Accept a list of company reference links (e.g., /a/d/investor/...)
    2. Check database for fresh data (within freshness_days)
    3. Scrape only companies that need updating
    4. Return combined results from database and fresh scraping
    
    Example reference format: "/a/d/investor/srAiTt8Aevx0dkPbmrFdUVl21azd7Gx7AOT8J4fO1Zs/ycombinator"
    """
    try:
        # Validate input
        if not request.company_references or len(request.company_references) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="company_references list cannot be empty"
            )
        
        if len(request.company_references) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 100 company references can be scraped in a single batch request"
            )
        
        logger.info(f"Starting reference-based scrape for {len(request.company_references)} companies")
        
        result = await scrape_references_background(
            request.company_references,
            request.freshness_days
        )
        
        # Format response
        companies = []
        for company in result['companies']:
            companies.append(CompanyData(
                company_reference=company['company_reference'],
                data=company['data'],
                last_updated=datetime.now(),
                search_query=None  # No search query for direct references
            ))
        
        return ScrapingResponse(
            message=f"Reference scraping completed successfully for {len(request.company_references)} references",
            total_companies=result['total_companies'],
            fresh_from_db=result['fresh_from_db'],
            newly_scraped=result['newly_scraped'],
            companies=companies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scrape-references endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reference scraping failed: {str(e)}"
        )

@app.post("/manual-bulk-scrape", response_model=ScrapingResponse)
async def manual_bulk_scrape(request: ManualBulkScrapeRequest):
    """
    Manual bulk scraping endpoint for premium accounts.
    
    This endpoint will:
    1. Prompt for email and verification code in terminal (if not provided)
    2. Login with the provided credentials
    3. Navigate to the specified page URL
    4. Scroll to load all companies (up to max_scrolls times)
    5. Extract all company references from the table
    6. Scrape each company one by one
    7. Optionally save to database
    
    This is designed for scraping large lists (~4000 companies) that require
    extensive scrolling to load all entries in the table.
    
    Example page_url: "https://platform.tracxn.com/search/..."
    """
    try:
        logger.info(f"Starting manual bulk scrape for page: {request.page_url}")
        
        async with async_playwright() as playwright:
            bot = None
            try:
                # Create bot instance
                bot = TracxnBot(playwright, debug=False)
                
                # Perform manual login with terminal input
                logger.info("Initiating manual login...")
                login_success = await bot.manual_login(
                    email=request.email,
                    verification_code=request.verification_code
                )
                
                if not login_success:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Manual login failed. Please check your credentials."
                    )
                
                logger.info("Manual login successful")
                
                # Navigate to the page and load all companies
                logger.info(f"Navigating to page and loading companies (max {request.max_scrolls} scrolls)...")
                load_success = await bot.navigate_to_page_and_load_all(
                    page_url=request.page_url,
                    max_scrolls=request.max_scrolls
                )
                
                if not load_success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to navigate to page and load companies"
                    )
                
                logger.info("Successfully loaded all companies")
                
                # Extract and scrape all companies
                logger.info("Starting to extract and scrape all companies...")
                
                # Pass database saving callback if save_to_db is requested
                save_callback = None
                if request.save_to_db:
                    def save_callback(reference, data):
                        try:
                            db_manager.save_company_data(
                                reference,
                                data,
                                f"manual_bulk_scrape:{request.page_url}"
                            )
                            logger.info(f"Saved {reference} to database")
                            return True
                        except Exception as e:
                            logger.error(f"Error saving company {reference} to database: {e}")
                            return False
                
                scraped_results = await bot.extract_and_scrape_all_companies(
                    save_callback=save_callback
                )
                
                if not scraped_results:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to extract or scrape companies"
                    )
                
                # Process results
                successful_companies = []
                newly_scraped = 0
                
                for result in scraped_results:
                    if result['status'] == 'success' and result['data']:
                        # Count saved companies
                        if request.save_to_db and result.get('saved', False):
                            newly_scraped += 1
                        
                        successful_companies.append(CompanyData(
                            company_reference=result['reference'],
                            data=result['data'],
                            last_updated=datetime.now(),
                            search_query=f"manual_bulk_scrape:{request.page_url}",
                            source='scraped'
                        ))
                
                logger.info(f"Manual bulk scrape completed. Total: {len(scraped_results)}, Success: {len(successful_companies)}")
                
                return ScrapingResponse(
                    message=f"Manual bulk scraping completed successfully. Scraped {len(successful_companies)} out of {len(scraped_results)} companies.",
                    total_companies=len(scraped_results),
                    fresh_from_db=0,  # All freshly scraped
                    newly_scraped=newly_scraped,
                    companies=successful_companies
                )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error during manual bulk scraping: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Manual bulk scraping failed: {str(e)}"
                )
            finally:
                # Always close the bot
                if bot:
                    try:
                        await bot.close()
                    except Exception as e:
                        logger.error(f"Error closing bot: {e}")
                        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual-bulk-scrape endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual bulk scraping failed: {str(e)}"
        )

@app.get("/companies", response_model=List[CompanyData])
async def get_all_companies():
    """Get all companies from database"""
    try:
        companies = db_manager.get_all_companies()
        
        result = []
        for company in companies:
            result.append(CompanyData(
                company_reference=company['company_reference'],
                data=company['company_data'],
                last_updated=company['last_updated'],
                search_query=company['search_query']
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving companies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve companies: {str(e)}"
        )

@app.get("/companies/{company_reference}", response_model=CompanyData)
async def get_company(company_reference: str):
    """Get specific company data by reference"""
    try:
        company_data = db_manager.get_company_data(company_reference)
        
        if not company_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company with reference '{company_reference}' not found"
            )
        
        return CompanyData(
            company_reference=company_reference,
            data=company_data['data'],
            last_updated=company_data['last_updated'],
            search_query=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving company {company_reference}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve company: {str(e)}"
        )

@app.post("/export", response_model=ExportResponse)
async def export_companies(
    output_dir: str = Query(default="exported_companies", description="Output directory for exported files")
):
    """Export all company data to JSON files"""
    try:
        exported_count = db_manager.export_all_to_json(output_dir)
        
        return ExportResponse(
            message="Export completed successfully",
            exported_count=exported_count,
            output_directory=output_dir
        )
        
    except Exception as e:
        logger.error(f"Error exporting companies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )

@app.post("/scrape-batch-api-with-rank")
async def scrape_batch_companies_api_with_rank(request: BatchCompaniesAPIWithRankRequest):
    """
    Scrape multiple companies via API with similarity and TracXN score ranking
    
    This endpoint combines AI-powered similarity scoring with TracXN scores.
    
    It will:
    1. Search for each company name via TracXN API (fast)
    2. Collect descriptions and TracXN scores from API responses
    3. Calculate AI similarity scores against target description
    4. Normalize TracXN scores to 0-1 range
    5. Combine scores using weighted formula: combined_score = (similarity * similarity_weight) + (tracxn_score * score_weight)
    6. Return ALL companies sorted by combined score (with descriptions and scores)
    7. Additionally scrape and return full data for the top N most relevant companies
    
    Scoring details:
    - Similarity score: 0-1 (higher = more similar to target description)
    - TracXN score: 0-1 (normalized from original TracXN overall score)
    - Combined score: weighted sum of similarity and TracXN scores
    
    Default weights: 75% similarity, 25% TracXN score (configurable via parameters)
    
    Response structure:
    - all_companies: List of ALL companies sorted by combined score
    - top_companies_full_data: Full scraped data for the top N companies
    - metadata: Statistics including score ranges, weights used, and timing information
    """
    # Extract request_id and report_id for cancellation tracking and status updates
    request_id = getattr(request, 'request_id', None)
    report_id = getattr(request, 'report_id', None)
    if request_id:
        active_requests[request_id] = {"cancelled": False, "created_at": datetime.now()}
        logger.info(f"📝 Tracking request {request_id} (report_id: {report_id})")
    
    # Helper function to send status updates to ReportProgressTracker
    # Matches Crunchbase API architecture: POST /api/reports/status-update/
    async def send_status_update(step_key: str, detail_type: str, message: str, data: dict = None):
        """
        Send status update to backend ReportProgressTracker for WebSocket broadcasting.
        
        Args:
            step_key: The step being updated (e.g., 'api_search', 'sorting')
            detail_type: Type of detail (e.g., 'search_result', 'company_found')
            message: Human-readable status message
            data: Optional additional data dict
        """
        if not report_id:
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "report_id": report_id,
                    "step_key": step_key,
                    "detail_type": detail_type,
                    "message": message,
                    "data": data or {}
                }
                # Use configured callback URL (default to backend for docker, but allow override for local script)
                callback_url = os.getenv("STATUS_CALLBACK_URL", "http://backend:8000/api/reports/status-update/")
                await client.post(
                    callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                logger.debug(f"📡 Status update sent: {step_key}/{detail_type}: {message[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ Failed to send status update: {e}")
    
    try:
        if not SIMILARITY_SEARCH_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail={"error": "Similarity search functionality is not available. Please ensure the similarity_search module is installed."}
            )
        
        # Validate weights
        if not (0 <= request.similarity_weight <= 1) or not (0 <= request.score_weight <= 1):
            raise HTTPException(
                status_code=400,
                detail={"error": "Weights must be between 0 and 1"}
            )
        
        if abs((request.similarity_weight + request.score_weight) - 1.0) > 0.001:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Weights must sum to 1.0. Current sum: {request.similarity_weight + request.score_weight}"}
            )
        
        logger.info(f"Starting API-based similarity search for {len(request.company_names)} keywords")
        
        # Send initial status: Keywords selected
        await send_status_update(
            "api_search",
            "search_started",
            f"Starting Tracxn search with {len(request.company_names)} keywords: {', '.join(request.company_names[:3])}{'...' if len(request.company_names) > 3 else ''}",
            {"keywords": request.company_names[:10], "total_keywords": len(request.company_names)}
        )
        
        # Step 1: Search companies via API and collect metadata
        async with async_playwright() as playwright:
            company_tracker = {}  # {reference: {name, description, tracxn_score, keywords}}
            search_retry_count = 0
            search_max_retries = 3
            
            while search_retry_count < search_max_retries:
                try:
                    browser = await playwright.chromium.launch(headless=True)
                    ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                    context = await browser.new_context(user_agent=ua)
                    page = await context.new_page()
                    bot = TracxnBot(playwright, debug=False)
                    
                    # Login once
                    if not await bot.login():
                        logger.error("Login failed")
                        await browser.close()
                        search_retry_count += 1
                        continue
                    
                    logger.info("✅ Login successful, starting API searches")
                    
                    # Search each keyword
                    for idx, keyword in enumerate(request.company_names, 1):
                        # Check for cancellation
                        if request_id and request_id in active_requests and active_requests[request_id]["cancelled"]:
                            logger.info(f"🛑 Request {request_id} cancelled during keyword search")
                            await browser.close()
                            return {"error": "Request was cancelled", "cancelled": True}
                        
                        # Send status for current keyword search
                        await send_status_update(
                            "api_search",
                            "search_result",
                            f"Searched '{keyword}' ({idx}/{len(request.company_names)})",
                            {
                                "keyword": keyword,
                                "keyword_index": idx,
                                "total_keywords": len(request.company_names)
                            }
                        )
                        
                        logger.info(f"Searching via API: '{keyword}'")
                        
                        # Use API search to get company data with descriptions
                        company_data_list = await bot.search_companies_via_api(
                            query=keyword,
                            size=request.num_companies_per_search,
                            sort_by=request.sort_by
                        )
                        
                        logger.info(f"API returned {len(company_data_list)} companies for '{keyword}'")
                        
                        # Generate preview of found companies for status update
                        found_names = []
                        if company_data_list:
                            for c in company_data_list[:5]:
                                if isinstance(c, dict):
                                    found_names.append(c.get('name', 'Unknown'))
                        
                        preview_msg = ", ".join(found_names)
                        if len(company_data_list) > 5:
                            preview_msg += f" +{len(company_data_list)-5} more"
                            
                        # Send updated status with results
                        await send_status_update(
                            "api_search",
                            "search_result",
                            f"Searched '{keyword}': Found {len(company_data_list)} companies ({preview_msg})",
                            {
                                "keyword": keyword,
                                "companies_found": len(company_data_list),
                                "top_companies": found_names,
                                "total_keywords": len(request.company_names),
                                "keyword_index": idx
                            }
                        )

                        # Track companies with their metadata
                        for company_data in company_data_list:
                            if isinstance(company_data, dict):
                                ref = company_data.get('reference', '')
                                name = company_data.get('name', '')
                                description = company_data.get('detailedDescription', '')
                                tracxn_score = company_data.get('tracxnScore', 0)
                                
                                if ref:
                                    if ref not in company_tracker:
                                        company_tracker[ref] = {
                                            'reference': ref,
                                            'name': name,
                                            'description': description,
                                            'tracxn_score': tracxn_score,
                                            'keywords': [keyword],
                                            'appearance_count': 1
                                        }
                                    else:
                                        company_tracker[ref]['keywords'].append(keyword)
                                        company_tracker[ref]['appearance_count'] += 1
                        
                        # Rate limiting
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                    
                    await browser.close()
                    logger.info(f"✅ API search complete: found {len(company_tracker)} unique companies")
                    break
                    
                except Exception as e:
                    logger.error(f"Error during API search (attempt {search_retry_count + 1}/{search_max_retries}): {e}")
                    try:
                        await browser.close()
                    except:
                        pass
                    search_retry_count += 1
                    if search_retry_count < search_max_retries:
                        await asyncio.sleep(5)
            
            if not company_tracker:
                return {
                    "all_companies": [],
                    "top_companies_full_data": [],
                    "metadata": {
                        "total_keywords_searched": len(request.company_names),
                        "total_unique_companies": 0,
                        "top_count_requested": request.top_count,
                        "top_count_returned": 0,
                        "similarity_weight": request.similarity_weight,
                        "score_weight": request.score_weight
                    }
                }
            
            # Send status: Sorting companies
            await send_status_update(
                "sorting",
                "sorting_started",
                f"Ranking {len(company_tracker)} startups by similarity and Tracxn score",
                {"total_companies": len(company_tracker)}
            )
            
            # Step 2: Calculate similarity scores
            logger.info(f"\\n=== Step 2: Calculating similarity scores for {len(company_tracker)} companies ===")
            
            # Prepare companies for similarity search
            companies_for_similarity = []
            for ref, tracker_data in company_tracker.items():
                companies_for_similarity.append({
                    "reference": ref,
                    "name": tracker_data['name'],
                    "description": tracker_data['description'] or tracker_data['name']
                })
            
            companies_json = json.dumps(companies_for_similarity)
            
            try:
                similar_companies = find_similar_companies(
                    companies_json=companies_json,
                    target_description=request.target_description,
                    top_k=None  # Get all companies ranked
                )
                
                logger.info(f"✅ Similarity scores calculated")
                
                # Send status: Companies ranked
                await send_status_update(
                    "sorting",
                    "company_ranked",
                    f"Ranked {len(similar_companies)} startups by combined score",
                    {"total_companies": len(similar_companies), "top_company": similar_companies[0]['name'] if similar_companies else None}
                )
                
                # Step 3: Convert TracXN scores (0-100) to 0-1 range and combine with similarity
                logger.info(f"\\n=== Step 3: Converting TracXN scores and calculating combined scores ===")
                
                # Get TracXN score range for logging
                all_tracxn_scores = [company_tracker[comp['reference']]['tracxn_score'] for comp in similar_companies]
                min_score = min(all_tracxn_scores) if all_tracxn_scores else 0
                max_score = max(all_tracxn_scores) if all_tracxn_scores else 100
                
                logger.info(f"TracXN Score range: {min_score:.2f} (lowest) to {max_score:.2f} (highest)")
                
                # Calculate combined scores
                all_companies_with_scores = []
                for sim_comp in similar_companies:
                    ref = sim_comp['reference']
                    tracker_data = company_tracker[ref]
                    
                    # Convert TracXN score from 0-100 to 0-1 range
                    normalized_tracxn_score = tracker_data['tracxn_score'] / 100.0
                    
                    # Calculate combined score
                    combined_score = (
                        sim_comp['similarity_score'] * request.similarity_weight +
                        normalized_tracxn_score * request.score_weight
                    )
                    
                    all_companies_with_scores.append({
                        'reference': ref,
                        'name': tracker_data['name'],
                        'description': tracker_data['description'],
                        'similarity_score': sim_comp['similarity_score'],
                        'tracxn_score': tracker_data['tracxn_score'],
                        'normalized_tracxn_score': normalized_tracxn_score,
                        'combined_score': combined_score,
                        'appearance_count': tracker_data['appearance_count'],
                        'keywords': tracker_data['keywords']
                    })
                
                # Sort by combined score (descending)
                all_companies_with_scores.sort(key=lambda x: x['combined_score'], reverse=True)
                
                # Add rank
                for i, company in enumerate(all_companies_with_scores):
                    company['rank'] = i + 1
                
                logger.info(f"✅ Combined scores calculated, top company: {all_companies_with_scores[0]['name']} (score: {all_companies_with_scores[0]['combined_score']:.4f})")
                
                # Extract company names for status update
                top_company_names = [comp['name'] for comp in all_companies_with_scores[:request.top_count]]
                
                # Send status: Top companies selected
                await send_status_update(
                    "sorting",
                    "top_selected",
                    f"Selected top {request.top_count} startups for detailed scraping",
                    {"top_count": request.top_count, "top_companies": top_company_names[:5]}
                )
                
                # Step 4: Scrape top N companies for full data
                logger.info(f"\\n=== Step 4: Scraping top {request.top_count} companies for full data ===")
                
                top_references = [comp['reference'] for comp in all_companies_with_scores[:request.top_count]]
                
                # Check freshness and scrape
                fresh_result = db_manager.get_fresh_companies(top_references, request.freshness_days)
                fresh_data = fresh_result['fresh_data']
                need_scraping = fresh_result['need_scraping']
                
                logger.info(f"Found {len(fresh_data)} fresh in DB, need to scrape {len(need_scraping)}")
                
                # Scrape companies that need updating
                newly_scraped = {}
                if need_scraping:
                    chunks = [need_scraping[i:i+4] for i in range(0, len(need_scraping), 4)]
                    semaphore = asyncio.Semaphore(4)
                    
                    # Track scraping progress
                    total_to_scrape = len(need_scraping)
                    scraped_count = 0
                    
                    async def scrape_batch(batch):
                        nonlocal scraped_count
                        async with semaphore:
                            browser = await playwright.chromium.launch(headless=True)
                            context = await browser.new_context()
                            page = await context.new_page()
                            bot = TracxnBot(playwright, debug=False)
                            
                            if not await bot.login():
                                await browser.close()
                                return {}
                            
                            batch_results = {}
                            for ref in batch:
                                try:
                                    # Get company name from tracker
                                    company_name = company_tracker.get(ref, {}).get('name', 'Unknown')
                                    
                                    # Send scraping status for this company
                                    await send_status_update(
                                        "fetching_details",
                                        "company_scraped",
                                        f"Scraped: {company_name} ({scraped_count + 1}/{total_to_scrape})",
                                        {"company_name": company_name, "scraped_count": scraped_count + 1, "total": total_to_scrape}
                                    )
                                    
                                    scraped_data = await bot.scrape_company(ref)
                                    if scraped_data:
                                        batch_results[ref] = {
                                            'data': scraped_data,
                                            'timestamp': datetime.now()
                                        }
                                        db_manager.save_company_data(ref, scraped_data)
                                    scraped_count += 1
                                except Exception as e:
                                    logger.error(f"Error scraping {ref}: {e}")
                                    scraped_count += 1
                            
                            await browser.close()
                            return batch_results
                    
                    all_results = await asyncio.gather(*[scrape_batch(chunk) for chunk in chunks])
                    for batch in all_results:
                        newly_scraped.update(batch)
                
                # Send final scraping complete status
                await send_status_update(
                    "fetching_details",
                    "scraping_complete",
                    f"Completed scraping: {len(newly_scraped)} new, {len(fresh_data)} from cache",
                    {"newly_scraped": len(newly_scraped), "from_cache": len(fresh_data)}
                )
                
                logger.info(f"✅ Scraping complete: {len(fresh_data)} from cache, {len(newly_scraped)} newly scraped")
                
                # Step 5: Format response
                # All companies with scores
                all_companies_response = []
                for comp in all_companies_with_scores:
                    all_companies_response.append({
                        'rank': comp['rank'],
                        'reference': comp['reference'],
                        'name': comp['name'],
                        'description': comp['description'],
                        'similarity_score': round(comp['similarity_score'], 4),
                        'tracxn_score': comp['tracxn_score'],
                        'normalized_tracxn_score': round(comp['normalized_tracxn_score'], 4),
                        'combined_score': round(comp['combined_score'], 4),
                        'appearance_count': comp['appearance_count'],
                        'keywords': comp['keywords']
                    })
                
                # Top companies with full data
                top_companies_full_data = []
                for comp in all_companies_with_scores[:request.top_count]:
                    ref = comp['reference']
                    
                    # Get scraped data
                    if ref in fresh_data:
                        company_data = fresh_data[ref]
                        source = 'database'
                    elif ref in newly_scraped:
                        company_data = newly_scraped[ref]['data']
                        source = 'scraped'
                    else:
                        continue
                    
                    top_companies_full_data.append({
                        'rank': comp['rank'],
                        'reference': ref,
                        'name': comp['name'],
                        'similarity_score': round(comp['similarity_score'], 4),
                        'tracxn_score': comp['tracxn_score'],
                        'normalized_tracxn_score': round(comp['normalized_tracxn_score'], 4),
                        'combined_score': round(comp['combined_score'], 4),
                        'appearance_count': comp['appearance_count'],
                        'keywords': comp['keywords'],
                        'full_data': company_data,
                        'source': source
                    })
                
                return {
                    "all_companies": all_companies_response,
                    "top_companies_full_data": top_companies_full_data,
                    "metadata": {
                        "total_keywords_searched": len(request.company_names),
                        "total_unique_companies": len(company_tracker),
                        "all_companies_count": len(all_companies_response),
                        "top_count_requested": request.top_count,
                        "top_count_returned": len(top_companies_full_data),
                        "target_description": request.target_description,
                        "similarity_weight": request.similarity_weight,
                        "score_weight": request.score_weight,
                        "tracxn_score_range": {
                            "min": min_score,
                            "max": max_score
                        }
                    }
                }
                
            except Exception as e:
                logger.error(f"Error in similarity/ranking: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={"error": f"Similarity search failed: {str(e)}"}
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in API-based similarity search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API-based similarity search failed: {str(e)}"
        )
    finally:
        # Clean up request tracking
        if request_id and request_id in active_requests:
            del active_requests[request_id]
            logger.info(f"🗑️ Cleaned up request {request_id}")

@app.post("/cancel/{request_id}")
async def cancel_request(request_id: str):
    """Cancel an active scraping request."""
    if request_id in active_requests:
        active_requests[request_id]["cancelled"] = True
        logger.info(f"🛑 Request {request_id} marked for cancellation")
        return {"status": "cancelled", "request_id": request_id}
    else:
        logger.warning(f"⚠️ Request {request_id} not found in active requests")
        return {"status": "not_found", "request_id": request_id}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_test = DatabaseManager()
        if db_test.connect():
            db_test.disconnect()
            return {"status": "healthy", "database": "connected", "timestamp": datetime.now()}
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "database": "disconnected", "timestamp": datetime.now()}
            )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e), "timestamp": datetime.now()}
        )

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "TracXN Company Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8008,
        reload=True,
        log_level="info"
    )