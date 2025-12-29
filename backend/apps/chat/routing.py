"""
WebSocket routing for chat.
"""
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/projects/<uuid:project_id>/chat/', consumers.ChatConsumer.as_asgi()),
]
