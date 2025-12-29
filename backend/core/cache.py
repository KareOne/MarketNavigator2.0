"""
Cache service layer with TTL strategies.
Per HIGH_SCALE_ARCHITECTURE_PLAN.md Cache Strategy.
"""
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """
    Centralized cache service with TTL strategies per HIGH_SCALE_ARCHITECTURE_PLAN.
    
    Cache Layers:
    - User sessions: 24 hours
    - API responses: 5-60 minutes
    - Research results: 24 hours
    - Company data: 7 days
    - Project data: 1 hour
    """
    
    # Cache key prefixes
    PREFIX_USER = 'user'
    PREFIX_PROJECT = 'project'
    PREFIX_REPORT = 'report'
    PREFIX_COMPANY = 'company'
    PREFIX_RESEARCH = 'research'
    PREFIX_API = 'api'
    
    @staticmethod
    def get_ttl(cache_type: str) -> int:
        """Get TTL for cache type from settings."""
        ttl_settings = getattr(settings, 'CACHE_TTL', {})
        return ttl_settings.get(cache_type, 300)  # Default 5 minutes
    
    @staticmethod
    def make_key(*args) -> str:
        """Create a cache key from arguments."""
        key_parts = [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    @staticmethod
    def hash_key(data: dict) -> str:
        """Create a hash from dict for complex cache keys."""
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.md5(serialized.encode()).hexdigest()
    
    # =========================================================================
    # User Caching
    # =========================================================================
    @classmethod
    def get_user(cls, user_id: str):
        """Get cached user data."""
        key = cls.make_key(cls.PREFIX_USER, user_id)
        return cache.get(key)
    
    @classmethod
    def set_user(cls, user_id: str, data: dict):
        """Cache user data."""
        key = cls.make_key(cls.PREFIX_USER, user_id)
        ttl = cls.get_ttl('user_session')
        cache.set(key, data, ttl)
    
    @classmethod
    def invalidate_user(cls, user_id: str):
        """Invalidate user cache."""
        key = cls.make_key(cls.PREFIX_USER, user_id)
        cache.delete(key)
        # Also invalidate user's projects list
        cache.delete(cls.make_key(cls.PREFIX_USER, user_id, 'projects'))
    
    # =========================================================================
    # Project Caching
    # =========================================================================
    @classmethod
    def get_project(cls, project_id: str):
        """Get cached project data."""
        key = cls.make_key(cls.PREFIX_PROJECT, project_id)
        return cache.get(key)
    
    @classmethod
    def set_project(cls, project_id: str, data: dict):
        """Cache project data."""
        key = cls.make_key(cls.PREFIX_PROJECT, project_id)
        ttl = cls.get_ttl('project_data')
        cache.set(key, data, ttl)
    
    @classmethod
    def invalidate_project(cls, project_id: str, user_id: str = None):
        """Invalidate project and related caches."""
        cache.delete(cls.make_key(cls.PREFIX_PROJECT, project_id))
        cache.delete(cls.make_key(cls.PREFIX_PROJECT, project_id, 'inputs'))
        cache.delete(cls.make_key(cls.PREFIX_PROJECT, project_id, 'reports'))
        
        if user_id:
            cache.delete(cls.make_key(cls.PREFIX_USER, user_id, 'projects'))
    
    # =========================================================================
    # Report Caching
    # =========================================================================
    @classmethod
    def get_report(cls, report_id: str):
        """Get cached report data."""
        key = cls.make_key(cls.PREFIX_REPORT, report_id)
        return cache.get(key)
    
    @classmethod
    def set_report(cls, report_id: str, data: dict):
        """Cache report data."""
        key = cls.make_key(cls.PREFIX_REPORT, report_id)
        ttl = cls.get_ttl('research_results')
        cache.set(key, data, ttl)
    
    @classmethod
    def invalidate_report(cls, report_id: str, project_id: str = None):
        """Invalidate report cache."""
        cache.delete(cls.make_key(cls.PREFIX_REPORT, report_id))
        if project_id:
            cache.delete(cls.make_key(cls.PREFIX_PROJECT, project_id, 'reports'))
    
    # =========================================================================
    # Company/Research Data Caching
    # =========================================================================
    @classmethod
    def get_company(cls, company_id: str):
        """Get cached company data."""
        key = cls.make_key(cls.PREFIX_COMPANY, company_id)
        return cache.get(key)
    
    @classmethod
    def set_company(cls, company_id: str, data: dict):
        """Cache company data (long TTL)."""
        key = cls.make_key(cls.PREFIX_COMPANY, company_id)
        ttl = cls.get_ttl('company_data')
        cache.set(key, data, ttl)
    
    @classmethod
    def get_research(cls, project_id: str, source: str):
        """Get cached research results."""
        key = cls.make_key(cls.PREFIX_RESEARCH, project_id, source)
        return cache.get(key)
    
    @classmethod
    def set_research(cls, project_id: str, source: str, data: dict):
        """Cache research results."""
        key = cls.make_key(cls.PREFIX_RESEARCH, project_id, source)
        ttl = cls.get_ttl('research_results')
        cache.set(key, data, ttl)
    
    # =========================================================================
    # API Response Caching
    # =========================================================================
    @classmethod
    def get_api_response(cls, endpoint: str, params: dict):
        """Get cached API response."""
        params_hash = cls.hash_key(params)
        key = cls.make_key(cls.PREFIX_API, endpoint, params_hash)
        return cache.get(key)
    
    @classmethod
    def set_api_response(cls, endpoint: str, params: dict, data: dict, ttl: int = None):
        """Cache API response."""
        params_hash = cls.hash_key(params)
        key = cls.make_key(cls.PREFIX_API, endpoint, params_hash)
        if ttl is None:
            ttl = cls.get_ttl('api_response')
        cache.set(key, data, ttl)


def cache_response(cache_type: str = 'api_response', key_func=None):
    """
    Decorator for caching function/method responses.
    
    Usage:
        @cache_response('project_data')
        def get_project(project_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name + args hash
                key_data = {
                    'func': func.__name__,
                    'args': str(args),
                    'kwargs': str(sorted(kwargs.items())),
                }
                cache_key = f"fn:{func.__name__}:{CacheService.hash_key(key_data)}"
            
            # Try cache first
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            ttl = CacheService.get_ttl(cache_type)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key} (TTL: {ttl}s)")
            
            return result
        return wrapper
    return decorator
