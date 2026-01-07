"""
WebSocket consumer for admin dashboard.
Provides real-time updates for orchestrator task status.
"""
import json
import logging
import asyncio
import httpx
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)

ORCHESTRATOR_URL = getattr(settings, 'ORCHESTRATOR_URL', 'http://orchestrator:8010')


class AdminTaskConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for admin task testing with real-time updates."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            logger.warning("❌ Admin WebSocket rejected - not authenticated")
            await self.close()
            return
        
        # Check if user is admin
        admin_emails = ["thehamidrezamafi@gmail.com"]
        if self.user.email not in admin_emails:
            logger.warning(f"❌ Admin WebSocket rejected - {self.user.email} not admin")
            await self.close()
            return
        
        await self.accept()
        logger.info(f"✅ Admin WebSocket connected for {self.user.email}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        logger.info(f"🔌 Admin WebSocket disconnected (code: {close_code})")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'submit_test':
                await self.handle_submit_test(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send_error(str(e))
    
    async def handle_submit_test(self, data):
        """Submit a test task and stream results."""
        import uuid
        
        api_type = data.get('api_type', 'crunchbase')
        action = data.get('action', 'health')
        payload = data.get('payload', {})
        target_worker_id = data.get('target_worker_id')  # Route to specific worker
        test_report_id = f"test-{uuid.uuid4()}"
        
        # Send acknowledgment
        await self.send(text_data=json.dumps({
            'type': 'task_submitted',
            'report_id': test_report_id
        }))
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=30.0)) as client:
                # Submit task to orchestrator
                response = await client.post(
                    f"{ORCHESTRATOR_URL}/tasks/submit",
                    json={
                        "api_type": api_type,
                        "action": action,
                        "report_id": test_report_id,
                        "payload": payload,
                        "priority": 10,
                        "target_worker_id": target_worker_id
                    }
                )
                
                if response.status_code != 200:
                    await self.send(text_data=json.dumps({
                        'type': 'task_error',
                        'error': f"Failed to submit: {response.text}"
                    }))
                    return
                
                task_data = response.json()
                task_id = task_data.get("task_id")
                
                await self.send(text_data=json.dumps({
                    'type': 'task_started',
                    'task_id': task_id
                }))
                
                # Poll for completion (no timeout - runs until complete)
                poll_interval = 3.0
                while True:
                    await asyncio.sleep(poll_interval)
                    
                    try:
                        status_response = await client.get(f"{ORCHESTRATOR_URL}/tasks/{task_id}")
                        
                        if status_response.status_code != 200:
                            continue
                        
                        status_data = status_response.json()
                        task_status = status_data.get("status")
                        
                        # Send status update
                        await self.send(text_data=json.dumps({
                            'type': 'task_status',
                            'task_id': task_id,
                            'status': task_status
                        }))
                        
                        if task_status == "completed":
                            await self.send(text_data=json.dumps({
                                'type': 'task_complete',
                                'task_id': task_id,
                                'success': True,
                                'result': status_data.get("result")
                            }))
                            return
                        
                        elif task_status in ("failed", "cancelled"):
                            await self.send(text_data=json.dumps({
                                'type': 'task_complete',
                                'task_id': task_id,
                                'success': False,
                                'error': status_data.get("error")
                            }))
                            return
                    
                    except Exception as poll_error:
                        logger.warning(f"Poll error: {poll_error}")
                        # Continue polling on errors
                        
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'task_error',
                'error': str(e)
            }))
    
    async def send_error(self, error: str):
        """Send error message."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error
        }))
