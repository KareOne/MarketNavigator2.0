"""
Organization views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Organization, OrganizationMember
from .serializers import (
    OrganizationSerializer, 
    OrganizationMemberSerializer,
    CreateOrganizationSerializer
)


class OrganizationViewSet(viewsets.ModelViewSet):
    """ViewSet for organizations."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer
    
    def get_queryset(self):
        """Get organizations for current user."""
        return Organization.objects.filter(
            members__user=self.request.user
        ).distinct()
    
    def create(self, request, *args, **kwargs):
        """Create organization with current user as owner."""
        serializer = CreateOrganizationSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        org = serializer.save()
        
        return Response(
            OrganizationSerializer(org).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """List organization members."""
        org = self.get_object()
        members = org.members.select_related('user').all()
        serializer = OrganizationMemberSerializer(members, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """Invite a user to organization."""
        org = self.get_object()
        
        # Check if user is admin
        membership = OrganizationMember.objects.filter(
            organization=org,
            user=request.user
        ).first()
        
        if not membership or not membership.can_manage_members():
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        email = request.data.get('email')
        role = request.data.get('role', 'member')
        
        from apps.users.models import User
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create membership
        member, created = OrganizationMember.objects.get_or_create(
            organization=org,
            user=user,
            defaults={
                'role': role,
                'invited_by': request.user
            }
        )
        
        if not created:
            return Response(
                {"error": "User is already a member"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            OrganizationMemberSerializer(member).data,
            status=status.HTTP_201_CREATED
        )
