"""
Report serializers.
"""
from rest_framework import serializers
from .models import Report, ReportVersion, ReportProgressStep, ReportAnalysisSection


class ReportAnalysisSectionSerializer(serializers.ModelSerializer):
    """Serializer for report analysis sections."""
    
    section_type_display = serializers.CharField(source='get_section_type_display', read_only=True)
    
    class Meta:
        model = ReportAnalysisSection
        fields = [
            'id', 'section_type', 'section_type_display', 'company_name',
            'content_markdown', 'order', 'generated_at', 'processing_time'
        ]


class ReportProgressStepSerializer(serializers.ModelSerializer):
    """Serializer for report progress steps."""
    
    class Meta:
        model = ReportProgressStep
        fields = [
            'step_number', 'step_key', 'step_name', 'step_description',
            'status', 'progress_percent', 'weight',
            'started_at', 'completed_at', 'duration_seconds',
            'metadata', 'details', 'error_message'
        ]


class ReportVersionSerializer(serializers.ModelSerializer):
    """Serializer for report versions."""
    
    generated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportVersion
        fields = [
            'id', 'version_number', 
            'html_content', 'data_snapshot', 'changes_summary',
            'generated_at', 'generated_by', 'generated_by_name'
        ]
    
    def get_generated_by_name(self, obj):
        if obj.generated_by:
            return obj.generated_by.full_name or obj.generated_by.username
        return None


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for reports."""
    
    is_outdated = serializers.SerializerMethodField()
    progress_steps = ReportProgressStepSerializer(many=True, read_only=True)
    analysis_sections = ReportAnalysisSectionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'status', 'current_version',
            'html_content', 'data',
            'progress', 'current_step', 'error_message',
            'inputs_hash', 'is_outdated',
            'progress_steps', 'analysis_sections',
            'started_at', 'completed_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'current_version',
            'html_content', 'data',
            'progress', 'current_step', 'error_message',
            'inputs_hash', 'is_outdated',
            'progress_steps', 'analysis_sections',
            'started_at', 'completed_at', 'updated_at'
        ]
    
    def get_is_outdated(self, obj):
        return obj.check_if_outdated()


class ReportListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing reports."""
    
    is_outdated = serializers.SerializerMethodField()
    progress_steps = ReportProgressStepSerializer(many=True, read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'status', 'current_version',
            'progress', 'current_step', 'is_outdated',
            'progress_steps', 'html_content',  # Added html_content for View Report button
            'completed_at', 'updated_at'
        ]
    
    def get_is_outdated(self, obj):
        return obj.check_if_outdated()

