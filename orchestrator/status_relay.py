"""
Status Relay - forwards status updates from workers to Django backend.
"""
import asyncio
import logging
from typing import List
import httpx

from models import StatusUpdate
import config

logger = logging.getLogger(__name__)


class StatusRelay:
    """
    Relays status updates from workers to the Django backend.
    
    Uses fire-and-forget pattern to avoid blocking worker communication.
    Batches updates when possible for efficiency.
    """
    
    def __init__(self, backend_url: str = None):
        self.backend_url = backend_url or config.BACKEND_STATUS_URL
        self._client: httpx.AsyncClient = None
        self._pending_updates: List[StatusUpdate] = []
        self._batch_task: asyncio.Task = None
        self._lock = asyncio.Lock()
    
    async def start(self):
        """Start the status relay."""
        self._client = httpx.AsyncClient(timeout=10.0)
        self._batch_task = asyncio.create_task(self._batch_sender())
        logger.info(f"Status relay started, forwarding to {self.backend_url}")
    
    async def stop(self):
        """Stop the status relay."""
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining updates
        if self._pending_updates:
            await self._flush()
        
        if self._client:
            await self._client.aclose()
        
        logger.info("Status relay stopped")
    
    async def relay(self, update: StatusUpdate):
        """
        Queue a status update for relay to backend.
        
        Uses async batching to reduce HTTP overhead.
        """
        async with self._lock:
            self._pending_updates.append(update)
        
        # If we have multiple updates queued, let batch sender handle them
        # But if this is the first, send immediately
        if len(self._pending_updates) == 1:
            await self._flush()
    
    async def relay_immediate(self, update: StatusUpdate):
        """Immediately relay a status update (bypass batching)."""
        await self._send_update(update)
    
    async def _flush(self):
        """Flush all pending updates to backend."""
        async with self._lock:
            updates = self._pending_updates.copy()
            self._pending_updates.clear()
        
        for update in updates:
            await self._send_update(update)
    
    async def _send_update(self, update: StatusUpdate):
        """Send a single status update to backend."""
        try:
            payload = {
                "report_id": update.report_id,
                "step_key": update.step_key,
                "detail_type": update.detail_type,
                "message": update.message,
                "data": update.data
            }
            
            response = await self._client.post(
                self.backend_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.warning(
                    f"⚠️ Backend returned {response.status_code} for status update: "
                    f"{response.text[:100]}"
                )
            else:
                logger.debug(f"📡 Status relayed: {update.step_key}/{update.detail_type}")
                
        except Exception as e:
            logger.error(f"❌ Failed to relay status update: {e}")
    
    async def _batch_sender(self):
        """Background task to batch and send pending updates."""
        while True:
            try:
                await asyncio.sleep(0.1)  # 100ms batching window
                
                if self._pending_updates:
                    await self._flush()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch sender error: {e}")
