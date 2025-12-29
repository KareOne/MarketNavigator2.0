"""
Audit and API Usage models.
Per HIGH_SCALE_ARCHITECTURE_PLAN.md audit_logs and api_usage tables.
"""
import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Audit log for tracking user actions.
    Per HIGH_SCALE_ARCHITECTURE_PLAN.md audit_logs table.
    """
    
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('create_project', 'Create Project'),
        ('update_project', 'Update Project'),
        ('delete_project', 'Delete Project'),
        ('start_report', 'Start Report'),
        ('complete_report', 'Complete Report'),
        ('share_report', 'Share Report'),
        ('upload_file', 'Upload File'),
        ('delete_file', 'Delete File'),
        ('invite_member', 'Invite Member'),
        ('remove_member', 'Remove Member'),
        ('change_role', 'Change Role'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    
    action = models.CharField(max_length=100, db_index=True)
    resource_type = models.CharField(max_length=100, blank=True, db_index=True)
    resource_id = models.UUIDField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.action} by {self.user} at {self.created_at}"


class APIUsage(models.Model):
    """
    API usage tracking for rate limiting and analytics.
    Per HIGH_SCALE_ARCHITECTURE_PLAN.md api_usage table.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_usage'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_usage'
    )
    
    endpoint = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField(null=True)
    
    response_time_ms = models.IntegerField(null=True)
    request_size = models.BigIntegerField(default=0)
    response_size = models.BigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'api_usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['endpoint', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"


class DownloadToken(models.Model):
    """
    Download tokens for secure file access.
    Per HIGH_SCALE_ARCHITECTURE_PLAN.md download_tokens table.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    
    file = models.ForeignKey(
        'files.File',
        on_delete=models.CASCADE,
        related_name='download_tokens'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        null=True
    )
    
    expires_at = models.DateTimeField(db_index=True)
    access_count = models.IntegerField(default=0)
    max_access_count = models.IntegerField(default=-1)  # -1 = unlimited
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(null=True)
    
    class Meta:
        db_table = 'download_tokens'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['file']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Token for {self.file.name}"
    
    def is_valid(self):
        """Check if token is still valid."""
        from django.utils import timezone
        if timezone.now() > self.expires_at:
            return False
        if self.max_access_count != -1 and self.access_count >= self.max_access_count:
            return False
        return True
