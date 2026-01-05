"""
Custom middleware for MarketNavigator v2.
Includes audit logging and API usage tracking.
Per HIGH_SCALE_ARCHITECTURE_PLAN.md
"""
import time
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DatabaseCleanupMiddleware:
    """
    Middleware to ensure database connections are closed after request.
    Critical for preventing connection pool exhaustion in async/threaded environments.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Force close old connections to prevent zombies
        from django.db import close_old_connections
        close_old_connections()
        
        return response


class AuditMiddleware:
    """
    Middleware for audit logging and API usage tracking.
    Per HIGH_SCALE_ARCHITECTURE_PLAN.md audit_logs and api_usage tables.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.audit_enabled = getattr(settings, 'AUDIT_LOG_ENABLED', True)
        self.usage_tracking = getattr(settings, 'API_USAGE_TRACKING_ENABLED', True)
    
    def __call__(self, request):
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        # Record start time
        start_time = time.time()
        
        # Get request size
        request_size = len(request.body) if request.body else 0
        
        # Process request
        response = self.get_response(request)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Get response size
        response_size = len(response.content) if hasattr(response, 'content') else 0
        
        # Track API usage (async to avoid blocking)
        if self.usage_tracking:
            self._track_usage(
                request=request,
                response=response,
                response_time_ms=response_time_ms,
                request_size=request_size,
                response_size=response_size,
            )
        
        return response
    
    def _track_usage(self, request, response, response_time_ms, request_size, response_size):
        """Track API usage for rate limiting and analytics.
        Uses Celery for async processing to avoid blocking requests and exhausting DB connections.
        """
        try:
            # Skip tracking for high-frequency endpoints to reduce DB load
            skip_endpoints = ['/api/health/', '/api/admin/orchestrator/health/']
            if request.path in skip_endpoints:
                return
            
            # Sample high-frequency endpoints (track 1 in 10 requests)
            sample_endpoints = ['/api/admin/orchestrator/workers/', '/api/admin/orchestrator/queue/']
            if request.path in sample_endpoints:
                import random
                if random.random() > 0.1:  # Skip 90% of requests
                    return
            
            user_id = request.user.id if request.user.is_authenticated else None
            org_id = getattr(request.user, 'organization_id', None) if request.user.is_authenticated else None
            
            # Use Celery task for async processing (non-blocking)
            from apps.audit.tasks import track_api_usage
            track_api_usage.delay(
                org_id=org_id,
                user_id=user_id,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                request_size=request_size,
                response_size=response_size,
            )
        except Exception as e:
            # Log but don't fail the request
            logger.warning(f"Failed to queue API usage tracking: {e}")
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class RequestLoggingMiddleware:
    """
    Middleware for logging all requests.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log request
        logger.info(
            f"Request: {request.method} {request.path}",
            extra={
                'method': request.method,
                'path': request.path,
                'user': str(request.user.id) if request.user.is_authenticated else 'anonymous',
            }
        )
        
        response = self.get_response(request)
        
        # Log response
        logger.info(
            f"Response: {response.status_code}",
            extra={
                'status_code': response.status_code,
                'path': request.path,
            }
        )
        
        return response
