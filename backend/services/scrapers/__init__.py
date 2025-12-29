"""
Base scraper service with high-scale features.
Provides common functionality for all scraper API clients:
- Retry with exponential backoff
- Circuit breaker pattern
- Response caching
- Request rate limiting
- Health monitoring

Per FINAL_ARCHITECTURE_SPECIFICATION.md - uses existing MVP scraper containers.
"""
import httpx
from abc import ABC, abstractmethod
from django.conf import settings
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)
from core.cache import CacheService
from core.exceptions import ExternalAPIError, RateLimitError
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation for API resilience.
    Prevents cascading failures when external services are down.
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3
    
    # State
    failures: int = 0
    state: CircuitState = CircuitState.CLOSED
    last_failure_time: Optional[datetime] = None
    half_open_calls: int = 0
    
    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPENED after {self.failures} failures")
    
    def record_success(self):
        """Record a success and reset if needed."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self._reset()
        elif self.state == CircuitState.CLOSED:
            self.failures = 0
    
    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info("Circuit breaker moving to HALF_OPEN")
                    return True
            return False
        
        # HALF_OPEN state
        return True
    
    def _reset(self):
        """Reset the circuit breaker."""
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        self.half_open_calls = 0
        logger.info("Circuit breaker CLOSED (reset)")


class BaseScraperClient(ABC):
    """
    Base class for scraper API clients.
    Provides high-scale features for reliability.
    """
    
    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 3,
        cache_ttl: int = 3600,
    ):
        self.service_name = service_name
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout)
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl
        self.circuit_breaker = CircuitBreaker()
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key for request."""
        return f"scraper:{self.service_name}:{endpoint}:{CacheService.hash_key(params)}"
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        data: dict = None,
        use_cache: bool = True,
    ) -> dict:
        """
        Make an API request with retry, caching, and circuit breaker.
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise ExternalAPIError(
                f"{self.service_name} service is temporarily unavailable (circuit open)"
            )
        
        # Check cache
        cache_key = self._get_cache_key(endpoint, params or data or {})
        if use_cache:
            cached = CacheService.get_api_response(
                self.service_name, 
                {'key': cache_key}
            )
            if cached:
                logger.debug(f"Cache hit for {self.service_name}:{endpoint}")
                return cached
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params if method == 'GET' else None,
                    json=data if method == 'POST' else None,
                    headers={
                        'accept': 'application/json',
                        'Content-Type': 'application/json',
                    },
                )
                
                if response.status_code == 429:
                    self.circuit_breaker.record_failure()
                    raise RateLimitError(f"{self.service_name} rate limit exceeded")
                
                if response.status_code >= 500:
                    self.circuit_breaker.record_failure()
                    raise ExternalAPIError(f"{self.service_name} server error: {response.status_code}")
                
                if response.status_code >= 400:
                    raise ExternalAPIError(f"{self.service_name} error: {response.status_code}")
                
                result = response.json()
                
                # Record success
                self.circuit_breaker.record_success()
                
                # Cache result
                if use_cache:
                    CacheService.set_api_response(
                        self.service_name,
                        {'key': cache_key},
                        result,
                        ttl=self.cache_ttl
                    )
                
                return result
                
        except httpx.RequestError as e:
            self.circuit_breaker.record_failure()
            logger.error(f"{self.service_name} request failed: {e}")
            raise ExternalAPIError(f"Failed to connect to {self.service_name}: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of the scraper service."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.get(f"{self.base_url}/health")
                is_healthy = response.status_code < 500
                
                return {
                    'service': self.service_name,
                    'healthy': is_healthy,
                    'status_code': response.status_code,
                    'circuit_state': self.circuit_breaker.state.value,
                    'failures': self.circuit_breaker.failures,
                }
        except Exception as e:
            return {
                'service': self.service_name,
                'healthy': False,
                'error': str(e),
                'circuit_state': self.circuit_breaker.state.value,
                'failures': self.circuit_breaker.failures,
            }


class RetryableScraperClient(BaseScraperClient):
    """
    Scraper client with tenacity retry logic.
    """
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.RequestError, ExternalAPIError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def request_with_retry(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        data: dict = None,
        use_cache: bool = True,
    ) -> dict:
        """Make request with automatic retry on failure."""
        return await self._make_request(method, endpoint, params, data, use_cache)
