"""
Worker Agent - connects to orchestrator and executes API tasks.
"""
import asyncio
import logging
import json
import signal
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import httpx
import websockets
from websockets.exceptions import ConnectionClosed

import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class WorkerAgent:
    """
    Worker agent that connects to the orchestrator and executes tasks.
    
    Lifecycle:
    1. Connect to orchestrator via WebSocket
    2. Authenticate with token
    3. Wait for task assignment
    4. Execute task by calling local API
    5. Stream status updates to orchestrator
    6. Report completion/failure
    7. Go back to idle, repeat
    """
    
    def __init__(self):
        self.orchestrator_url = config.ORCHESTRATOR_URL
        self.token = config.WORKER_TOKEN
        self.api_type = config.API_TYPE
        self.local_api_url = config.LOCAL_API_URL
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.worker_id: Optional[str] = None
        self.current_task_id: Optional[str] = None
        
        self._running = False
        self._reconnect_attempts = 0
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def start(self):
        """Start the worker agent."""
        logger.info(f"🚀 Starting worker agent ({self.api_type})...")
        logger.info(f"   Orchestrator: {self.orchestrator_url}")
        logger.info(f"   Local API: {self.local_api_url}")
        
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=600.0)  # 10 min timeout for API calls
        
        # Setup signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig, 
                lambda: asyncio.create_task(self.stop())
            )
        
        await self._run_loop()
    
    async def stop(self):
        """Stop the worker agent."""
        logger.info("🛑 Stopping worker agent...")
        self._running = False
        
        if self.websocket:
            await self.websocket.close()
        
        if self._http_client:
            await self._http_client.aclose()
        
        logger.info("✅ Worker agent stopped")
    
    async def _run_loop(self):
        """Main loop with reconnection logic."""
        while self._running:
            try:
                await self._connect_and_run()
            except Exception as e:
                logger.error(f"Connection error: {e}")
            
            if not self._running:
                break
            
            # Reconnect delay
            self._reconnect_attempts += 1
            
            if config.MAX_RECONNECT_ATTEMPTS > 0:
                if self._reconnect_attempts >= config.MAX_RECONNECT_ATTEMPTS:
                    logger.error("Max reconnection attempts reached, giving up")
                    break
            
            delay = min(config.RECONNECT_DELAY * self._reconnect_attempts, 60)
            logger.info(f"⏳ Reconnecting in {delay}s (attempt {self._reconnect_attempts})...")
            await asyncio.sleep(delay)
    
    async def _connect_and_run(self):
        """Connect to orchestrator and run message loop."""
        logger.info(f"🔌 Connecting to {self.orchestrator_url}...")
        
        async with websockets.connect(
            self.orchestrator_url,
            ping_interval=30,
            ping_timeout=10
        ) as websocket:
            self.websocket = websocket
            self._reconnect_attempts = 0
            
            # Authenticate
            if not await self._authenticate():
                return
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            try:
                await self._message_loop()
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
    
    async def _authenticate(self) -> bool:
        """Send auth message and wait for confirmation."""
        auth_message = {
            "type": "auth",
            "api_type": self.api_type,
            "token": self.token,
            "metadata": {
                "name": config.WORKER_NAME,
                "version": config.WORKER_VERSION,
                "local_api_url": self.local_api_url
            }
        }
        
        await self.websocket.send(json.dumps(auth_message))
        
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("type") == "auth_success":
            self.worker_id = data.get("worker_id")
            logger.info(f"✅ Authenticated as {self.worker_id}")
            return True
        else:
            error = data.get("error", "Unknown error")
            logger.error(f"❌ Authentication failed: {error}")
            return False
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to orchestrator."""
        while True:
            try:
                await asyncio.sleep(config.HEARTBEAT_INTERVAL)
                await self.websocket.send(json.dumps({"type": "heartbeat"}))
                logger.debug("💓 Heartbeat sent")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break
    
    async def _message_loop(self):
        """Listen for messages from orchestrator."""
        async for message in self.websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "heartbeat_ack":
                    logger.debug("💓 Heartbeat acknowledged")
                    
                elif msg_type == "task":
                    # Received a task to execute
                    await self._handle_task(data)
                    
                elif msg_type == "cancel":
                    # Task cancellation request
                    task_id = data.get("task_id")
                    if task_id == self.current_task_id:
                        logger.info(f"🚫 Task {task_id} cancelled")
                        # TODO: Implement cancellation logic
                        
                else:
                    logger.debug(f"Received: {msg_type}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Message handling error: {e}")
    
    async def _handle_task(self, data: dict):
        """
        Handle an incoming task from orchestrator.
        """
        task_id = data.get("task_id")
        report_id = data.get("report_id")
        action = data.get("action")
        payload = data.get("payload", {})
        
        logger.info(f"📥 Received task: {task_id} ({action})")
        self.current_task_id = task_id
        
        # Notify orchestrator we're starting
        await self._send({
            "type": "running",
            "task_id": task_id
        })
        
        try:
            # Execute the task
            result = await self._execute_task(action, payload, report_id, task_id)
            
            # Report success
            await self._send({
                "type": "complete",
                "task_id": task_id,
                "result": result
            })
            logger.info(f"✅ Task {task_id} completed")
            
        except Exception as e:
            # Report failure
            error_msg = str(e)
            logger.error(f"❌ Task {task_id} failed: {error_msg}")
            await self._send({
                "type": "error",
                "task_id": task_id,
                "error": error_msg
            })
        finally:
            self.current_task_id = None
    
    async def _execute_task(
        self, 
        action: str, 
        payload: dict, 
        report_id: str,
        task_id: str
    ) -> dict:
        """
        Execute a task by calling the local API.
        
        The local API is the existing Crunchbase/Tracxn scraper.
        We wrap the call and intercept status updates.
        """
        # Build the API endpoint based on action
        endpoint = self._get_endpoint(action)
        url = f"{self.local_api_url}{endpoint}"
        
        logger.info(f"📡 Calling local API: {url}")
        
        # Add our callback URL for status updates
        # We'll use a special header to route updates through the agent
        # Note: The existing APIs send updates directly, but we need to intercept
        # For now, we'll modify the payload to include our report_id
        modified_payload = {**payload, "report_id": report_id}
        
        # Make the API call
        response = await self._http_client.post(
            url,
            json=modified_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            error_detail = response.text[:500]
            raise Exception(f"API returned {response.status_code}: {error_detail}")
        
        return response.json()
    
    def _get_endpoint(self, action: str) -> str:
        """Get the local API endpoint for an action."""
        # Map action names to API endpoints
        endpoints = {
            # Crunchbase endpoints
            "search_with_rank": "/search/crunchbase/top-similar-with-rank",
            "search_similar": "/search/crunchbase/top-similar",
            "search_batch": "/search/crunchbase/batch",
            
            # Tracxn endpoints
            "tracxn_search_with_rank": "/scrape-batch-api-with-rank",
            "tracxn_search": "/scrape-batch-api",
            
            # Generic
            "health": "/health",
        }
        
        return endpoints.get(action, f"/{action}")
    
    async def _send(self, message: dict):
        """Send a message to the orchestrator."""
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def send_status(
        self,
        step_key: str,
        detail_type: str,
        message: str,
        data: dict = None
    ):
        """
        Send a status update to orchestrator.
        
        This can be called during task execution to report progress.
        """
        if not self.current_task_id:
            return
        
        await self._send({
            "type": "status",
            "task_id": self.current_task_id,
            "step_key": step_key,
            "detail_type": detail_type,
            "message": message,
            "data": data or {}
        })


async def main():
    """Entry point for worker agent."""
    agent = WorkerAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
