"""
Tracxn API client service.
Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 2: Tracxn Analysis.

Data includes:
- Startup landscape
- Sector analysis
- Valuation estimates
- Growth stages
- Geographic distribution
"""
import httpx
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential
from core.cache import CacheService
from core.exceptions import ExternalAPIError, RateLimitError
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class TracxnClient:
    """
    Tracxn API client with rate limiting and caching.
    """
    
    BASE_URL = 'https://api.tracxn.com/2.2'
    
    def __init__(self):
        self.api_key = getattr(settings, 'TRACXN_API_KEY', '')
        self.timeout = httpx.Timeout(30.0)
    
    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            'accessToken': self.api_key,
            'Content-Type': 'application/json',
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """
        Make an API request with retry logic.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                )
                
                if response.status_code == 429:
                    raise RateLimitError("Tracxn rate limit exceeded")
                
                if response.status_code >= 400:
                    logger.error(f"Tracxn API error: {response.status_code} - {response.text}")
                    raise ExternalAPIError(f"Tracxn API error: {response.status_code}")
                
                return response.json()
            except httpx.RequestError as e:
                logger.error(f"Tracxn request failed: {e}")
                raise ExternalAPIError(f"Failed to connect to Tracxn: {e}")
    
    # =========================================================================
    # Company Search (per FINAL_ARCHITECTURE_SPECIFICATION)
    # =========================================================================
    
    async def search_companies(
        self,
        query: str = None,
        sectors: List[str] = None,
        locations: List[str] = None,
        funding_stage: str = None,
        funding_range: tuple = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for startups matching criteria.
        
        Returns list of startups with:
        - name, description, website
        - sector, funding stage
        - location, employee estimate
        """
        # Check cache first
        cache_key = CacheService.hash_key({
            'query': query,
            'sectors': sectors,
            'locations': locations,
            'limit': limit
        })
        cached = CacheService.get_api_response('tracxn_search', {'key': cache_key})
        if cached:
            return cached
        
        # Build search payload
        payload = {
            'filter': {},
            'limit': limit,
        }
        
        if query:
            payload['filter']['name'] = {'contains': query}
        
        if sectors:
            payload['filter']['primaryIndustrySector'] = {'in': sectors}
        
        if locations:
            payload['filter']['hqLocation'] = {'in': locations}
        
        if funding_stage:
            payload['filter']['latestRoundType'] = {'equals': funding_stage}
        
        try:
            response = await self._make_request('POST', 'companies', data=payload)
            
            companies = self._parse_company_results(response.get('result', []))
            
            # Cache results
            CacheService.set_api_response('tracxn_search', {'key': cache_key}, companies, ttl=3600)
            
            return companies
        except Exception as e:
            logger.error(f"Tracxn search failed: {e}")
            return []
    
    async def get_company_details(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed startup information.
        """
        # Check cache
        cached = CacheService.get_company(f"tracxn_{company_id}")
        if cached:
            return cached
        
        try:
            response = await self._make_request('GET', f'companies/{company_id}')
            company = self._parse_company_detail(response)
            
            # Cache company data
            CacheService.set_company(f"tracxn_{company_id}", company)
            
            return company
        except Exception as e:
            logger.error(f"Failed to get Tracxn company details: {e}")
            return None
    
    async def get_sector_analysis(self, sector: str) -> Dict[str, Any]:
        """
        Get sector analysis including trends and top companies.
        """
        cache_key = CacheService.hash_key({'sector': sector})
        cached = CacheService.get_api_response('tracxn_sector', {'key': cache_key})
        if cached:
            return cached
        
        try:
            response = await self._make_request('GET', f'sectors/{sector}')
            analysis = {
                'sector': sector,
                'total_companies': response.get('totalCompanies', 0),
                'total_funding': response.get('totalFunding', 0),
                'avg_funding': response.get('averageFunding', 0),
                'top_companies': response.get('topCompanies', []),
                'funding_stages': response.get('fundingStageDistribution', {}),
            }
            
            CacheService.set_api_response('tracxn_sector', {'key': cache_key}, analysis, ttl=7200)
            
            return analysis
        except Exception as e:
            logger.error(f"Sector analysis failed: {e}")
            return {}
    
    # =========================================================================
    # Data Parsing
    # =========================================================================
    
    def _parse_company_results(self, results: list) -> List[Dict[str, Any]]:
        """Parse company search results."""
        companies = []
        for company in results:
            companies.append({
                'id': company.get('id'),
                'name': company.get('name', 'Unknown'),
                'description': company.get('description', ''),
                'website': company.get('website', ''),
                'logo': company.get('logoUrl', ''),
                'sector': company.get('primaryIndustrySector', ''),
                'sub_sector': company.get('primaryIndustrySubSector', ''),
                'funding_stage': company.get('latestRoundType', ''),
                'total_funding': company.get('totalFunding', 0),
                'funding_currency': 'USD',
                'employee_estimate': company.get('employeeEstimate', ''),
                'founded': company.get('foundedYear'),
                'location': self._parse_location(company),
            })
        return companies
    
    def _parse_company_detail(self, company: dict) -> Dict[str, Any]:
        """Parse detailed company info."""
        return {
            'id': company.get('id'),
            'name': company.get('name', ''),
            'description': company.get('description', ''),
            'long_description': company.get('longDescription', ''),
            'website': company.get('website', ''),
            'logo': company.get('logoUrl', ''),
            'linkedin': company.get('linkedinUrl', ''),
            'twitter': company.get('twitterUrl', ''),
            'sector': company.get('primaryIndustrySector', ''),
            'sub_sector': company.get('primaryIndustrySubSector', ''),
            'business_model': company.get('businessModel', ''),
            'founded': company.get('foundedYear'),
            'employee_estimate': company.get('employeeEstimate', ''),
            'total_funding': company.get('totalFunding', 0),
            'last_funding_date': company.get('lastFundingDate'),
            'funding_stage': company.get('latestRoundType', ''),
            'funding_rounds': company.get('fundingRounds', []),
            'investors': company.get('investors', []),
            'location': self._parse_location(company),
        }
    
    def _parse_location(self, company: dict) -> str:
        """Parse location to readable string."""
        city = company.get('hqCity', '')
        country = company.get('hqCountry', '')
        if city and country:
            return f"{city}, {country}"
        return city or country or ''


# Singleton instance
tracxn_client = TracxnClient()
