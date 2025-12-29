"""
Shareable link models.
"""
import uuid
import secrets
from django.db import models
from django.conf import settings


class ShareableLink(models.Model):
    """Shareable link for public report access."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=32, unique=True, db_index=True)
    
    # What's being shared
    report = models.ForeignKey(
        'reports.Report',
        on_delete=models.CASCADE,
        related_name='shareable_links'
    )
    report_version = models.ForeignKey(
        'reports.ReportVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Who created it
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shared_links'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='shareable_links'
    )
    
    # Access control
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    password_hash = models.CharField(max_length=255, blank=True)
    
    # Tracking
    view_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shareable_links'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Share link for {self.report}"
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(16)[:24]
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Check if link is still valid."""
        from django.utils import timezone
        
        if not self.is_active:
            return False
        
        if self.expires_at and self.expires_at < timezone.now():
            return False
        
        return True
    
    def increment_view_count(self):
        """Increment view count and update last viewed."""
        from django.utils import timezone
        
        self.view_count += 1
        self.last_viewed_at = timezone.now()
        self.save(update_fields=['view_count', 'last_viewed_at'])
