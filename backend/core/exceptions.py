"""
Custom exception handling for MarketNavigator v2.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    Provides consistent error response format.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Customize the response data
        custom_data = {
            'success': False,
            'error': {
                'type': exc.__class__.__name__,
                'message': str(exc),
                'code': response.status_code,
            }
        }
        
        # Add field errors for validation
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                custom_data['error']['details'] = exc.detail
            elif isinstance(exc.detail, list):
                custom_data['error']['details'] = exc.detail
        
        response.data = custom_data
        
        # Log errors
        if response.status_code >= 500:
            logger.error(f"Server error: {exc}", exc_info=True)
        elif response.status_code >= 400:
            logger.warning(f"Client error: {exc}")
    
    return response


class APIException(Exception):
    """Base exception for API errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "An error occurred"
    
    def __init__(self, message=None, status_code=None):
        self.message = message or self.default_message
        if status_code:
            self.status_code = status_code
        super().__init__(self.message)


class ExternalAPIError(APIException):
    """Exception for external API failures."""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = "External service unavailable"


class RateLimitError(APIException):
    """Exception for rate limit exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = "Rate limit exceeded"


class ResourceNotFoundError(APIException):
    """Exception for resource not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found"


class PermissionDeniedError(APIException):
    """Exception for permission denied."""
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "Permission denied"


class ValidationError(APIException):
    """Exception for validation errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "Validation error"
