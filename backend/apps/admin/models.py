"""
Django models for database enrichment feature.
Manages admin-defined keywords and enrichment history.
"""
from django.db import models
from django.conf import settings


class EnrichmentKeyword(models.Model):
    """Admin-defined keywords for background database enrichment."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('failed', 'Failed'),
    ]
    
    keyword = models.CharField(max_length=255)
    num_companies = models.IntegerField(
        default=50,
        help_text="Number of companies to scrape for this keyword"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority keywords are processed first"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='enrichment_keywords'
    )
    
    # Tracking fields
    times_processed = models.IntegerField(default=0)
    last_processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.keyword} ({self.status})"


class EnrichmentHistory(models.Model):
    """Log of enrichment task executions."""
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('paused', 'Paused'),
    ]
    
    keyword = models.ForeignKey(
        EnrichmentKeyword,
        on_delete=models.CASCADE,
        related_name='history'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='running'
    )
    
    # Results tracking
    companies_found = models.IntegerField(default=0)
    companies_scraped = models.IntegerField(default=0)
    companies_skipped = models.IntegerField(
        default=0,
        help_text="Companies skipped due to freshness"
    )
    
    # Execution details
    worker_id = models.CharField(max_length=100, null=True, blank=True)
    task_id = models.CharField(max_length=100, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name_plural = 'Enrichment histories'
    
    def __str__(self):
        return f"{self.keyword.keyword} - {self.started_at} ({self.status})"


class EnrichmentSettings(models.Model):
    """Global settings for enrichment feature. Singleton pattern."""
    
    is_paused = models.BooleanField(
        default=False,
        help_text="When True, no new enrichment tasks will be dispatched"
    )
    days_threshold = models.IntegerField(
        default=180,
        help_text="Skip companies scraped within this many days"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name_plural = 'Enrichment settings'
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
