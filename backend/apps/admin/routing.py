"""
WebSocket routing for admin.
"""
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/admin/tasks/', consumers.AdminTaskConsumer.as_asgi()),
]
