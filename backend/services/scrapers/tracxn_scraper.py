"""
Tracxn Scraper Service.
Wraps the MVP tracxn_api container with high-scale features.
Supports remote workers via orchestrator when enabled.

Original API: http://tracxn_api:8008
Endpoints:
- POST /scrape-batch-api-with-rank
- POST /scrape-batch
- GET /companies

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 2: Tracxn Analysis
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


class TracxnScraperClient(RetryableScraperClient):
    """
    High-scale client for Tracxn scraper API.
    Supports orchestrator-based remote workers with fallback to direct API.
    """
    
    def __init__(self):
        # Get URL from settings or use default container name
        base_url = getattr(settings, 'TRACXN_SCRAPER_URL', 'http://tracxn_api:8008')
        
        super().__init__(
            service_name='tracxn_scraper',
            base_url=base_url,
            timeout=3000.0,  # 50 minutes for long scraping operations
            max_retries=3,
            cache_ttl=86400,  # 24 hours
        )
        
        # Orchestrator settings
        self.use_orchestrator = getattr(settings, 'USE_ORCHESTRATOR', False)
        self.orchestrator_url = getattr(settings, 'ORCHESTRATOR_URL', 'http://orchestrator:8010')
    
    async def _check_orchestrator_available(self) -> bool:
        """
        Check if orchestrator is enabled and reachable for Tracxn workers.
        
        Tracxn REQUIRES orchestrator with remote workers - no fallback to direct API.
        """
        if not self.use_orchestrator:
            logger.error("❌ Orchestrator disabled in settings - Tracxn requires orchestrator")
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.orchestrator_url}/workers/tracxn/stats")
                if response.status_code == 200:
                    data = response.json()
                    total_workers = data.get('total', 0)
                    idle_workers = data.get('idle', 0)
                    logger.info(f"🔍 Tracxn Orchestrator: {total_workers} workers ({idle_workers} idle)")
                    
                    if total_workers == 0:
                        logger.error("❌ No Tracxn workers connected to orchestrator")
                        return False
                    
                    return True
                else:
                    logger.error(f"❌ Orchestrator stats failed: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Orchestrator unreachable for Tracxn: {e}")
            return False
    
    async def _submit_to_orchestrator(
        self,
        action: str,
        payload: Dict[str, Any],
        report_id: str,
        timeout: float = 10800.0  # 3 hour timeout for long-running Tracxn scrapes
    ) -> Dict[str, Any]:
        """Submit task to orchestrator and wait for result."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=30.0)) as client:
            # Submit task
            submit_response = await client.post(
                f"{self.orchestrator_url}/tasks/submit",
                json={
                    "api_type": "tracxn",
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
            logger.info(f"📤 Tracxn task submitted to orchestrator: {task_id}")
            
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
                    logger.info(f"✅ Tracxn orchestrator task completed: {task_id}")
                    return status_data.get("result", {})
                elif task_status in ("failed", "cancelled"):
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"Tracxn orchestrator task {task_status}: {error_msg}")
            
            raise Exception(f"Tracxn orchestrator task timed out after {timeout}s")
    
    async def search_with_ranking(
        self,
        company_names: List[str],
        target_description: str,
        num_companies_per_search: int = 30,
        freshness_days: int = 180,
        top_count: int = 10,
        similarity_weight: float = 0.75,
        score_weight: float = 0.25,
        sort_by: str = "relevance",
        report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for companies with AI similarity + Tracxn score ranking.
        
        Uses orchestrator remote workers ONLY - no fallback to direct API.
        
        This is the main endpoint that:
        1. Searches Tracxn for each company name/keyword
        2. Ranks by AI similarity to target description
        3. Combines with Tracxn score
        4. Returns top companies with full scraped data
        
        Args:
            report_id: Optional report ID for status callback updates
        
        Per mcp_server/main.py search_tracxn_companies function.
        
        Raises:
            Exception: If orchestrator is unavailable or no workers connected
        """
        logger.info(f"Tracxn ranked search: {len(company_names)} keywords, report_id={report_id}")
        
        request_data = {
            "company_names": company_names,
            "num_companies_per_search": num_companies_per_search,
            "freshness_days": freshness_days,
            "top_count": top_count,
            "target_description": target_description,
            "similarity_weight": similarity_weight,
            "score_weight": score_weight,
            "sort_by": sort_by,
        }
        
        # Add report_id for status callbacks if provided
        if report_id:
            request_data["report_id"] = report_id
        
        # Check orchestrator availability - REQUIRED, no fallback
        orchestrator_available = await self._check_orchestrator_available()
        
        if not orchestrator_available:
            raise Exception(
                "Tracxn orchestrator is unavailable or no workers connected. "
                "Please ensure the orchestrator is running and at least one Tracxn worker is connected."
            )
        
        # Submit to orchestrator
        logger.info("🔄 Submitting Tracxn search to orchestrator queue")
        result = await self._submit_to_orchestrator(
            action="search_with_rank",
            payload=request_data,
            report_id=report_id or "direct-search",
        )
        
        # Mark that orchestrator was used
        if 'metadata' not in result:
            result['metadata'] = {}
        result['metadata']['used_orchestrator'] = True
        
        logger.info(
            f"Tracxn (orchestrator) returned: "
            f"{result.get('metadata', {}).get('all_companies_count', 0)} total, "
            f"{result.get('metadata', {}).get('top_count_returned', 0)} top companies"
        )
        
        return result
    
    async def search_batch(
        self,
        company_names: List[str],
        num_companies_per_search: int = 10,
        freshness_days: int = 180,
    ) -> Dict[str, Any]:
        """
        Basic batch search without ranking.
        """
        request_data = {
            "company_names": company_names,
            "num_companies_per_search": num_companies_per_search,
            "freshness_days": freshness_days,
        }
        
        return await self.request_with_retry(
            'POST',
            '/scrape-batch',
            data=request_data,
        )
    
    async def search_by_references(
        self,
        company_references: List[str],
        freshness_days: int = 180,
    ) -> Dict[str, Any]:
        """
        Scrape companies by their Tracxn reference URLs.
        """
        request_data = {
            "company_references": company_references,
            "freshness_days": freshness_days,
        }
        
        return await self.request_with_retry(
            'POST',
            '/scrape-references',
            data=request_data,
        )
    
    def parse_company_data(self, raw_company: Dict) -> Dict[str, Any]:
        """
        Parse raw company data from scraper into standardized format.
        """
        # Handle nested 'data' field from Tracxn
        data = raw_company.get('data', [{}])
        company_info = data[0] if isinstance(data, list) and data else {}
        
        return {
            'name': company_info.get('Name', raw_company.get('name', 'Unknown')),
            'description': company_info.get('Overview', raw_company.get('description', '')),
            'website': company_info.get('Website', ''),
            'logo': company_info.get('Logo', ''),
            'founded': company_info.get('Founded', ''),
            'employee_count': company_info.get('Employees', ''),
            'funding_total': company_info.get('Total Equity Funding', ''),
            'funding_stage': company_info.get('Stage', ''),
            'valuation': company_info.get('Valuation', ''),
            'hq_location': company_info.get('Headquarters', ''),
            'sectors': company_info.get('Sectors', []),
            'investors': company_info.get('Key Investors', []),
            'revenue': company_info.get('Revenue', ''),
            # Scoring
            'similarity_score': raw_company.get('similarity_score', 0),
            'tracxn_score': raw_company.get('tracxn_score', 0),
            'combined_score': raw_company.get('combined_score', 0),
            # Meta
            'tracxn_url': raw_company.get('company_reference', ''),
            'last_updated': raw_company.get('last_updated', ''),
        }


# Singleton instance
tracxn_scraper = TracxnScraperClient()
