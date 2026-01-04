"""
Enrichment Manager - Background database enrichment using idle workers.

Monitors for idle Crunchbase workers and dispatches enrichment tasks
when no backend requests are pending.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import httpx

import config

logger = logging.getLogger(__name__)


class EnrichmentManager:
    """
    Manages background database enrichment using idle workers.
    
    Key behaviors:
    - Monitors for idle Crunchbase workers
    - Fetches pending enrichment keywords from Django backend
    - Dispatches enrichment tasks only when:
      1. At least one Crunchbase worker is idle
      2. No pending backend tasks in queue
      3. Enrichment is not paused
    - Freezes on backend request, resumes when queue is empty
    """
    
    # Backend URL for enrichment API
    BACKEND_URL = config.BACKEND_STATUS_URL.replace('/api/reports/status-update/', '')
    
    # Enrichment task parameters
    DAYS_THRESHOLD = 180  # Skip companies scraped within 180 days
    
    def __init__(self, redis_client, registry, task_queue):
        self.redis = redis_client
        self.registry = registry
        self.task_queue = task_queue
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._current_enrichment_task_id: Optional[str] = None
        
    async def start(self):
        """Start the enrichment monitoring loop."""
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("✅ Enrichment manager started")
    
    async def stop(self):
        """Stop the enrichment manager."""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Enrichment manager stopped")
    
    async def _monitor_loop(self):
        """
        Background loop that checks for enrichment opportunities.
        Runs every 30 seconds.
        """
        while self._is_running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if await self.should_enrich():
                    await self.dispatch_next_enrichment()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Enrichment monitor error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def should_enrich(self) -> bool:
        """
        Check if conditions allow dispatching an enrichment task.
        
        Returns True if:
        1. Enrichment is not paused (checked via backend)
        2. No pending backend tasks in queue
        3. At least one Crunchbase worker is idle
        """
        # Check for pending backend tasks
        stats = await self.task_queue.get_queue_stats()
        crunchbase_pending = stats.get("crunchbase", {}).get("pending", 0)
        
        if crunchbase_pending > 0:
            logger.debug(f"Skipping enrichment: {crunchbase_pending} backend tasks pending")
            return False
        
        # Check for idle workers
        idle_workers = self.registry.get_idle_workers("crunchbase")
        if not idle_workers:
            logger.debug("Skipping enrichment: no idle Crunchbase workers")
            return False
        
        # Check if enrichment is paused (via backend API - internal endpoint, no auth)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.BACKEND_URL}/api/admin/enrichment/internal/status/")
                if response.status_code == 200:
                    status_data = response.json()
                    if status_data.get('is_paused', False):
                        logger.debug("Skipping enrichment: enrichment is paused")
                        return False
                    if status_data.get('pending_count', 0) == 0:
                        logger.debug("Skipping enrichment: no pending keywords")
                        return False
        except Exception as e:
            logger.warning(f"Could not check enrichment status: {e}")
            return False
        
        return True
    
    async def fetch_next_keyword(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the next pending keyword from Django backend.
        
        Returns keyword data or None if no keywords available.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Use internal endpoint - no auth required
                response = await client.get(
                    f"{self.BACKEND_URL}/api/admin/enrichment/internal/keywords/"
                )
                
                if response.status_code == 200:
                    keywords = response.json()
                    if keywords and len(keywords) > 0:
                        # Return highest priority keyword (first in list due to ordering)
                        return keywords[0]
                        
        except Exception as e:
            logger.error(f"Failed to fetch keywords: {e}")
        
        return None
    
    async def dispatch_next_enrichment(self):
        """
        Fetch next keyword and dispatch enrichment task.
        """
        keyword_data = await self.fetch_next_keyword()
        
        if not keyword_data:
            return
        
        keyword_id = keyword_data.get('id')
        keyword_text = keyword_data.get('keyword')
        num_companies = keyword_data.get('num_companies', 50)
        
        logger.info(f"📥 Dispatching enrichment for keyword: {keyword_text}")
        
        # Notify backend that we're starting
        await self._notify_backend(keyword_id, 'start')
        
        # Create enrichment task
        from models import TaskSubmitRequest
        
        request = TaskSubmitRequest(
            api_type="crunchbase",
            action="enrich",
            report_id=f"enrichment-{keyword_id}",
            payload={
                # Batch endpoint expects 'keywords' as a list
                "keywords": [keyword_text],
                "num_companies": num_companies,
                "days_threshold": self.DAYS_THRESHOLD,
                "enrichment_keyword_id": keyword_id,
            },
            priority=-10,  # Low priority (backend tasks have priority >= 0)
            source="enrichment"
        )
        
        task = await self.task_queue.enqueue(request)
        self._current_enrichment_task_id = task.task_id
        
        logger.info(f"✅ Enrichment task queued: {task.task_id} for '{keyword_text}'")
    
    async def _notify_backend(self, keyword_id: int, action: str, **kwargs):
        """
        Notify Django backend of enrichment status change.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "keyword_id": keyword_id,
                    "action": action,
                    **kwargs
                }
                await client.post(
                    f"{self.BACKEND_URL}/api/admin/enrichment/callback/",
                    json=payload
                )
        except Exception as e:
            logger.warning(f"Failed to notify backend: {e}")
    
    async def on_task_complete(self, task_id: str, result: Dict[str, Any]):
        """
        Called when an enrichment task completes.
        Updates backend with results.
        """
        if not result:
            return
        
        keyword_id = result.get("enrichment_keyword_id")
        if not keyword_id:
            return
        
        # Extract data from batch endpoint response format
        # Batch response: {"results": [...], "summary": {...}}
        summary = result.get("summary", {})
        results = result.get("results", [])
        
        # Count companies from results
        companies_found = summary.get("total_companies_found", 0)
        companies_scraped = sum(r.get("count", 0) for r in results if r.get("status") == "success")
        
        await self._notify_backend(
            keyword_id,
            'complete',
            task_id=task_id,
            companies_found=companies_found,
            companies_scraped=companies_scraped,
            companies_skipped=0  # Batch endpoint doesn't track skipped
        )
        
        if task_id == self._current_enrichment_task_id:
            self._current_enrichment_task_id = None
    
    async def on_task_failed(self, task_id: str, error: str, keyword_id: Optional[int] = None):
        """
        Called when an enrichment task fails.
        Updates backend with error.
        """
        if keyword_id:
            await self._notify_backend(
                keyword_id,
                'error',
                task_id=task_id,
                error_message=error
            )
        
        if task_id == self._current_enrichment_task_id:
            self._current_enrichment_task_id = None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current enrichment manager status."""
        return {
            "is_running": self._is_running,
            "current_task_id": self._current_enrichment_task_id,
        }
