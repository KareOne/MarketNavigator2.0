"""
Crunchbase API client service.
Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 1: Crunchbase Analysis.

Data includes:
- Similar/competitor companies
- Funding data and trends
- Employee counts
- Investment rounds
- Market insights
"""
import httpx
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential
from core.cache import CacheService
from core.exceptions import ExternalAPIError, RateLimitError
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class CrunchbaseClient:
    """
    Crunchbase API client with rate limiting and caching.
    """
    
    BASE_URL = 'https://api.crunchbase.com/api/v4'
    
    def __init__(self):
        self.api_key = getattr(settings, 'CRUNCHBASE_API_KEY', '')
        self.timeout = httpx.Timeout(30.0)
    
    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            'X-cb-user-key': self.api_key,
            'Content-Type': 'application/json',
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
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
                    params=params,
                    json=data,
                )
                
                if response.status_code == 429:
                    raise RateLimitError("Crunchbase rate limit exceeded")
                
                if response.status_code >= 400:
                    logger.error(f"Crunchbase API error: {response.status_code} - {response.text}")
                    raise ExternalAPIError(f"Crunchbase API error: {response.status_code}")
                
                return response.json()
            except httpx.RequestError as e:
                logger.error(f"Crunchbase request failed: {e}")
                raise ExternalAPIError(f"Failed to connect to Crunchbase: {e}")
    
    # =========================================================================
    # Company Search (per FINAL_ARCHITECTURE_SPECIFICATION)
    # =========================================================================
    
    async def search_companies(
        self,
        query: str,
        categories: List[str] = None,
        locations: List[str] = None,
        employee_range: tuple = None,
        funding_total_min: int = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for companies matching criteria.
        
        Returns list of companies with:
        - name, description, website
        - funding total, last funding date
        - employee count
        - categories
        """
        # Check cache first
        cache_key = CacheService.hash_key({
            'query': query,
            'categories': categories,
            'locations': locations,
            'limit': limit
        })
        cached = CacheService.get_api_response('crunchbase_search', {'key': cache_key})
        if cached:
            return cached
        
        # Build search query
        field_ids = [
            'identifier', 'short_description', 'website',
            'num_employees_enum', 'funding_total', 'last_funding_at',
            'categories', 'location_identifiers', 'founded_on'
        ]
        
        query_params = {
            'field_ids': ','.join(field_ids),
            'limit': limit,
        }
        
        if query:
            query_params['query'] = query
        
        try:
            response = await self._make_request(
                'GET',
                'searches/organizations',
                params=query_params
            )
            
            companies = self._parse_company_results(response.get('entities', []))
            
            # Cache results
            CacheService.set_api_response('crunchbase_search', {'key': cache_key}, companies, ttl=3600)
            
            return companies
        except Exception as e:
            logger.error(f"Company search failed: {e}")
            return []
    
    async def get_company_details(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed company information.
        """
        # Check cache
        cached = CacheService.get_company(f"crunchbase_{company_id}")
        if cached:
            return cached
        
        try:
            response = await self._make_request('GET', f'entities/organizations/{company_id}')
            company = self._parse_company_detail(response.get('properties', {}))
            
            # Cache company data (7 days per spec)
            CacheService.set_company(f"crunchbase_{company_id}", company)
            
            return company
        except Exception as e:
            logger.error(f"Failed to get company details: {e}")
            return None
    
    async def get_funding_rounds(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Get funding rounds for a company.
        """
        try:
            response = await self._make_request(
                'GET',
                f'entities/organizations/{company_id}/funding_rounds'
            )
            return self._parse_funding_rounds(response.get('entities', []))
        except Exception as e:
            logger.error(f"Failed to get funding rounds: {e}")
            return []
    
    # =========================================================================
    # Data Parsing
    # =========================================================================
    
    def _parse_company_results(self, entities: list) -> List[Dict[str, Any]]:
        """Parse company search results."""
        companies = []
        for entity in entities:
            props = entity.get('properties', {})
            companies.append({
                'id': entity.get('identifier', {}).get('uuid'),
                'name': entity.get('identifier', {}).get('value', 'Unknown'),
                'description': props.get('short_description', ''),
                'website': props.get('website', {}).get('value', ''),
                'employee_count': props.get('num_employees_enum', 'Unknown'),
                'funding_total': props.get('funding_total', {}).get('value', 0),
                'funding_currency': props.get('funding_total', {}).get('currency', 'USD'),
                'last_funding': props.get('last_funding_at'),
                'founded': props.get('founded_on'),
                'categories': [c.get('value') for c in props.get('categories', [])],
                'location': self._parse_location(props.get('location_identifiers', [])),
            })
        return companies
    
    def _parse_company_detail(self, props: dict) -> Dict[str, Any]:
        """Parse detailed company info."""
        return {
            'name': props.get('name', ''),
            'description': props.get('short_description', ''),
            'long_description': props.get('description', ''),
            'website': props.get('website', {}).get('value', ''),
            'linkedin': props.get('linkedin', {}).get('value', ''),
            'twitter': props.get('twitter', {}).get('value', ''),
            'employee_count': props.get('num_employees_enum', ''),
            'founded': props.get('founded_on'),
            'funding_total': props.get('funding_total', {}).get('value', 0),
            'funding_rounds_count': props.get('num_funding_rounds', 0),
            'last_funding': props.get('last_funding_at'),
            'last_funding_type': props.get('last_funding_type'),
            'stock_symbol': props.get('stock_symbol'),
            'ipo_status': props.get('ipo_status'),
            'categories': [c.get('value') for c in props.get('categories', [])],
        }
    
    def _parse_funding_rounds(self, entities: list) -> List[Dict[str, Any]]:
        """Parse funding rounds."""
        rounds = []
        for entity in entities:
            props = entity.get('properties', {})
            rounds.append({
                'id': entity.get('identifier', {}).get('uuid'),
                'type': props.get('investment_type'),
                'announced_date': props.get('announced_on'),
                'money_raised': props.get('money_raised', {}).get('value', 0),
                'currency': props.get('money_raised', {}).get('currency', 'USD'),
                'num_investors': props.get('num_investors', 0),
            })
        return rounds
    
    def _parse_location(self, locations: list) -> str:
        """Parse location identifiers to readable string."""
        if not locations:
            return ''
        location_parts = [loc.get('value', '') for loc in locations[:2]]
        return ', '.join(location_parts)


# Singleton instance
crunchbase_client = CrunchbaseClient()
