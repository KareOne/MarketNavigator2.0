"""
Serializers for enrichment feature API.
"""
from rest_framework import serializers
from .models import EnrichmentKeyword, EnrichmentHistory, EnrichmentSettings


class EnrichmentKeywordSerializer(serializers.ModelSerializer):
    """Serializer for EnrichmentKeyword model."""
    
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    
    class Meta:
        model = EnrichmentKeyword
        fields = [
            'id', 'keyword', 'num_companies', 'status', 'priority',
            'created_at', 'updated_at', 'created_by', 'created_by_email',
            'times_processed', 'last_processed_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'created_by_email',
            'times_processed', 'last_processed_at'
        ]


class EnrichmentKeywordCreateSerializer(serializers.Serializer):
    """Serializer for creating single or bulk keywords."""
    
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=255),
        min_length=1,
        help_text="List of keywords to add"
    )
    num_companies = serializers.IntegerField(
        default=50,
        min_value=1,
        max_value=500,
        help_text="Number of companies to scrape per keyword"
    )
    priority = serializers.IntegerField(
        default=0,
        help_text="Higher priority keywords are processed first"
    )


class EnrichmentHistorySerializer(serializers.ModelSerializer):
    """Serializer for EnrichmentHistory model."""
    
    keyword_text = serializers.CharField(source='keyword.keyword', read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = EnrichmentHistory
        fields = [
            'id', 'keyword', 'keyword_text', 'started_at', 'completed_at',
            'status', 'companies_found', 'companies_scraped', 'companies_skipped',
            'worker_id', 'task_id', 'error_message', 'duration_seconds'
        ]
    
    def get_duration_seconds(self, obj):
        if obj.completed_at and obj.started_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        return None


class EnrichmentSettingsSerializer(serializers.ModelSerializer):
    """Serializer for EnrichmentSettings model."""
    
    class Meta:
        model = EnrichmentSettings
        fields = ['is_paused', 'days_threshold', 'updated_at']
        read_only_fields = ['updated_at']


class EnrichmentStatusSerializer(serializers.Serializer):
    """Serializer for enrichment status response."""
    
    is_paused = serializers.BooleanField()
    is_active = serializers.BooleanField()
    current_keyword = serializers.CharField(allow_null=True)
    pending_count = serializers.IntegerField()
    processing_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    total_companies_scraped = serializers.IntegerField()
    idle_workers = serializers.IntegerField()
