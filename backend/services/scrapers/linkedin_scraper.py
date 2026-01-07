"""
Linkedin Scraper Service.
Wraps the Linkedin Worker Agent via Orchestrator.

Supports remote workers via orchestrator when enabled.
"""
import httpx
import asyncio
from django.conf import settings
from services.scrapers import RetryableScraperClient
from core.exceptions import ExternalAPIError
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LinkedinScraperClient(RetryableScraperClient):
    """
    High-scale client for Linkedin scraper API via Orchestrator.
    """
    
    def __init__(self):
        # Base URL for local service (if ever needed fallback)
        base_url = getattr(settings, 'LINKEDIN_SCRAPER_URL', 'http://linkedin_api:8004')
        
        super().__init__(
            service_name='linkedin_scraper',
            base_url=base_url,
            timeout=900.0,
            max_retries=3,
        )
        
        # Orchestrator settings
        self.use_orchestrator = getattr(settings, 'USE_ORCHESTRATOR', True) # Default to True for Linkedin
        self.orchestrator_url = getattr(settings, 'ORCHESTRATOR_URL', 'http://orchestrator:8010')
    
    async def _check_orchestrator_available(self) -> bool:
        """Check if orchestrator is enabled and reachable."""
        if not self.use_orchestrator:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.orchestrator_url}/workers/social/stats")
                if response.status_code == 200:
                    data = response.json()
                    total = data.get('total', 0)
                    if total > 0:
                        return True
                    else:
                        logger.warning("No Linkedin workers connected")
                        return True # Still return True so it queues
                return False
        except Exception:
            return False
    
    async def _submit_to_orchestrator(
        self,
        action: str,
        payload: Dict[str, Any],
        report_id: str,
        timeout: float = 3600.0
    ) -> Dict[str, Any]:
        """Submit task to orchestrator and wait for result."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=30.0)) as client:
            # Submit task
            submit_response = await client.post(
                f"{self.orchestrator_url}/tasks/submit",
                json={
                    "api_type": "social",
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
            logger.info(f"📤 Linkedin task submitted: {task_id}")
            
            # Poll for completion
            poll_interval = 5.0
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
                    logger.info(f"✅ Linkedin task completed: {task_id}")
                    return status_data.get("result", {})
                elif task_status in ("failed", "cancelled"):
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"Linkedin task {task_status}: {error_msg}")
            
            raise Exception(f"Linkedin task timed out after {timeout}s")

    async def search_tweets(
        self,
        keywords: List[str],
        limit: int = 50,
        report_id: str = None
    ) -> Dict[str, Any]:
        """
        Search tweets for multiple keywords.
        """
        logger.info(f"Linkedin search: {len(keywords)} keywords")
        
        request_data = {
            "keywords": keywords,
            "limit": limit
        }
        
        if not await self._check_orchestrator_available():
             raise ExternalAPIError("Orchestrator unavailable for Linkedin search")
             
        try:
            result = await self._submit_to_orchestrator(
                action="search_tweets",
                payload=request_data,
                report_id=report_id or "direct-search"
            )
            return result
        except Exception as e:
            logger.error(f"Linkedin search failed: {e}")
            raise ExternalAPIError(f"Linkedin search failed: {e}")

    async def get_tweet_replies(
        self,
        tweet_id: str,
        limit: int = 50,
        report_id: str = None
    ) -> Dict[str, Any]:
        """
        Get replies for a specific tweet.
        """
        request_data = {
            "tweet_id": tweet_id,
            "limit": limit
        }
        
        try:
            result = await self._submit_to_orchestrator(
                action="tweet_replies",
                payload=request_data,
                report_id=report_id or "direct-reply-fetch"
            )
            return result
        except Exception as e:
            logger.error(f"Linkedin reply fetch failed: {e}")
            raise ExternalAPIError(f"Linkedin reply fetch failed: {e}")


# Singleton instance
linkedin_scraper = LinkedinScraperClient()
