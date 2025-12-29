"""
Chat URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('project/<uuid:project_id>/messages/', views.get_messages, name='chat-messages'),
    path('project/<uuid:project_id>/clear/', views.clear_messages, name='chat-clear'),
    path('modes/', views.get_available_modes, name='chat-modes'),
]

