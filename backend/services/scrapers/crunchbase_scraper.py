"""
Crunchbase Scraper Service.
Wraps the MVP crunchbase_api container with high-scale features.
Supports remote workers via orchestrator when enabled.

Original API: http://crunchbase_api:8003
Endpoints:
- POST /search/crunchbase/top-similar-with-rank
- POST /search/crunchbase/batch
- GET /companies

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 1: Crunchbase Analysis
"""
import httpx
import asyncio
from django.conf import settings
from services.scrapers import RetryableScraperClient
from core.cache import CacheService
from core.exceptions import ExternalAPIError
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CrunchbaseScraperClient(RetryableScraperClient):
    """
    High-scale client for Crunchbase scraper API.
    Supports orchestrator-based remote workers with fallback to direct API.
    """
    
    def __init__(self):
        # Get URL from settings or use default container name
        base_url = getattr(settings, 'CRUNCHBASE_SCRAPER_URL', 'http://crunchbase_api:8003')
        
        super().__init__(
            service_name='crunchbase_scraper',
            base_url=base_url,
            timeout=900.0,  # 15 minutes for long scraping operations
            max_retries=3,
            cache_ttl=86400,  # 24 hours - scraping results are expensive
        )
        
        # Orchestrator settings
        self.use_orchestrator = getattr(settings, 'USE_ORCHESTRATOR', False)
        self.orchestrator_url = getattr(settings, 'ORCHESTRATOR_URL', 'http://orchestrator:8010')
    
    async def _check_orchestrator_available(self) -> bool:
        """Check if orchestrator has any connected workers (tasks will queue if busy)."""
        if not self.use_orchestrator:
            logger.debug("Orchestrator disabled in settings")
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.orchestrator_url}/workers/crunchbase/stats")
                if response.status_code == 200:
                    data = response.json()
                    total_workers = data.get('total', 0)
                    idle_workers = data.get('idle', 0)
                    logger.info(f"🔍 Orchestrator check: {total_workers} total workers, {idle_workers} idle")
                    # Use orchestrator if ANY workers are connected (tasks will queue)
                    return total_workers > 0
                else:
                    logger.warning(f"Orchestrator stats failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"Orchestrator check failed: {e}")
        return False
    
    async def _submit_to_orchestrator(
        self,
        action: str,
        payload: Dict[str, Any],
        report_id: str,
        timeout: float = 10800.0  # 3 hour timeout
    ) -> Dict[str, Any]:
        """Submit task to orchestrator and wait for result."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=30.0)) as client:
            # Submit task
            submit_response = await client.post(
                f"{self.orchestrator_url}/tasks/submit",
                json={
                    "api_type": "crunchbase",
                    "action": action,
                    "report_id": report_id,
                    "payload": payload,
                    "priority": 5
                }
            )
            
            if submit_response.status_code != 200:
                raise Exception(f"Orchestrator submit failed: {submit_response.text}")
            
            task_data = submit_response.json()
            task_id = task_data.get("task_id")
            logger.info(f"📤 Task submitted to orchestrator: {task_id}")
            
            # Poll for completion
            poll_interval = 5.0  # Check every 5 seconds
            elapsed = 0.0
            while elapsed < timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                status_response = await client.get(f"{self.orchestrator_url}/tasks/{task_id}")
                if status_response.status_code != 200:
                    continue
                
                status_data = status_response.json()
                task_status = status_data.get("status")
                
                if task_status == "completed":
                    logger.info(f"✅ Orchestrator task completed: {task_id}")
                    return status_data.get("result", {})
                elif task_status in ("failed", "cancelled"):
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"Orchestrator task {task_status}: {error_msg}")
            
            raise Exception(f"Orchestrator task timed out after {timeout}s")
    
    async def search_similar_companies(
        self,
        keywords: List[str],
        target_description: str,
        num_companies: int = 20,
        days_threshold: int = 180,
        top_count: int = 10,
        similarity_weight: float = 0.75,
        rank_weight: float = 0.25,
        report_id: str = None,  # For real-time status callbacks
    ) -> Dict[str, Any]:
        """
        Search for companies using AI-powered similarity + rank scoring.
        
        Uses orchestrator remote workers if available, with fallback to direct API.
        """
        logger.info(f"Crunchbase similarity search: {len(keywords)} keywords")
        
        request_data = {
            "keywords": keywords,
            "target_description": target_description,
            "num_companies": num_companies,
            "days_threshold": days_threshold,
            "top_count": top_count,
            "similarity_weight": similarity_weight,
            "rank_weight": rank_weight,
        }
        
        # Include report_id for real-time status callbacks
        if report_id:
            request_data["report_id"] = report_id
        
        # Try orchestrator if enabled and workers available
        orchestrator_available = await self._check_orchestrator_available()
        if orchestrator_available:
            try:
                logger.info("🔄 Using orchestrator for Crunchbase search (remote worker)")
                result = await self._submit_to_orchestrator(
                    action="search_with_rank",
                    payload=request_data,
                    report_id=report_id or "direct-search",
                    # Use default 3-hour timeout - long tasks like scraping can take a while
                )
                logger.info(
                    f"Crunchbase (orchestrator) returned: "
                    f"{result.get('metadata', {}).get('all_companies_count', 0)} total, "
                    f"{result.get('metadata', {}).get('top_count_returned', 0)} top companies"
                )
                return result
            except Exception as e:
                # If orchestrator has workers but failed, don't fall back to direct API
                # (there's no local crunchbase_api container anyway)
                logger.error(f"Orchestrator task failed: {e}")
                raise ExternalAPIError(f"Crunchbase scraper (orchestrator) failed: {e}")
        
        # Fallback to direct API call
        try:
            logger.info("📡 Using direct API for Crunchbase search (local container)")
            result = await self.request_with_retry(
                'POST',
                '/search/crunchbase/top-similar-with-rank',
                data=request_data,
                use_cache=True,
            )
            
            logger.info(
                f"Crunchbase returned: {result.get('metadata', {}).get('all_companies_count', 0)} total, "
                f"{result.get('metadata', {}).get('top_count_returned', 0)} top companies"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Crunchbase search failed: {e}")
            raise
    
    async def search_batch(
        self,
        keywords: List[str],
        num_companies: int = 5,
        days_threshold: int = 180,
    ) -> Dict[str, Any]:
        """
        Basic batch search without similarity scoring.
        """
        request_data = {
            "keywords": keywords,
            "num_companies": num_companies,
            "days_threshold": days_threshold,
        }
        
        return await self.request_with_retry(
            'POST',
            '/search/crunchbase/batch',
            data=request_data,
        )
    
    async def get_all_companies(self) -> List[Dict[str, Any]]:
        """
        Get all companies stored in the scraper database.
        """
        result = await self.request_with_retry(
            'GET',
            '/companies',
            use_cache=False,  # Don't cache database dumps
        )
        return result.get('companies', [])
    
    async def get_companies_by_names(
        self,
        company_names: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve specific companies from the database.
        """
        result = await self.request_with_retry(
            'POST',
            '/companies/by-names',
            data={'company_names': company_names},
        )
        return result.get('companies', [])
    
    def parse_company_data(self, raw_company: Dict) -> Dict[str, Any]:
        """
        Parse raw company data from scraper into standardized format.
        """
        # Company name can be stored as 'name' or 'Company Name' depending on source
        name = raw_company.get('name') or raw_company.get('Company Name') or 'Unknown'
        
        return {
            'name': name,
            'description': raw_company.get('about', raw_company.get('About', raw_company.get('description', ''))),
            'website': raw_company.get('website_url', raw_company.get('Website', raw_company.get('url', ''))),
            'logo': raw_company.get('logo_url', ''),
            'founded': raw_company.get('founded_year', raw_company.get('founded', '')),
            'employee_count': raw_company.get('employee_count', raw_company.get('Headcount', raw_company.get('employees', ''))),
            'funding_total': raw_company.get('total_funding', raw_company.get('Total Funding Amount', raw_company.get('funding', ''))),
            'last_funding': raw_company.get('last_funding_date', ''),
            'hq_location': raw_company.get('hq_location', raw_company.get('location', '')),
            'industries': raw_company.get('industries', raw_company.get('Industry Tags', [])),
            'founders': raw_company.get('founders', []),
            # Similarity/ranking scores
            'similarity_score': raw_company.get('similarity_score', 0),
            'rank_score': raw_company.get('rank_score', 0),
            'combined_score': raw_company.get('combined_score', 0),
        }


# Singleton instance
crunchbase_scraper = CrunchbaseScraperClient()
