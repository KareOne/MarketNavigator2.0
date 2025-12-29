"""
JWT authentication middleware for WebSocket.
"""
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import logging

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_string):
    """Get user from JWT token."""
    from apps.users.models import User
    
    try:
        token = AccessToken(token_string)
        user_id = token.get('user_id')
        
        if user_id:
            return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist) as e:
        logger.warning(f"WebSocket auth failed: {e}")
    
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Middleware to authenticate WebSocket connections with JWT."""
    
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        params = dict(x.split('=') for x in query_string.split('&') if '=' in x)
        token = params.get('token', '')
        
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
