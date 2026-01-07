"""
API Adapters - pluggable adapters for different API types.
"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)


class BaseAPIAdapter(ABC):
    """
    Base class for API adapters.
    
    Each API type (crunchbase, tracxn, social) has its own adapter
    that knows how to call the local API and map actions to endpoints.
    """
    
    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        self.base_url = base_url
        self.client = http_client
    
    @abstractmethod
    def get_endpoint(self, action: str) -> str:
        """Get the API endpoint path for an action."""
        pass
    
    @abstractmethod
    def prepare_payload(self, action: str, payload: dict, report_id: str) -> dict:
        """Prepare the payload for the API call."""
        pass
    
    async def execute(
        self, 
        action: str, 
        payload: dict, 
        report_id: str,
        status_callback: Callable = None
    ) -> dict:
        """
        Execute an API call.
        
        Args:
            action: The action to perform
            payload: Request payload
            report_id: Report ID for status tracking
            status_callback: Optional callback for status updates
            
        Returns:
            API response as dict
        """
        endpoint = self.get_endpoint(action)
        url = f"{self.base_url}{endpoint}"
        prepared_payload = self.prepare_payload(action, payload, report_id)
        
        logger.info(f"📡 Calling {url}")
        
        response = await self.client.post(
            url,
            json=prepared_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text[:500]}")
        
        return response.json()


class CrunchbaseAdapter(BaseAPIAdapter):
    """Adapter for Crunchbase scraper API."""
    
    ENDPOINTS = {
        "search_with_rank": "/search/crunchbase/top-similar-with-rank",
        "search_similar": "/search/crunchbase/top-similar",
        "search_similar_full": "/search/crunchbase/top-similar-full",
        "search_batch": "/search/crunchbase/batch",
        "search_hashtag": "/search/crunchbase/hashtag",
        "get_all": "/companies/all",
        "get_by_names": "/companies/by-names",
    }
    
    def get_endpoint(self, action: str) -> str:
        return self.ENDPOINTS.get(action, f"/{action}")
    
    def prepare_payload(self, action: str, payload: dict, report_id: str) -> dict:
        """Add report_id for status tracking."""
        return {
            **payload,
            "report_id": report_id
        }


class TracxnAdapter(BaseAPIAdapter):
    """Adapter for Tracxn scraper API."""
    
    ENDPOINTS = {
        "search_with_rank": "/scrape-batch-api-with-rank",
        "search": "/scrape-batch-api",
        "search_batch": "/scrape-batch",
        "search_by_references": "/scrape-references",
        "get_all": "/companies",
        "health": "/health",
    }
    
    def get_endpoint(self, action: str) -> str:
        return self.ENDPOINTS.get(action, f"/{action}")
    
    def prepare_payload(self, action: str, payload: dict, report_id: str) -> dict:
        """Add report_id for status tracking."""
        return {
            **payload,
            "report_id": report_id
        }


class TwitterAdapter(BaseAPIAdapter):
    """Adapter for Twitter scraper API."""
    
    ENDPOINTS = {
        "search_tweets": "/search/tweets",
        "tweet_replies": "/tweet/replies",
        "tweet_thread": "/tweet/{tweet_id}/thread",
        "health": "/health",
    }
    
    def get_endpoint(self, action: str) -> str:
        s = self.ENDPOINTS.get(action, f"/{action}")
        return s
    
    def prepare_payload(self, action: str, payload: dict, report_id: str) -> dict:
        """
        Prepare payload matching api.py Pydantic models.
        """
        if action == "search_tweets":
            # Map search_tweets fields
            return {
                "keyword": payload.get("keywords", [""])[0] if isinstance(payload.get("keywords"), list) else payload.get("keyword", ""), # Handle list or string
                "query_type": payload.get("query_type", "Top"),
                "num_posts": payload.get("limit", 10), # Map limit to num_posts
                "num_comments": payload.get("num_comments", 0),
                # Note: api.py doesn't accept report_id in body, so we don't send it to the local API
                # The worker agent tracks the task/report association internally
            }
        elif action == "tweet_replies":
            return {
                "tweet_id": payload.get("tweet_id", ""),
                "num_replies": payload.get("limit", 20)
            }
            
        return payload


def get_adapter(api_type: str, base_url: str, client: httpx.AsyncClient) -> BaseAPIAdapter:
    """
    Factory function to get the appropriate adapter.
    
    Args:
        api_type: Type of API (crunchbase, tracxn, social)
        base_url: Base URL of the local API
        client: HTTP client for making requests
        
    Returns:
        Configured API adapter
    """
    adapters = {
        "crunchbase": CrunchbaseAdapter,
        "tracxn": TracxnAdapter,
        "social": TwitterAdapter,
        "twitter": TwitterAdapter,
    }
    
    adapter_class = adapters.get(api_type)
    if not adapter_class:
        raise ValueError(f"Unknown API type: {api_type}")
    
    return adapter_class(base_url, client)
