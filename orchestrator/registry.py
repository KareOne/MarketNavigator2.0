"""
Worker Registry - manages connected workers and their states.
Uses Redis for persistent state that survives restarts.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import json

from fastapi import WebSocket

from models import Worker, WorkerStats
import config

logger = logging.getLogger(__name__)


class WorkerRegistry:
    """
    Manages connected workers and their states.
    
    Responsibilities:
    - Track connected workers with WebSocket connections
    - Persist worker state to Redis for durability
    - Monitor heartbeats and mark offline workers
    - Provide idle worker selection for task assignment
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.workers: Dict[str, Worker] = {}  # worker_id -> Worker
        self.connections: Dict[str, WebSocket] = {}  # worker_id -> WebSocket
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the worker registry background tasks."""
        self._cleanup_task = asyncio.create_task(self._heartbeat_monitor())
        logger.info("Worker registry started")
    
    async def stop(self):
        """Stop the worker registry and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Mark all workers as offline
        for worker_id in list(self.workers.keys()):
            await self.unregister(worker_id)
        
        logger.info("Worker registry stopped")
    
    async def register(
        self, 
        worker_id: str, 
        api_type: str, 
        token: str, 
        websocket: WebSocket,
        metadata: Dict = None
    ) -> bool:
        """
        Register a new worker connection.
        
        Args:
            worker_id: Unique worker identifier
            api_type: Type of API (crunchbase, tracxn, etc.)
            token: Authentication token
            websocket: WebSocket connection
            metadata: Optional worker metadata
            
        Returns:
            True if registration successful, False if auth failed
        """
        # Validate token
        valid_tokens = config.WORKER_TOKENS.get(api_type, [])
        if token not in valid_tokens:
            logger.warning(f"Invalid token for worker {worker_id} ({api_type})")
            return False
        
        # Create worker record
        worker = Worker(
            worker_id=worker_id,
            api_type=api_type,
            status="idle",
            metadata=metadata or {},
            connected_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        # Store in memory and Redis
        self.workers[worker_id] = worker
        self.connections[worker_id] = websocket
        await self._persist_worker(worker)
        
        logger.info(f"✅ Worker registered: {worker_id} ({api_type})")
        return True
    
    async def unregister(self, worker_id: str):
        """Remove a worker from the registry."""
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            worker.status = "offline"
            await self._persist_worker(worker)
            
            del self.workers[worker_id]
            if worker_id in self.connections:
                del self.connections[worker_id]
            
            # Remove from Redis
            await self.redis.delete(f"worker:{worker_id}")
            await self.redis.srem(f"workers:{worker.api_type}", worker_id)
            
            logger.info(f"🔌 Worker unregistered: {worker_id}")
    
    async def update_heartbeat(self, worker_id: str):
        """Update the last heartbeat time for a worker."""
        if worker_id in self.workers:
            self.workers[worker_id].last_heartbeat = datetime.utcnow()
            await self._persist_worker(self.workers[worker_id])
    
    async def set_status(
        self, 
        worker_id: str, 
        status: str, 
        task_id: Optional[str] = None
    ):
        """Update worker status and optionally current task."""
        if worker_id in self.workers:
            self.workers[worker_id].status = status
            self.workers[worker_id].current_task_id = task_id
            await self._persist_worker(self.workers[worker_id])
            logger.debug(f"Worker {worker_id} status: {status}, task: {task_id}")
    
    def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Get a worker by ID."""
        return self.workers.get(worker_id)
    
    def get_connection(self, worker_id: str) -> Optional[WebSocket]:
        """Get WebSocket connection for a worker."""
        return self.connections.get(worker_id)
    
    def get_idle_workers(self, api_type: str) -> List[Worker]:
        """Get all idle workers for a specific API type."""
        return [
            w for w in self.workers.values()
            if w.api_type == api_type and w.status == "idle"
        ]
    
    def get_workers_by_type(self, api_type: str) -> List[Worker]:
        """Get all workers for a specific API type."""
        return [w for w in self.workers.values() if w.api_type == api_type]
    
    def get_all_workers(self) -> List[Worker]:
        """Get all connected workers."""
        return list(self.workers.values())
    
    def get_worker_stats(self, api_type: Optional[str] = None) -> Dict[str, WorkerStats]:
        """
        Get worker statistics, optionally filtered by API type.
        
        Returns dict: {api_type: WorkerStats}
        """
        stats: Dict[str, WorkerStats] = {}
        
        for worker in self.workers.values():
            if api_type and worker.api_type != api_type:
                continue
            
            if worker.api_type not in stats:
                stats[worker.api_type] = WorkerStats(api_type=worker.api_type)
            
            s = stats[worker.api_type]
            s.total += 1
            if worker.status == "idle":
                s.idle += 1
            elif worker.status == "working":
                s.working += 1
            elif worker.status == "offline":
                s.offline += 1
        
        return stats
    
    async def broadcast_to_type(self, api_type: str, message: dict):
        """Broadcast a message to all workers of a specific type."""
        for worker in self.get_workers_by_type(api_type):
            ws = self.connections.get(worker.worker_id)
            if ws:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {worker.worker_id}: {e}")
    
    # =========================================================================
    # Private methods
    # =========================================================================
    
    async def _persist_worker(self, worker: Worker):
        """Persist worker state to Redis."""
        key = f"worker:{worker.worker_id}"
        await self.redis.set(key, worker.model_dump_json(), ex=config.WORKER_TIMEOUT * 2)
        await self.redis.sadd(f"workers:{worker.api_type}", worker.worker_id)
    
    async def _heartbeat_monitor(self):
        """Background task to monitor worker heartbeats and mark offline."""
        while True:
            try:
                await asyncio.sleep(config.WORKER_HEARTBEAT_INTERVAL)
                
                now = datetime.utcnow()
                idle_timeout = timedelta(seconds=config.WORKER_TIMEOUT)
                # Working workers send heartbeats too (via separate task)
                # Use slightly longer timeout than idle to be safe, but not 4 hours
                working_timeout = timedelta(seconds=config.WORKER_TIMEOUT * 3)  # ~15 mins with 5 min base
                
                for worker_id, worker in list(self.workers.items()):
                    time_since_heartbeat = now - worker.last_heartbeat
                    
                    # Use different timeouts based on worker status
                    if worker.status == "working" or worker.current_task_id:
                        # Worker is executing a task - use long timeout
                        if time_since_heartbeat > working_timeout:
                            logger.warning(f"⚠️ Working worker {worker_id} timed out after {time_since_heartbeat.seconds}s, marking offline")
                            await self.unregister(worker_id)
                        elif time_since_heartbeat > idle_timeout:
                            logger.debug(f"Worker {worker_id} heartbeat delayed ({time_since_heartbeat.seconds}s) but working on task, keeping alive")
                    else:
                        # Idle worker - use normal timeout
                        if time_since_heartbeat > idle_timeout:
                            logger.warning(f"⚠️ Idle worker {worker_id} timed out, marking offline")
                            await self.unregister(worker_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")

