"""
Task Queue - manages task distribution to workers.
Uses Redis for persistence and priority-based queuing.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
import uuid

from .models import Task, TaskSubmitRequest
from .registry import WorkerRegistry
from . import config

logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Priority queue with load-balanced task assignment.
    
    Responsibilities:
    - Maintain pending task queue per API type
    - Assign tasks to idle workers (round-robin within type)
    - Track task status and results
    - Handle task retries for failures
    """
    
    # Redis key prefixes
    QUEUE_KEY = "task_queue"  # Sorted set: priority -> task_id
    TASK_KEY = "task"  # Hash: task_id -> task_json
    
    def __init__(self, redis_client, registry: WorkerRegistry):
        self.redis = redis_client
        self.registry = registry
        self._assignment_task: Optional[asyncio.Task] = None
        self._assignment_event = asyncio.Event()
    
    async def start(self):
        """Start the task queue background assignment loop."""
        self._assignment_task = asyncio.create_task(self._assignment_loop())
        logger.info("Task queue started")
    
    async def stop(self):
        """Stop the task queue."""
        if self._assignment_task:
            self._assignment_task.cancel()
            try:
                await self._assignment_task
            except asyncio.CancelledError:
                pass
        logger.info("Task queue stopped")
    
    async def enqueue(self, request: TaskSubmitRequest) -> Task:
        """
        Add a new task to the queue.
        
        Args:
            request: Task submission request
            
        Returns:
            Created Task object
        """
        task = Task(
            task_id=str(uuid.uuid4()),
            report_id=request.report_id,
            api_type=request.api_type,
            action=request.action,
            payload=request.payload,
            priority=request.priority,
            max_retries=config.TASK_RETRY_LIMIT,
            created_at=datetime.utcnow()
        )
        
        # Store task data
        await self._store_task(task)
        
        # Add to priority queue (negated priority for descending order)
        queue_key = f"{self.QUEUE_KEY}:{task.api_type}"
        await self.redis.zadd(queue_key, {task.task_id: -task.priority})
        
        logger.info(f"📥 Task enqueued: {task.task_id} ({task.api_type}/{task.action})")
        
        # Signal assignment loop
        self._assignment_event.set()
        
        return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        task_json = await self.redis.get(f"{self.TASK_KEY}:{task_id}")
        if task_json:
            return Task.model_validate_json(task_json)
        return None
    
    async def assign_next(self, api_type: str) -> Optional[Tuple[Task, str]]:
        """
        Assign the next pending task to an idle worker.
        
        Returns:
            Tuple of (Task, worker_id) if assignment made, else None
        """
        # Get idle workers
        idle_workers = self.registry.get_idle_workers(api_type)
        if not idle_workers:
            return None
        
        # Get next task from queue (highest priority = lowest score)
        queue_key = f"{self.QUEUE_KEY}:{api_type}"
        result = await self.redis.zpopmin(queue_key, count=1)
        
        if not result:
            return None
        
        task_id = result[0][0] if isinstance(result[0], tuple) else result[0]
        task = await self.get_task(task_id)
        
        if not task:
            logger.warning(f"Task {task_id} not found in store")
            return None
        
        # Select worker (simple round-robin - just pick first idle)
        worker = idle_workers[0]
        
        # Update task
        task.status = "assigned"
        task.assigned_worker_id = worker.worker_id
        task.assigned_at = datetime.utcnow()
        await self._store_task(task)
        
        # Update worker status
        await self.registry.set_status(worker.worker_id, "working", task.task_id)
        
        logger.info(f"📤 Task {task_id} assigned to worker {worker.worker_id}")
        
        return task, worker.worker_id
    
    async def mark_running(self, task_id: str):
        """Mark a task as running (worker started execution)."""
        task = await self.get_task(task_id)
        if task:
            task.status = "running"
            task.started_at = datetime.utcnow()
            await self._store_task(task)
            logger.debug(f"Task {task_id} marked as running")
    
    async def mark_completed(self, task_id: str, result: dict):
        """Mark a task as completed with result."""
        task = await self.get_task(task_id)
        if task:
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.utcnow()
            await self._store_task(task)
            
            # Release worker
            if task.assigned_worker_id:
                await self.registry.set_status(task.assigned_worker_id, "idle", None)
            
            logger.info(f"✅ Task {task_id} completed")
    
    async def mark_failed(self, task_id: str, error: str):
        """
        Mark a task as failed. May retry if within limits.
        
        Args:
            task_id: Task ID
            error: Error message
        """
        task = await self.get_task(task_id)
        if not task:
            return
        
        task.retry_count += 1
        task.error = error
        
        # Release worker first
        if task.assigned_worker_id:
            await self.registry.set_status(task.assigned_worker_id, "idle", None)
            task.assigned_worker_id = None
        
        if task.retry_count < task.max_retries:
            # Re-queue for retry
            task.status = "pending"
            task.assigned_at = None
            task.started_at = None
            await self._store_task(task)
            
            # Add back to queue with same priority
            queue_key = f"{self.QUEUE_KEY}:{task.api_type}"
            await self.redis.zadd(queue_key, {task.task_id: -task.priority})
            
            logger.warning(f"⟳ Task {task_id} failed, retrying ({task.retry_count}/{task.max_retries})")
            self._assignment_event.set()
        else:
            # Max retries exceeded
            task.status = "failed"
            task.completed_at = datetime.utcnow()
            await self._store_task(task)
            logger.error(f"❌ Task {task_id} failed permanently: {error}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or assigned task.
        
        Returns:
            True if cancelled, False if not found or already running
        """
        task = await self.get_task(task_id)
        if not task:
            return False
        
        if task.status in ("running", "completed", "failed"):
            return False
        
        # Remove from queue
        queue_key = f"{self.QUEUE_KEY}:{task.api_type}"
        await self.redis.zrem(queue_key, task_id)
        
        # Update task status
        task.status = "cancelled"
        task.completed_at = datetime.utcnow()
        await self._store_task(task)
        
        # Release worker if assigned
        if task.assigned_worker_id:
            await self.registry.set_status(task.assigned_worker_id, "idle", None)
        
        logger.info(f"🚫 Task {task_id} cancelled")
        return True
    
    async def get_queue_stats(self) -> Dict[str, Dict[str, int]]:
        """Get queue statistics by API type."""
        stats = {}
        api_types = ["crunchbase", "tracxn", "social"]
        
        for api_type in api_types:
            queue_key = f"{self.QUEUE_KEY}:{api_type}"
            pending_count = await self.redis.zcard(queue_key)
            
            worker_stats = self.registry.get_worker_stats(api_type)
            ws = worker_stats.get(api_type)
            
            stats[api_type] = {
                "pending": pending_count,
                "total_workers": ws.total if ws else 0,
                "idle_workers": ws.idle if ws else 0,
                "working_workers": ws.working if ws else 0,
            }
        
        return stats
    
    # =========================================================================
    # Private methods
    # =========================================================================
    
    async def _store_task(self, task: Task):
        """Store task in Redis."""
        key = f"{self.TASK_KEY}:{task.task_id}"
        # Keep completed tasks for 1 hour for result retrieval
        ttl = 3600 if task.status in ("completed", "failed", "cancelled") else config.TASK_TIMEOUT * 2
        await self.redis.set(key, task.model_dump_json(), ex=ttl)
    
    async def _assignment_loop(self):
        """
        Background loop that assigns pending tasks to idle workers.
        """
        api_types = ["crunchbase", "tracxn", "social"]
        
        while True:
            try:
                # Wait for signal or timeout
                try:
                    await asyncio.wait_for(
                        self._assignment_event.wait(),
                        timeout=5.0  # Check every 5 seconds anyway
                    )
                except asyncio.TimeoutError:
                    pass
                
                self._assignment_event.clear()
                
                # Try to assign tasks for each API type
                for api_type in api_types:
                    while True:
                        result = await self.assign_next(api_type)
                        if not result:
                            break
                        
                        # Send task to worker
                        task, worker_id = result
                        ws = self.registry.get_connection(worker_id)
                        if ws:
                            try:
                                await ws.send_json({
                                    "type": "task",
                                    "task_id": task.task_id,
                                    "report_id": task.report_id,
                                    "action": task.action,
                                    "payload": task.payload
                                })
                            except Exception as e:
                                logger.error(f"Failed to send task to worker: {e}")
                                await self.mark_failed(task.task_id, f"Failed to send task: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Assignment loop error: {e}")
                await asyncio.sleep(1)
