"""
Tracxn Scraper Service.
Wraps the MVP tracxn_api container with high-scale features.

Original API: http://tracxn_api:8008
Endpoints:
- POST /scrape-batch-api-with-rank
- POST /scrape-batch
- GET /companies

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 2: Tracxn Analysis
"""
import httpx
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
    Connects to the MVP tracxn_api container.
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
        
        This is the main endpoint that:
        1. Searches Tracxn for each company name/keyword
        2. Ranks by AI similarity to target description
        3. Combines with Tracxn score
        4. Returns top companies with full scraped data
        
        Args:
            report_id: Optional report ID for status callback updates
        
        Per mcp_server/main.py search_tracxn_companies function.
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
        
        try:
            result = await self.request_with_retry(
                'POST',
                '/scrape-batch-api-with-rank',
                data=request_data,
                use_cache=True,
            )
            
            metadata = result.get('metadata', {})
            logger.info(
                f"Tracxn returned: {metadata.get('all_companies_count', 0)} total, "
                f"{metadata.get('top_count_returned', 0)} top companies"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Tracxn search failed: {e}")
            raise
    
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
