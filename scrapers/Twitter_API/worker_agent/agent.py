"""
Worker Agent - Robust connection to orchestrator with task execution.

Key reliability features:
- No ping timeout during task execution (disables WebSocket keepalive during API calls)
- Tracks task state to prevent duplicate execution
- Graceful reconnection without task restart
- Resilient status updates that don't crash on connection loss
"""
import asyncio
import logging
import json
import signal
from datetime import datetime
from typing import Optional, Dict, Any, Set
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
    Robust worker agent that connects to the orchestrator and executes tasks.
    
    Features:
    - Handles long-running tasks without WebSocket timeout
    - Tracks completed tasks to prevent re-execution on reconnect
    - Graceful degradation when connection is lost during task
    - Fire-and-forget status updates that don't block or crash
    """
    
    def __init__(self):
        self.orchestrator_url = config.ORCHESTRATOR_URL
        self.token = config.WORKER_TOKEN
        self.api_type = config.API_TYPE
        self.local_api_url = config.LOCAL_API_URL
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.worker_id: Optional[str] = None
        self.current_task_id: Optional[str] = None
        self.current_task_data: Optional[Dict] = None
        
        # Track tasks we've already worked on to prevent re-execution
        self._completed_tasks: Set[str] = set()
        self._in_progress_task: Optional[str] = None
        
        self._running = False
        self._reconnect_attempts = 0
        self._http_client: Optional[httpx.AsyncClient] = None
        self._connection_healthy = False
        
        # Pending messages to send after reconnect
        self._pending_messages: list = []
    
    async def _wait_for_local_api(self, max_wait: int = 120) -> bool:
        """
        Wait for local API to be ready before accepting tasks.
        
        Args:
            max_wait: Maximum seconds to wait for API
            
        Returns:
            True if API is ready, False if timeout
        """
        logger.info(f"⏳ Waiting for local API at {self.local_api_url} to be ready...")
        
        start_time = asyncio.get_event_loop().time()
        attempt = 0
        
        while asyncio.get_event_loop().time() - start_time < max_wait:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Try a simple health check endpoint or just connect
                    response = await client.get(f"{self.local_api_url}/health")
                    if response.status_code == 200:
                        logger.info(f"✅ Local API is ready (attempt {attempt})")
                        return True
            except Exception as e:
                # Also try the root endpoint as fallback
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(f"{self.local_api_url}/")
                        if response.status_code in (200, 404):  # 404 is fine, API is responding
                            logger.info(f"✅ Local API is ready (attempt {attempt})")
                            return True
                except:
                    pass
            
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            logger.info(f"⏳ Local API not ready yet (attempt {attempt}, {elapsed}s elapsed)...")
            await asyncio.sleep(5)
        
        logger.error(f"❌ Local API not ready after {max_wait}s")
        return False
    
    async def start(self):
        """Start the worker agent."""
        logger.info(f"🚀 Starting worker agent ({self.api_type})...")
        logger.info(f"   Orchestrator: {self.orchestrator_url}")
        logger.info(f"   Local API: {self.local_api_url}")
        
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(None, connect=30.0))
        
        # Wait for local API to be ready before connecting to orchestrator
        # This prevents accepting tasks before we can process them
        if not await self._wait_for_local_api():
            logger.error("❌ Cannot start worker - local API not available")
            return
        
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
            try:
                await self.websocket.close()
            except:
                pass
        
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
        
        # Use longer ping timeout to handle long-running tasks
        # ping_interval=None disables automatic ping - we'll handle it manually
        async with websockets.connect(
            self.orchestrator_url,
            ping_interval=None,  # Disable auto-ping
            ping_timeout=None,   # Disable ping timeout
            close_timeout=10
        ) as websocket:
            self.websocket = websocket
            self._connection_healthy = True
            self._reconnect_attempts = 0
            
            # Authenticate
            if not await self._authenticate():
                return
            
            # Send any pending messages (e.g., task completion from before disconnect)
            await self._flush_pending_messages()
            
            # Start manual heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            try:
                await self._message_loop()
            finally:
                self._connection_healthy = False
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
                "local_api_url": self.local_api_url,
                # Tell orchestrator about any task we're currently executing
                "in_progress_task": self._in_progress_task
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
            logger.error(f"❌ Authentication failed: {data}")
            return False
    
    async def _flush_pending_messages(self):
        """Send any messages that were queued during disconnect."""
        while self._pending_messages:
            msg = self._pending_messages.pop(0)
            try:
                await self.websocket.send(json.dumps(msg))
                logger.info(f"📤 Sent pending message: {msg.get('type')}")
            except Exception as e:
                logger.error(f"Failed to send pending message: {e}")
                self._pending_messages.insert(0, msg)  # Put it back
                break
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to keep connection alive."""
        consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(config.HEARTBEAT_INTERVAL)
                
                # Always send heartbeat to prevent timeout, even during task execution
                if self.websocket:
                    try:
                        await self.websocket.send(json.dumps({"type": "heartbeat"}))
                        consecutive_failures = 0
                        logger.debug("💓 Heartbeat sent")
                    except ConnectionClosed:
                        consecutive_failures += 1
                        self._connection_healthy = False
                        logger.warning(f"⚠️ Heartbeat failed ({consecutive_failures}x) - connection lost")
                        # If task in progress, don't break loop - let task continue
                        # The task completion will trigger reconnection
                        if not self._in_progress_task:
                            logger.info("No active task, will reconnect...")
                            break
                        else:
                            logger.info("Task in progress, will send result after reconnection")
                    except Exception as e:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Heartbeat send error: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _message_loop(self):
        """Main message processing loop."""
        while self._running:
            try:
                # Large timeout for receiving messages during task execution
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=600.0  # 10 minute timeout
                )
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "task":
                    await self._handle_task(data)
                elif msg_type == "ping":
                    # Server ping to keep connection alive - respond with pong
                    try:
                        await self.websocket.send(json.dumps({"type": "pong"}))
                        logger.debug("📡 Received ping, sent pong")
                    except Exception:
                        pass  # Connection may be closing
                elif msg_type == "heartbeat_ack":
                    # Log status confirmation from orchestrator
                    status = data.get("status", "unknown")
                    worker_id = data.get("worker_id", "?")
                    current_task = data.get("current_task")
                    task_info = f", task: {current_task}" if current_task else ""
                    logger.info(f"✅ Orchestrator confirms: {worker_id} → {status}{task_info}")
                elif msg_type == "cancel":
                    await self._handle_cancel(data)
                else:
                    logger.debug(f"Unknown message type: {msg_type}")
                    
            except asyncio.TimeoutError:
                # Check if connection is still alive
                if self._in_progress_task:
                    logger.debug("Receive timeout but task in progress, continuing...")
                else:
                    logger.warning("Receive timeout, checking connection...")
                    # Try a ping to check connection
                    try:
                        await self.websocket.ping()
                    except:
                        logger.error("Connection dead, exiting message loop")
                        break
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                break
            except Exception as e:
                logger.error(f"Message handling error: {e}")
    
    async def _handle_cancel(self, data: dict):
        """Handle task cancellation request."""
        task_id = data.get("task_id")
        if self._in_progress_task == task_id:
            logger.warning(f"⚠️ Task {task_id} cancellation requested (will complete current API call)")
            # Note: We can't easily cancel the HTTP request mid-flight
            # But we can mark it for cleanup after current call completes
    
    async def _handle_task(self, data: dict):
        """Handle an incoming task from orchestrator."""
        task_id = data.get("task_id")
        report_id = data.get("report_id")
        action = data.get("action")
        payload = data.get("payload", {})
        
        # CRITICAL: Prevent duplicate task execution
        if task_id in self._completed_tasks:
            logger.warning(f"⚠️ Task {task_id} already completed, skipping duplicate")
            return
        
        if self._in_progress_task == task_id:
            logger.warning(f"⚠️ Task {task_id} already in progress, skipping")
            return
        
        if self._in_progress_task is not None:
            logger.warning(f"⚠️ Already working on {self._in_progress_task}, cannot accept {task_id}")
            return
        
        logger.info(f"📥 Received task: {task_id} ({action})")
        self.current_task_id = task_id
        self._in_progress_task = task_id
        self.current_task_data = data
        
        # Notify orchestrator we're starting
        await self._send_safe({
            "type": "running",
            "task_id": task_id
        })
        
        try:
            # Execute the task (this can take a long time)
            result = await self._execute_task(action, payload, report_id, task_id)
            
            # Mark as completed BEFORE sending success message
            self._completed_tasks.add(task_id)
            
            # Report success - use safe send that queues if disconnected
            await self._send_safe({
                "type": "complete",
                "task_id": task_id,
                "result": result
            })
            logger.info(f"✅ Task {task_id} completed successfully")
            
        except Exception as e:
            # Mark as completed even on failure to prevent retry loop
            self._completed_tasks.add(task_id)
            
            error_msg = str(e)
            logger.error(f"❌ Task {task_id} failed: {error_msg}")
            
            await self._send_safe({
                "type": "error",
                "task_id": task_id,
                "error": error_msg
            })
        finally:
            self.current_task_id = None
            self._in_progress_task = None
            self.current_task_data = None
            
            # Clean up old completed tasks (keep last 100)
            if len(self._completed_tasks) > 100:
                # Convert to list, remove oldest entries
                task_list = list(self._completed_tasks)
                self._completed_tasks = set(task_list[-100:])
    
    async def _execute_task(
        self, 
        action: str, 
        payload: dict, 
        report_id: str,
        task_id: str
    ) -> dict:
        """Execute a task by calling the local API."""
        endpoint = self._get_endpoint(action)
        url = f"{self.local_api_url}{endpoint}"
        
        logger.info(f"📡 Calling local API: {url}")
        
        # Add report_id for status tracking to a copy, but we might need to filter for API
        full_payload = {**payload, "report_id": report_id}
        
        # --- FIXES for Twitter API ---
        if action == "search_tweets":
            api_payload = {}
            
            # 1. Handle Keyword(s)
            if "keywords" in full_payload and isinstance(full_payload["keywords"], list):
                # Join list with OR
                api_payload["keyword"] = " OR ".join(full_payload.get("keywords", []))
            elif "keyword" in full_payload:
                api_payload["keyword"] = full_payload["keyword"]
            else:
                # Fallback if no keyword found (shouldn't happen with valid task)
                api_payload["keyword"] = ""
            
            # 2. Defaults per user spec
            api_payload["query_type"] = full_payload.get("query_type", "Top")
            api_payload["num_posts"] = full_payload.get("num_posts", 10)
            api_payload["num_comments"] = full_payload.get("num_comments", 0)
            
            # Use this clean payload for the request
            final_payload = api_payload
        else:
            # For other actions, use the full payload with report_id
            final_payload = full_payload
        # -----------------------------
        
        # Make the API call with no timeout (long-running scraping)
        response = await self._http_client.post(
            url,
            json=final_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            error_detail = response.text[:500]
            raise Exception(f"API returned {response.status_code}: {error_detail}")
        
        return response.json()
    
    def _get_endpoint(self, action: str) -> str:
        """Get the local API endpoint for an action."""
        endpoints = {
            # Twitter endpoints
            "search_tweets": "/search/tweets",

            # Crunchbase endpoints
            "search_with_rank": "/search/crunchbase/top-similar-with-rank",
            "search_similar": "/search/crunchbase/top-similar",
            "search_batch": "/search/crunchbase/batch",
            "enrich": "/search/crunchbase/batch",  # Enrichment uses batch endpoint
            
            # Tracxn endpoints
            "tracxn_search_with_rank": "/scrape-batch-api-with-rank",
            "tracxn_search": "/scrape-batch-api",
            
            # Generic
            "health": "/health",
        }
        
        return endpoints.get(action, f"/{action}")
    
    async def _send_safe(self, message: dict):
        """
        Send a message to orchestrator with graceful handling of disconnects.
        If disconnected, queue the message to send after reconnect.
        """
        if self._connection_healthy and self.websocket:
            try:
                await self.websocket.send(json.dumps(message))
                return
            except Exception as e:
                logger.warning(f"Failed to send message, queueing: {e}")
        
        # Queue for later
        self._pending_messages.append(message)
        logger.info(f"📦 Queued message for later: {message.get('type')}")
    
    async def send_status(
        self,
        step_key: str,
        detail_type: str,
        message: str,
        data: dict = None
    ):
        """
        Send a status update to orchestrator (fire-and-forget).
        
        This is designed to NEVER crash or block, even if connection is lost.
        """
        if not self.current_task_id:
            return
        
        status_msg = {
            "type": "status",
            "task_id": self.current_task_id,
            "step_key": step_key,
            "detail_type": detail_type,
            "message": message,
            "data": data or {}
        }
        
        # Try to send, but don't crash or block if it fails
        if self._connection_healthy and self.websocket:
            try:
                await self.websocket.send(json.dumps(status_msg))
            except Exception as e:
                logger.debug(f"Status update failed (non-critical): {e}")
        # Don't queue status updates - they're not critical


class StatusProxyServer:
    """
    Local HTTP server that receives status updates from local API
    and relays them via the worker agent's WebSocket connection.
    """
    
    def __init__(self, agent: WorkerAgent, port: int = 9099):
        self.agent = agent
        self.port = port
        self._server = None
    
    async def start(self):
        """Start the status proxy server."""
        from aiohttp import web
        
        app = web.Application()
        app.router.add_post('/status', self.handle_status)
        app.router.add_post('/api/reports/status-update/', self.handle_status)
        app.router.add_get('/health', self.handle_health)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        self._server = web.TCPSite(runner, '0.0.0.0', self.port)
        await self._server.start()
        
        logger.info(f"📡 Status proxy server started on port {self.port}")
    
    async def handle_health(self, request):
        from aiohttp import web
        return web.json_response({
            "status": "ok",
            "connected": self.agent._connection_healthy,
            "current_task": self.agent.current_task_id
        })
    
    async def handle_status(self, request):
        """Handle incoming status update from local API."""
        from aiohttp import web
        
        try:
            data = await request.json()
            
            step_key = data.get('step_key', 'unknown')
            detail_type = data.get('detail_type', 'status')
            message = data.get('message', '')
            status_data = data.get('data', {})
            
            # Fire and forget - create task but don't await
            if self.agent.current_task_id:
                asyncio.create_task(
                    self._send_status_safe(step_key, detail_type, message, status_data)
                )
            
            return web.json_response({"success": True})
            
        except Exception as e:
            logger.error(f"Status proxy error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _send_status_safe(self, step_key: str, detail_type: str, message: str, data: dict):
        """Safely send status, catching all errors."""
        try:
            await self.agent.send_status(step_key, detail_type, message, data)
        except Exception as e:
            logger.debug(f"Status relay failed (non-critical): {e}")


async def main():
    """Entry point for worker agent."""
    agent = WorkerAgent()
    
    # Start status proxy server
    status_proxy = StatusProxyServer(agent, port=9099)
    await status_proxy.start()
    
    # Start the agent
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
