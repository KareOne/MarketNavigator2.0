"""
Project serializers.
"""
from rest_framework import serializers
from .models import Project, ProjectInput


class ProjectInputSerializer(serializers.ModelSerializer):
    """Serializer for project inputs (9 questions)."""
    
    inputs_hash = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectInput
        fields = [
            'id',
            'startup_name', 'startup_description', 'target_audience',
            'current_stage', 'business_model', 'geographic_focus',
            'research_goal', 'time_range', 'inspiration_sources',
            'target_description', 'extracted_keywords',
            'ai_generated_fields',  # Track which fields were filled by AI
            'completion_status', 'filled_via',
            'inputs_hash', 'updated_at'
        ]
        read_only_fields = ['id', 'completion_status', 'inputs_hash', 'updated_at']
    
    def get_inputs_hash(self, obj):
        return obj.get_inputs_hash()


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for projects."""
    
    inputs = ProjectInputSerializer(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status',
            'created_by', 'created_by_name',
            'inputs',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.username
        return None


class CreateProjectSerializer(serializers.Serializer):
    """Serializer for creating a project with wizard inputs."""
    
    organization_id = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    
    # Optional initial inputs from wizard
    startup_name = serializers.CharField(required=False, allow_blank=True)
    startup_description = serializers.CharField(required=False, allow_blank=True)
    target_audience = serializers.CharField(required=False, allow_blank=True)
    current_stage = serializers.CharField(required=False, allow_blank=True)  # No choices - accepts any text
    business_model = serializers.CharField(required=False, allow_blank=True)
    geographic_focus = serializers.CharField(required=False, allow_blank=True)
    research_goal = serializers.CharField(required=False, allow_blank=True)
    time_range = serializers.CharField(required=False, allow_blank=True)  # No choices - accepts any text
    inspiration_sources = serializers.CharField(required=False, allow_blank=True)
    
    def create(self, validated_data):
        from apps.organizations.models import Organization
        
        user = self.context['request'].user
        org_id = validated_data.pop('organization_id')
        
        # Separate project data from input data
        input_fields = [
            'startup_name', 'startup_description', 'target_audience',
            'current_stage', 'business_model', 'geographic_focus',
            'research_goal', 'time_range', 'inspiration_sources'
        ]
        input_data = {k: validated_data.pop(k, '') for k in input_fields}
        
        # Create project
        org = Organization.objects.get(id=org_id)
        project = Project.objects.create(
            organization=org,
            created_by=user,
            **validated_data
        )
        
        # Update inputs if provided
        if any(input_data.values()):
            inputs = project.inputs
            for field, value in input_data.items():
                if value:
                    setattr(inputs, field, value)
            inputs.filled_via = 'manual'
            inputs.save()
        
        return project
