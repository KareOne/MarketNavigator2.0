"""
Project views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Project, ProjectInput
from .serializers import ProjectSerializer, ProjectInputSerializer, CreateProjectSerializer
from apps.organizations.models import OrganizationMember


class ProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for projects."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectSerializer
    
    def get_queryset(self):
        """Get projects for user's organizations."""
        user = self.request.user
        org_ids = OrganizationMember.objects.filter(
            user=user
        ).values_list('organization_id', flat=True)
        
        queryset = Project.objects.filter(
            organization_id__in=org_ids,
            status='active'
        ).select_related('created_by', 'inputs')
        
        # Filter by organization if provided
        org_id = self.request.query_params.get('organization')
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create project with optional wizard inputs."""
        serializer = CreateProjectSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        
        return Response(
            ProjectSerializer(project).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get', 'put', 'patch'])
    def inputs(self, request, pk=None):
        """Get or update project inputs."""
        project = self.get_object()
        inputs = project.inputs
        
        if request.method == 'GET':
            serializer = ProjectInputSerializer(inputs)
            return Response(serializer.data)
        
        # PUT or PATCH
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📥 Received inputs update: ai_generated_fields = {request.data.get('ai_generated_fields')}")
        
        serializer = ProjectInputSerializer(
            inputs,
            data=request.data,
            partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        
        # Track if filled manually
        if not inputs.filled_via:
            inputs.filled_via = 'manual'
        elif inputs.filled_via == 'ai_chat':
            inputs.filled_via = 'mixed'
        
        serializer.save()
        
        # Log what was saved
        logger.info(f"💾 Saved inputs: ai_generated_fields = {inputs.ai_generated_fields}")
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a project."""
        project = self.get_object()
        project.status = 'archived'
        project.save()
        return Response(ProjectSerializer(project).data)
    
    @action(detail=True, methods=['post'], url_path='inputs/generate-crunchbase-params')
    def generate_crunchbase_params(self, request, pk=None):
        """
        Generate optimized Crunchbase search parameters using AI.
        
        Uses project inputs to generate:
        - keywords: 8-12 diverse search keywords
        - target_description: 2-3 sentence description for similarity search
        """
        import asyncio
        from services.ai_functions import generate_crunchbase_params_from_inputs
        
        project = self.get_object()
        inputs = project.inputs
        
        # Check if we have minimum required inputs
        if not inputs.startup_name and not inputs.startup_description:
            return Response(
                {"error": "Please fill in at least the startup name or description first"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                generate_crunchbase_params_from_inputs(inputs)
            )
        finally:
            loop.close()
        
        if result.get("error"):
            return Response(
                {"error": result["error"]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Save the generated params to the model
        inputs.extracted_keywords = result.get("keywords", [])
        inputs.target_description = result.get("target_description", "")
        inputs.save()
        
        return Response({
            "success": True,
            "keywords": inputs.extracted_keywords,
            "target_description": inputs.target_description,
            "message": f"Generated {len(inputs.extracted_keywords)} keywords"
        })
