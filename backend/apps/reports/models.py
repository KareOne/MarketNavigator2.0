"""
Report models for 4 report types with versioning.
"""
import uuid
from django.db import models
from django.conf import settings


class Report(models.Model):
    """Report model for 4 panel types."""
    
    REPORT_TYPE_CHOICES = [
        ('crunchbase', 'Crunchbase Analysis'),
        ('tracxn', 'Tracxn Analysis'),
        ('social', 'Social Analysis'),
        ('pitch_deck', 'Pitch Deck'),
    ]
    
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('outdated', 'Outdated'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='reports'
    )
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='not_started')
    current_version = models.PositiveIntegerField(default=0)
    
    # Latest HTML content
    html_content = models.TextField(blank=True)
    html_file = models.ForeignKey(
        'files.File',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    
    # Data and metadata
    data = models.JSONField(default=dict, blank=True)
    inputs_hash = models.CharField(max_length=32, blank=True)  # To detect input changes
    
    # Progress tracking
    progress = models.PositiveIntegerField(default=0)  # 0-100
    current_step = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reports'
        unique_together = ['project', 'report_type']
        ordering = ['report_type']
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.project.name}"
    
    def check_if_outdated(self):
        """Check if inputs have changed since last run."""
        if not self.inputs_hash:
            return False
        current_hash = self.project.inputs.get_inputs_hash()
        return self.inputs_hash != current_hash


class ReportVersion(models.Model):
    """Version history for reports."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.PositiveIntegerField()
    
    # Content
    html_content = models.TextField()
    html_file = models.ForeignKey(
        'files.File',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_versions'
    )
    data_snapshot = models.JSONField(default=dict)
    
    # Changes
    changes_summary = models.TextField(blank=True)
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        db_table = 'report_versions'
        unique_together = ['report', 'version_number']
        ordering = ['-version_number']
    
    def __str__(self):
        return f"{self.report} - v{self.version_number}"


class ReportProgressStep(models.Model):
    """
    Tracks individual progress steps for report generation.
    Provides detailed timing and status for each phase of report creation.
    Scalable design - works for all report types.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='progress_steps'
    )
    
    # Step identification
    step_number = models.PositiveIntegerField()
    step_key = models.CharField(max_length=100)  # e.g., 'api_search', 'ai_analysis'
    step_name = models.CharField(max_length=255)  # Human-readable name
    step_description = models.TextField(blank=True)
    weight = models.PositiveIntegerField(default=10)  # Weight for progress calculation
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percent = models.PositiveIntegerField(default=0)  # 0-100 for this step
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)  # e.g., companies_found, errors
    details = models.JSONField(default=list, blank=True)   # Real-time sub-step details array
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'report_progress_steps'
        ordering = ['step_number']
        unique_together = ['report', 'step_key']
    
    def __str__(self):
        return f"{self.report.report_type} - {self.step_name} ({self.status})"
    
    def calculate_duration(self):
        """Calculate duration if both timestamps exist."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()
            return self.duration_seconds
        return None


class ReportAnalysisSection(models.Model):
    """
    Store individual analysis sections for Crunchbase reports.
    Each section represents one AI-generated analysis component.
    """
    
    SECTION_TYPE_CHOICES = [
        # Overview
        ('company_overview', 'Company Overview'),
        # Per-company reports
        ('tech_product', 'Technology & Product'),
        ('market_demand', 'Market Demand & Web Insights'),
        ('competitor', 'Competitor Identification'),
        ('market_funding', 'Market & Funding Insights'),
        ('growth_potential', 'Growth Potential'),
        ('swot', 'SWOT Analysis'),
        # Executive summaries
        ('tech_product_summary', 'Tech & Product Summary'),
        ('market_demand_summary', 'Market Demand Summary'),
        ('competitor_summary', 'Competitor Summary'),
        ('market_funding_summary', 'Funding Summary'),
        ('growth_potential_summary', 'Growth Summary'),
        ('swot_summary', 'SWOT Summary'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='analysis_sections'
    )
    
    section_type = models.CharField(max_length=50, choices=SECTION_TYPE_CHOICES)
    company_name = models.CharField(max_length=255, blank=True)  # For per-company sections
    
    # Content
    content_markdown = models.TextField()  # AI-generated markdown
    content_html = models.TextField(blank=True)  # Rendered HTML (optional)
    
    # Ordering
    order = models.PositiveIntegerField(default=0)
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    processing_time = models.FloatField(null=True, blank=True)  # Seconds
    
    class Meta:
        db_table = 'report_analysis_sections'
        ordering = ['order', 'company_name']
    
    def __str__(self):
        if self.company_name:
            return f"{self.get_section_type_display()} - {self.company_name}"
        return self.get_section_type_display()


class StepTimingHistory(models.Model):
    """
    Stores historical step durations for time estimation.
    Used to predict remaining time for report generation based on past runs.
    This is a shared table - not tied to specific reports, only to report types.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Step identification
    report_type = models.CharField(max_length=50, db_index=True)  # crunchbase, tracxn, etc.
    step_key = models.CharField(max_length=100, db_index=True)    # api_search, company_overview, etc.
    
    # Timing
    duration_seconds = models.FloatField()
    
    # Context for better predictions (e.g., larger datasets take longer)
    context = models.JSONField(default=dict, blank=True)  # companies_count, etc.
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'step_timing_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'step_key', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.report_type}/{self.step_key}: {self.duration_seconds:.1f}s"


