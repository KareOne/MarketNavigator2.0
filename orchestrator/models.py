"""
Pydantic models for orchestrator data structures.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field
import uuid


# ============================================================================
# Worker Models
# ============================================================================

class Worker(BaseModel):
    """Represents a connected remote worker."""
    worker_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_type: str  # crunchbase, tracxn, social, etc.
    status: Literal["idle", "working", "offline"] = "idle"
    current_task_id: Optional[str] = None
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkerStats(BaseModel):
    """Statistics for workers of a specific API type."""
    api_type: str
    total: int = 0
    idle: int = 0
    working: int = 0
    offline: int = 0


# ============================================================================
# Task Models
# ============================================================================

class Task(BaseModel):
    """Represents a task to be executed by a worker."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str
    api_type: str
    action: str = "search_with_rank"  # The API action to perform
    status: Literal["pending", "assigned", "running", "completed", "failed", "cancelled"] = "pending"
    payload: Dict[str, Any] = Field(default_factory=dict)
    assigned_worker_id: Optional[str] = None
    target_worker_id: Optional[str] = None  # Preferred worker to route to
    priority: int = 0  # Higher = more priority
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskSubmitRequest(BaseModel):
    """Request to submit a new task."""
    api_type: str
    action: str = "search_with_rank"
    report_id: str
    payload: Dict[str, Any]
    priority: int = 0
    target_worker_id: Optional[str] = None  # Route to specific worker by ID


class TaskResponse(BaseModel):
    """Response for task operations."""
    task_id: str
    status: str
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# Status Update Models
# ============================================================================

class StatusUpdate(BaseModel):
    """Status update from a worker during task execution."""
    task_id: str
    report_id: str
    step_key: str
    detail_type: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# WebSocket Message Models
# ============================================================================

class WSMessage(BaseModel):
    """Base WebSocket message structure."""
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)


class WSAuthMessage(BaseModel):
    """Authentication message from worker."""
    type: Literal["auth"] = "auth"
    api_type: str
    token: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WSHeartbeatMessage(BaseModel):
    """Heartbeat message from worker."""
    type: Literal["heartbeat"] = "heartbeat"


class WSTaskMessage(BaseModel):
    """Task assignment message to worker."""
    type: Literal["task"] = "task"
    task_id: str
    report_id: str
    action: str
    payload: Dict[str, Any]


class WSStatusMessage(BaseModel):
    """Status update message from worker."""
    type: Literal["status"] = "status"
    task_id: str
    step_key: str
    detail_type: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class WSCompleteMessage(BaseModel):
    """Task completion message from worker."""
    type: Literal["complete"] = "complete"
    task_id: str
    result: Dict[str, Any]


class WSErrorMessage(BaseModel):
    """Error message from worker."""
    type: Literal["error"] = "error"
    task_id: Optional[str] = None
    error: str
    details: Optional[str] = None


# ============================================================================
# API Response Models
# ============================================================================

class WorkerListResponse(BaseModel):
    """Response for worker list endpoint."""
    workers: List[Worker]
    stats: Dict[str, WorkerStats]


class QueueStatsResponse(BaseModel):
    """Response for queue statistics endpoint."""
    pending: Dict[str, int]  # api_type -> count
    assigned: Dict[str, int]
    running: Dict[str, int]
    total_workers: Dict[str, int]
    idle_workers: Dict[str, int]
