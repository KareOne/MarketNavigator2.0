"""
Chat models for AI assistant.

Includes:
- ChatMessage: Individual chat messages
- ChatSummary: Compressed summaries of message batches for token optimization
"""
import uuid
from django.db import models
from django.conf import settings


class ChatSummary(models.Model):
    """
    Compressed summary of a batch of ChatMessages.
    
    Used for token optimization: instead of sending all historical messages,
    we send summaries of older message batches + recent raw messages.
    
    Example: For 73 messages with batch_size=10:
    - Summaries: [1-10], [11-20], [21-30], [31-40], [41-50], [51-60], [61-70]
    - Raw messages: 71, 72, 73
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='chat_summaries'
    )
    
    # The actual summary text used for LLM context
    summary_text = models.TextField()
    
    # Range tracking - which messages this summary covers
    start_sequence = models.IntegerField(help_text="Starting message sequence number in this batch")
    end_sequence = models.IntegerField(help_text="Ending message sequence number in this batch")
    
    # Metadata for tracking and debugging
    message_count = models.IntegerField(default=0, help_text="Number of messages summarized")
    input_tokens = models.IntegerField(default=0, help_text="Estimated input tokens before summarization")
    output_tokens = models.IntegerField(default=0, help_text="Tokens in the summary")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_summaries'
        ordering = ['start_sequence']
    
    def __str__(self):
        return f"Summary [{self.start_sequence}-{self.end_sequence}] for project {self.project_id}"


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
    
    # Sequence number for ordering and summary tracking
    sequence = models.IntegerField(default=0, help_text="Message sequence number within project")
    
    # Link to summary that contains this message (NULL = not yet summarized / recent)
    summary = models.ForeignKey(
        ChatSummary,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['project', 'sequence']),
            models.Index(fields=['project', 'summary']),
        ]
    
    def __str__(self):
        sender = "Bot" if self.is_bot else (self.user.username if self.user else "Unknown")
        return f"[{self.sequence}] {sender}: {self.message[:50]}"
    
    def save(self, *args, **kwargs):
        # Auto-assign sequence number if not set
        if self.sequence == 0 and not self.pk:
            last_msg = ChatMessage.objects.filter(project=self.project).order_by('-sequence').first()
            self.sequence = (last_msg.sequence + 1) if last_msg else 1
        super().save(*args, **kwargs)
