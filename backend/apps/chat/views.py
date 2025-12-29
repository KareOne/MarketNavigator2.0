"""
Chat API views.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ChatMessage
from apps.projects.models import Project


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_messages(request, project_id):
    """Get chat messages for a project."""
    project = Project.objects.get(id=project_id)
    
    messages = ChatMessage.objects.filter(
        project=project
    ).order_by('created_at')
    
    data = [
        {
            'id': str(m.id),
            'message': m.message,
            'is_bot': m.is_bot,
            'user_id': str(m.user_id) if m.user_id else None,
            'message_type': m.message_type,
            'metadata': m.metadata,
            'active_modes': m.active_modes,
            'created_at': m.created_at.isoformat()
        }
        for m in messages
    ]
    
    return Response(data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_messages(request, project_id):
    """Clear all chat messages for a project."""
    ChatMessage.objects.filter(project_id=project_id).delete()
    return Response({"message": "Chat cleared"})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_modes(request):
    """Get all available chat modes."""
    from services.chat_modes import get_available_modes as get_modes
    return Response(get_modes())

