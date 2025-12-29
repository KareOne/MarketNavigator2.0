"""
File models for storage.
"""
import uuid
from django.db import models
from django.conf import settings


class File(models.Model):
    """File model for storage management."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Ownership
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        related_name='files'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        null=True,
        related_name='files'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    # File info
    name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100, blank=True)  # report, upload, export
    file_category = models.CharField(max_length=100, blank=True)  # crunchbase, tracxn, etc
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.BigIntegerField(default=0)
    storage_path = models.TextField()
    
    # Access
    is_public = models.BooleanField(default=False)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'files'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
