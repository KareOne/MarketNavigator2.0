"""
Orchestrator Client - client for submitting tasks to the API orchestrator.
Used by backend to interact with the orchestration service.
"""
import logging
from typing import Optional, Dict, Any
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OrchestratorClient:
    """
    Client for the API Orchestrator service.
    
    Provides methods to submit tasks, check status, and manage workers.
    Falls back to direct API calls if orchestrator is not available.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'ORCHESTRATOR_URL', 'http://orchestrator:8010')
        self.enabled = getattr(settings, 'USE_ORCHESTRATOR', False)
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def is_available(self) -> bool:
        """Check if orchestrator is available."""
        if not self.enabled:
            return False
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Orchestrator not available: {e}")
            return False
    
    async def submit_task(
        self,
        api_type: str,
        action: str,
        report_id: str,
        payload: Dict[str, Any],
        priority: int = 0
    ) -> Optional[str]:
        """
        Submit a task to the orchestrator for execution.
        
        Args:
            api_type: Type of API (crunchbase, tracxn, social)
            action: The action to perform (e.g., search_with_rank)
            report_id: Report ID for status tracking
            payload: Task payload/parameters
            priority: Task priority (higher = more priority)
            
        Returns:
            Task ID if submitted successfully, None otherwise
        """
        try:
            request_data = {
                "api_type": api_type,
                "action": action,
                "report_id": report_id,
                "payload": payload,
                "priority": priority
            }
            
            response = await self.client.post(
                f"{self.base_url}/tasks/submit",
                json=request_data
            )
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                logger.info(f"📤 Task submitted to orchestrator: {task_id}")
                return task_id
            else:
                logger.error(f"Orchestrator returned {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to submit task to orchestrator: {e}")
            return None
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.
        
        Returns:
            Task status dict or None if not found
        """
        try:
            response = await self.client.get(f"{self.base_url}/tasks/{task_id}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                logger.error(f"Orchestrator returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return None
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout: float = 600.0,
        poll_interval: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a task to complete.
        
        Args:
            task_id: Task ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks
            
        Returns:
            Task result if completed, None if timed out or failed
        """
        import asyncio
        
        elapsed = 0.0
        while elapsed < timeout:
            status = await self.get_task_status(task_id)
            
            if status is None:
                return None
            
            task_status = status.get("status")
            
            if task_status == "completed":
                return status.get("result")
            elif task_status in ("failed", "cancelled"):
                logger.error(f"Task {task_id} {task_status}: {status.get('error')}")
                return None
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        logger.error(f"Task {task_id} timed out after {timeout}s")
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or assigned task.
        
        Returns:
            True if cancelled, False otherwise
        """
        try:
            response = await self.client.delete(f"{self.base_url}/tasks/{task_id}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to cancel task: {e}")
            return False
    
    async def get_worker_stats(self, api_type: str = None) -> Dict[str, Any]:
        """
        Get worker statistics.
        
        Args:
            api_type: Optional API type to filter by
            
        Returns:
            Worker statistics dict
        """
        try:
            if api_type:
                url = f"{self.base_url}/workers/{api_type}/stats"
            else:
                url = f"{self.base_url}/workers"
            
            response = await self.client.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {}
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get task queue statistics."""
        try:
            response = await self.client.get(f"{self.base_url}/queue/stats")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}


# Singleton instance
orchestrator_client = OrchestratorClient()
