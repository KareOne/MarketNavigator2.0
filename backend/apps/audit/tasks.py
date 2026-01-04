"""
Celery tasks for audit app.
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_tokens():
    """Clean up expired download tokens."""
    from apps.audit.models import DownloadToken
    
    expired_count = DownloadToken.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()[0]
    
    logger.info(f"Cleaned up {expired_count} expired download tokens")
    return expired_count


@shared_task
def cleanup_old_logs():
    """Clean up old audit logs based on retention policy."""
    from apps.audit.models import AuditLog, APIUsage
    
    retention_days = getattr(settings, 'AUDIT_LOG_RETENTION_DAYS', 90)
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # Clean audit logs
    audit_count = AuditLog.objects.filter(created_at__lt=cutoff_date).delete()[0]
    
    # Clean API usage (shorter retention - 30 days)
    api_cutoff = timezone.now() - timedelta(days=30)
    api_count = APIUsage.objects.filter(created_at__lt=api_cutoff).delete()[0]
    
    logger.info(f"Cleaned up {audit_count} audit logs and {api_count} API usage records")
    return {'audit_logs': audit_count, 'api_usage': api_count}


@shared_task
def log_audit_event(user_id, action, resource_type=None, resource_id=None, metadata=None, ip_address=None):
    """
    Async task to log audit events.
    Called from views/middleware to avoid blocking the request.
    """
    from apps.audit.models import AuditLog
    from apps.users.models import User
    
    try:
        user = User.objects.get(id=user_id) if user_id else None
        org_id = None
        
        if user:
            # Get user's organization
            from apps.organizations.models import OrganizationMember
            membership = OrganizationMember.objects.filter(user=user).first()
            if membership:
                org_id = membership.organization_id
        
        AuditLog.objects.create(
            user=user,
            organization_id=org_id,
            action=action,
            resource_type=resource_type or '',
            resource_id=resource_id,
            ip_address=ip_address,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def track_api_usage(self, org_id=None, user_id=None, endpoint=None, method=None, 
                    status_code=None, response_time_ms=None, request_size=None, response_size=None):
    """
    Async task to track API usage.
    Called from middleware to avoid blocking requests and exhausting DB connections.
    """
    from apps.audit.models import APIUsage
    from django.db import connection
    
    try:
        APIUsage.objects.create(
            organization_id=org_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            request_size=request_size,
            response_size=response_size,
        )
    except Exception as e:
        logger.error(f"Failed to track API usage: {e}")
        # Don't retry on DB errors as it might make connection pool issues worse
        if 'QueuePool' in str(e) or 'connection' in str(e).lower():
            return  # Don't retry connection-related errors
        raise self.retry(exc=e)
    finally:
        # Explicitly close connection to return it to pool
        connection.close()
