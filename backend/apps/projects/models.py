"""
Project models with 9-question inputs.
"""
import uuid
import hashlib
from django.db import models
from django.conf import settings


class Project(models.Model):
    """Project model."""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='projects'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'projects'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class ProjectInput(models.Model):
    """Project inputs - the 9 questions."""
    
    # Keep these for reference/display purposes only - not enforced in DB
    STAGE_CHOICES = [
        ('idea', 'Idea Stage'),
        ('mvp', 'MVP Development'),
        ('early_stage', 'Early-Stage'),
        ('growth', 'Growth Stage'),
        ('scale_up', 'Scale-Up'),
    ]
    
    TIME_RANGE_CHOICES = [
        ('1mo', 'Last Month'),
        ('3mo', 'Last 3 Months'),
        ('6mo', 'Last 6 Months'),
        ('1yr', 'Last Year'),
        ('all', 'All Time'),
    ]
    
    COMPLETION_STATUS_CHOICES = [
        ('incomplete', 'Incomplete'),
        ('partial', 'Partial'),
        ('complete', 'Complete'),
    ]
    
    FILLED_VIA_CHOICES = [
        ('manual', 'Manual'),
        ('ai_chat', 'AI Chat'),
        ('mixed', 'Mixed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='inputs'
    )
    
    # The 9 input fields - all accept any text (no choice restrictions)
    startup_name = models.CharField(max_length=255, blank=True)
    startup_description = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    current_stage = models.CharField(max_length=100, blank=True)  # No choices - accepts any text
    business_model = models.TextField(blank=True)
    geographic_focus = models.CharField(max_length=255, blank=True)
    research_goal = models.TextField(blank=True)
    time_range = models.CharField(max_length=100, blank=True)  # No choices - accepts any text
    inspiration_sources = models.TextField(blank=True)
    
    # AI-generated fields
    target_description = models.TextField(blank=True)  # AI-optimized for search
    extracted_keywords = models.JSONField(default=list, blank=True)
    
    # Track which fields were filled by AI (not edited by user)
    # Format: {"startup_name": true, "target_audience": true, ...}
    ai_generated_fields = models.JSONField(default=dict, blank=True)
    
    # Metadata
    completion_status = models.CharField(
        max_length=50, 
        choices=COMPLETION_STATUS_CHOICES, 
        default='incomplete'
    )
    filled_via = models.CharField(
        max_length=50, 
        choices=FILLED_VIA_CHOICES, 
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'project_inputs'
    
    def __str__(self):
        return f"Inputs for {self.project.name}"
    
    def get_inputs_hash(self):
        """Generate hash of inputs to detect changes."""
        content = f"{self.startup_name}|{self.startup_description}|{self.target_audience}"
        content += f"|{self.current_stage}|{self.business_model}|{self.geographic_focus}"
        content += f"|{self.research_goal}|{self.time_range}|{self.inspiration_sources}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def calculate_completion(self):
        """Calculate completion status based on filled fields."""
        required_fields = [
            'startup_name', 'startup_description', 'target_audience',
            'current_stage', 'business_model', 'geographic_focus',
            'research_goal', 'time_range'
        ]
        
        filled = sum(1 for f in required_fields if getattr(self, f))
        
        if filled == 0:
            return 'incomplete'
        elif filled == len(required_fields):
            return 'complete'
        else:
            return 'partial'
    
    def save(self, *args, **kwargs):
        self.completion_status = self.calculate_completion()
        super().save(*args, **kwargs)


# Signal to create ProjectInput when Project is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Project)
def create_project_input(sender, instance, created, **kwargs):
    if created:
        ProjectInput.objects.create(project=instance)
