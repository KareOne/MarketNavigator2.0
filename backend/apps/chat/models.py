"""
Chat models for AI assistant.
"""
import uuid
from django.db import models
from django.conf import settings


class ChatMessage(models.Model):
    """Chat message model."""
    
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('system', 'System'),
        ('error', 'Error'),
        ('auto_fill', 'Auto Fill'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='messages'
    )
    
    message = models.TextField()
    is_bot = models.BooleanField(default=False)
    message_type = models.CharField(
        max_length=50, 
        choices=MESSAGE_TYPE_CHOICES, 
        default='text'
    )
    metadata = models.JSONField(default=dict, blank=True)
    active_modes = models.JSONField(default=list, blank=True)  # Modes active when message generated
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
    
    def __str__(self):
        sender = "Bot" if self.is_bot else (self.user.username if self.user else "Unknown")
        return f"{sender}: {self.message[:50]}"
