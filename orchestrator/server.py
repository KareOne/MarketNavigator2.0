"""
Orchestrator Server - FastAPI application with HTTP API and WebSocket support.
"""
import asyncio
import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

import config
from models import (
    Task, TaskSubmitRequest, TaskResponse, 
    Worker, WorkerStats, WorkerListResponse, QueueStatsResponse,
    StatusUpdate, WSAuthMessage, WSStatusMessage, WSCompleteMessage, WSErrorMessage
)
from registry import WorkerRegistry
from task_queue import TaskQueue
from status_relay import StatusRelay
from enrichment_manager import EnrichmentManager

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
redis_client: redis.Redis = None
registry: WorkerRegistry = None
task_queue: TaskQueue = None
status_relay: StatusRelay = None
enrichment_manager: EnrichmentManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_client, registry, task_queue, status_relay, enrichment_manager
    
    # Startup
    logger.info("🚀 Starting API Orchestrator...")
    
    # Connect to Redis
    redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)
    await redis_client.ping()
    logger.info(f"✅ Connected to Redis: {config.REDIS_URL}")
    
    # Initialize components
    registry = WorkerRegistry(redis_client)
    await registry.start()
    
    task_queue = TaskQueue(redis_client, registry)
    await task_queue.start()
    
    status_relay = StatusRelay(config.BACKEND_STATUS_URL)
    await status_relay.start()
    
    enrichment_manager = EnrichmentManager(redis_client, registry, task_queue)
    await enrichment_manager.start()
    
    logger.info(f"✅ Orchestrator ready on port {config.ORCHESTRATOR_PORT}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down API Orchestrator...")
    await enrichment_manager.stop()
    await status_relay.stop()
    await task_queue.stop()
    await registry.stop()
    await redis_client.close()
    logger.info("✅ Orchestrator shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="API Orchestrator",
    description="Distributed API task orchestration service for MarketNavigator",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HTTP Endpoints (for backend/admin)
# =============================================================================

@app.get("/health")
async def health_check():
    """Orchestrator health check."""
    try:
        await redis_client.ping()
        redis_ok = True
    except:
        redis_ok = False
    
    stats = registry.get_worker_stats() if registry else {}
    total_workers = sum(s.total for s in stats.values())
    
    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "workers_connected": total_workers,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/tasks/submit", response_model=TaskResponse)
async def submit_task(request: TaskSubmitRequest):
    """
    Submit a new task for execution by a worker.
    
    The task will be queued and assigned to an available worker
    of the specified API type.
    """
    # Check if we have any workers for this API type
    workers = registry.get_workers_by_type(request.api_type)
    
    if not workers:
        logger.warning(f"⚠️ No workers available for {request.api_type}")
        # Still enqueue - workers might connect later
    
    task = await task_queue.enqueue(request)
    
    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        message=f"Task queued for {request.api_type}"
    )


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """Get task status and result."""
    task = await task_queue.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        message=f"Task {task.status}",
        result=task.result,
        error=task.error
    )


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or assigned task."""
    success = await task_queue.cancel_task(task_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Task not found or cannot be cancelled (already running/completed)"
        )
    
    return {"status": "cancelled", "task_id": task_id}


@app.get("/workers", response_model=WorkerListResponse)
async def list_workers():
    """List all connected workers and their status."""
    workers = registry.get_all_workers()
    stats = registry.get_worker_stats()
    
    return WorkerListResponse(workers=workers, stats=stats)


@app.get("/workers/{api_type}/stats")
async def get_worker_stats(api_type: str):
    """Get worker statistics for an API type."""
    stats = registry.get_worker_stats(api_type)
    
    if api_type not in stats:
        return WorkerStats(api_type=api_type)
    
    return stats[api_type]


@app.get("/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """Get task queue statistics."""
    stats = await task_queue.get_queue_stats()
    
    pending = {}
    total_workers = {}
    idle_workers = {}
    
    for api_type, s in stats.items():
        pending[api_type] = s["pending"]
        total_workers[api_type] = s["total_workers"]
        idle_workers[api_type] = s["idle_workers"]
    
    return QueueStatsResponse(
        pending=pending,
        assigned={},  # Could track this separately
        running={},
        total_workers=total_workers,
        idle_workers=idle_workers
    )


# =============================================================================
# WebSocket Endpoint (for workers)
# =============================================================================

@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for remote workers.
    
    Connection flow:
    1. Worker connects
    2. Worker sends auth message: {"type": "auth", "api_type": "crunchbase", "token": "..."}
    3. Orchestrator validates token and registers worker
    4. Worker sends heartbeats: {"type": "heartbeat"}
    5. Orchestrator sends tasks: {"type": "task", ...}
    6. Worker sends status updates: {"type": "status", ...}
    7. Worker sends completion: {"type": "complete", ...}
    """
    await websocket.accept()
    
    worker_id = str(uuid.uuid4())
    authenticated = False
    worker_api_type = None
    
    logger.info(f"🔌 New WebSocket connection: {worker_id}")
    
    try:
        # Wait for authentication (timeout: 30 seconds)
        try:
            auth_data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            await websocket.send_json({
                "type": "error",
                "error": "Authentication timeout"
            })
            await websocket.close(code=4001)
            return
        
        # Validate auth message
        if auth_data.get("type") != "auth":
            await websocket.send_json({
                "type": "error",
                "error": "First message must be auth"
            })
            await websocket.close(code=4002)
            return
        
        api_type = auth_data.get("api_type")
        token = auth_data.get("token")
        metadata = auth_data.get("metadata", {})
        
        # Register worker
        success = await registry.register(
            worker_id=worker_id,
            api_type=api_type,
            token=token,
            websocket=websocket,
            metadata=metadata
        )
        
        if not success:
            await websocket.send_json({
                "type": "error",
                "error": "Authentication failed - invalid token"
            })
            await websocket.close(code=4003)
            return
        
        authenticated = True
        worker_api_type = api_type
        
        # Send success response
        await websocket.send_json({
            "type": "auth_success",
            "worker_id": worker_id,
            "message": f"Registered as {api_type} worker"
        })
        
        logger.info(f"✅ Worker {worker_id} authenticated as {api_type}")
        
        # Signal task queue to check for pending tasks
        task_queue._assignment_event.set()
        
        # Server-side ping task to keep connection alive during long tasks
        async def server_ping_loop():
            """Send periodic ping messages to keep connection alive."""
            ping_interval = 30  # seconds
            while True:
                try:
                    await asyncio.sleep(ping_interval)
                    await websocket.send_json({"type": "ping"})
                    logger.debug(f"📡 Sent ping to {worker_id}")
                except Exception as e:
                    logger.debug(f"Ping failed for {worker_id}: {e}")
                    break
        
        # Start ping task in background
        ping_task = asyncio.create_task(server_ping_loop())
        
        try:
            # Main message loop
            while True:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                
                if msg_type == "heartbeat":
                    await registry.update_heartbeat(worker_id)
                    # Send acknowledgement with worker status so worker can confirm it's recognized
                    worker = registry.get_worker(worker_id)
                    await websocket.send_json({
                        "type": "heartbeat_ack",
                        "worker_id": worker_id,
                        "status": worker.status if worker else "unknown",
                        "current_task": worker.current_task_id if worker else None
                    })
                
                elif msg_type == "pong":
                    # Response to server ping - connection alive
                    logger.debug(f"📡 Received pong from {worker_id}")
                    
                elif msg_type == "status":
                    # Worker sending status update during task execution
                    task_id = message.get("task_id")
                    task = await task_queue.get_task(task_id)
                    
                    if task:
                        # Forward to backend via status relay
                        update = StatusUpdate(
                            task_id=task_id,
                            report_id=task.report_id,
                            step_key=message.get("step_key", ""),
                            detail_type=message.get("detail_type", "status"),
                            message=message.get("message", ""),
                            data=message.get("data", {})
                        )
                        await status_relay.relay(update)
                        
                elif msg_type == "running":
                    # Worker started executing task
                    task_id = message.get("task_id")
                    await task_queue.mark_running(task_id)
                    
                elif msg_type == "complete":
                    # Worker completed task
                    task_id = message.get("task_id")
                    result = message.get("result", {})
                    task = await task_queue.get_task(task_id)
                    await task_queue.mark_completed(task_id, result)
                    
                    # Notify enrichment manager if this was an enrichment task
                    if task and task.source == "enrichment":
                        # Merge enrichment_keyword_id from original payload into result
                        enrichment_result = {
                            **result,
                            "enrichment_keyword_id": task.payload.get("enrichment_keyword_id")
                        }
                        await enrichment_manager.on_task_complete(task_id, enrichment_result)
                    
                    # Signal for next task
                    task_queue._assignment_event.set()
                    
                elif msg_type == "error":
                    # Worker encountered error
                    task_id = message.get("task_id")
                    error = message.get("error", "Unknown error")
                    if task_id:
                        task = await task_queue.get_task(task_id)
                        await task_queue.mark_failed(task_id, error)
                        
                        # Notify enrichment manager if this was an enrichment task
                        if task and task.source == "enrichment":
                            keyword_id = task.payload.get("enrichment_keyword_id")
                            await enrichment_manager.on_task_failed(task_id, error, keyword_id)
                    logger.error(f"Worker {worker_id} error: {error}")
                    
                else:
                    logger.warning(f"Unknown message type from {worker_id}: {msg_type}")
        finally:
            # Cancel ping task when message loop exits
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Worker {worker_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {worker_id}: {e}")
    finally:
        # Cleanup worker registration
        if authenticated:
            # Check if worker had an active task
            worker = registry.get_worker(worker_id)
            if worker and worker.current_task_id:
                await task_queue.mark_failed(
                    worker.current_task_id,
                    "Worker disconnected during task execution"
                )
            
            await registry.unregister(worker_id)


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "orchestrator.server:app",
        host=config.ORCHESTRATOR_HOST,
        port=config.ORCHESTRATOR_PORT,
        reload=True
    )
