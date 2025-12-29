"""
WebSocket consumer for real-time chat.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for project chat."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.room_group_name = f"project_{self.project_id}"
        self.user = self.scope.get('user')
        
        logger.info(f"🔌 WebSocket connect attempt for project {self.project_id}")
        logger.info(f"👤 User from scope: {self.user} (authenticated: {getattr(self.user, 'is_authenticated', False)})")
        
        if not self.user or not self.user.is_authenticated:
            logger.warning(f"❌ WebSocket connection rejected - user not authenticated")
            await self.close()
            return
        
        logger.info(f"✅ User {self.user.id} authenticated for project {self.project_id}")
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"✅ WebSocket connection accepted for project {self.project_id}")
        
        # Send chat history
        history = await self.get_chat_history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': history
        }))
        logger.info(f"📤 Sent {len(history)} history messages")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        logger.info(f"🔌 WebSocket disconnect for project {self.project_id} (code: {close_code})")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket message."""
        logger.info(f"📥 Received message: {text_data[:100]}...")
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')
            
            if message_type == 'message':
                await self.handle_user_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON received")
            await self.send_error("Invalid message format")
    
    async def handle_user_message(self, data):
        """Handle user message and trigger AI response."""
        message = data.get('message', '').strip()
        active_modes = data.get('active_modes', [])  # Get active modes from client
        if not message:
            logger.warning("⚠️ Empty message received, ignoring")
            return
        
        logger.info(f"💬 Processing message: {message[:50]}... (modes: {active_modes})")
        
        # Save user message (user messages don't have modes - only bot responses do)
        saved_msg = await self.save_message(message, is_bot=False)
        logger.info(f"💾 User message saved with id: {saved_msg['id']}")
        
        # Broadcast user message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(saved_msg['id']),
                    'message': message,
                    'is_bot': False,
                    'user_id': str(self.user.id),
                    'created_at': saved_msg['created_at'],
                    'active_modes': []
                }
            }
        )
        
        # Send thinking status
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'status_update',
                'status': 'thinking'
            }
        )
        
        # Process with AI (async task)
        logger.info(f"🚀 Dispatching Celery task for project {self.project_id} with modes: {active_modes}")
        from .tasks import process_chat_message
        task = process_chat_message.delay(
            str(self.project_id),
            str(self.user.id),
            message,
            active_modes  # Pass active modes to task
        )
        logger.info(f"✅ Celery task dispatched: {task.id}")
    
    async def handle_typing(self, data):
        """Broadcast typing indicator."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'is_typing': data.get('is_typing', False)
            }
        )
    
    # Group message handlers
    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def status_update(self, event):
        """Send status update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'status',
            'status': event['status']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'is_typing': event['is_typing']
        }))
    
    async def report_progress(self, event):
        """Send report progress update with step details."""
        await self.send(text_data=json.dumps({
            'type': 'report_progress',
            'report_type': event['report_type'],
            'report_id': event.get('report_id'),
            'progress': event['progress'],
            'current_step': event['current_step'],
            'step_key': event.get('step_key'),
            'status': event.get('status'),
            'steps': event.get('steps', []),  # All steps with their status and details
            'time_estimate': event.get('time_estimate')  # Forward time estimate
        }))
    
    async def auto_fill(self, event):
        """Send auto-fill notification."""
        await self.send(text_data=json.dumps({
            'type': 'auto_fill',
            'field': event['field'],
            'value': event['value'],
            'confidence': event.get('confidence', 1.0)
        }))
    
    async def send_error(self, error):
        """Send error message."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error
        }))
    
    @database_sync_to_async
    def get_chat_history(self):
        """Get chat history for project."""
        from .models import ChatMessage
        
        messages = ChatMessage.objects.filter(
            project_id=self.project_id
        ).order_by('created_at')[:100]
        
        return [
            {
                'id': str(m.id),
                'message': m.message,
                'is_bot': m.is_bot,
                'user_id': str(m.user_id) if m.user_id else None,
                'message_type': m.message_type,
                'metadata': m.metadata,
                'active_modes': m.active_modes,  # Include modes in history
                'created_at': m.created_at.isoformat()
            }
            for m in messages
        ]
    
    @database_sync_to_async
    def save_message(self, message, is_bot=False, message_type='text', metadata=None):
        """Save message to database."""
        from .models import ChatMessage
        
        msg = ChatMessage.objects.create(
            project_id=self.project_id,
            user_id=None if is_bot else self.user.id,
            message=message,
            is_bot=is_bot,
            message_type=message_type,
            metadata=metadata or {}
        )
        
        return {
            'id': msg.id,
            'created_at': msg.created_at.isoformat()
        }
