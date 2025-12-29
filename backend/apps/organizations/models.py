"""
Organization models with role-based permissions.
"""
import uuid
from django.db import models
from django.conf import settings


class Organization(models.Model):
    """Organization for multi-tenancy."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    plan_tier = models.CharField(max_length=50, default='free')  # free, pro, enterprise (mock)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organizations'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    """Organization membership with roles."""
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='member')
    permissions = models.JSONField(default=dict, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='invitations_sent'
    )
    
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'organization_members'
        unique_together = ['organization', 'user']
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"
    
    @property
    def is_owner(self):
        return self.role == 'owner'
    
    @property
    def is_admin(self):
        return self.role in ['owner', 'admin']
    
    def can_manage_members(self):
        return self.is_admin
    
    def can_edit_project(self, project):
        """Check if user can edit a specific project."""
        if self.is_admin:
            return True
        return project.created_by_id == self.user_id
    
    def can_run_reports(self, project):
        """Check if user can run reports for a project."""
        if self.is_admin:
            return True
        return project.created_by_id == self.user_id
