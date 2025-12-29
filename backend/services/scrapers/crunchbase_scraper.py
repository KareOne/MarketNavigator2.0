"""
Crunchbase Scraper Service.
Wraps the MVP crunchbase_api container with high-scale features.

Original API: http://crunchbase_api:8003
Endpoints:
- POST /search/crunchbase/top-similar-with-rank
- POST /search/crunchbase/batch
- GET /companies

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 1: Crunchbase Analysis
"""
import httpx
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
    Connects to the MVP crunchbase_api container.
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
        
        This is the main endpoint that:
        1. Searches for companies by keywords
        2. Ranks by AI similarity to target description
        3. Combines with Crunchbase rank score
        4. Returns top companies with full data
        
        Per mcp_server/main.py search_crunchbase_companies function.
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
        
        try:
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
