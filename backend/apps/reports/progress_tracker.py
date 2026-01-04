"""
Report Progress Tracker Service.
Scalable progress tracking for all report types with real-time WebSocket updates.
Includes connection management to prevent pool exhaustion during long-running tasks.
"""
import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db import connection
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class ReportProgressTracker:
    """
    Scalable progress tracker for all report types.
    
    Includes connection management to prevent DB pool exhaustion during
    long-running report generation tasks.
    
    Usage:
        tracker = ReportProgressTracker(report)
        tracker.initialize_steps()
        
        tracker.start_step('api_search')
        # ... do work ...
        tracker.complete_step('api_search', {'companies_found': 50})
        
        tracker.start_step('ai_analysis')
        # ... do work ...
        tracker.complete_step('ai_analysis')
    """
    
    # Define steps for each report type with weights (weights should sum to ~100)
    REPORT_STEPS = {
        'crunchbase': [
            {'key': 'init', 'name': 'Generating Keywords', 'description': 'Creating AI-powered search keywords', 'weight': 2},
            {'key': 'api_search', 'name': 'Searching Crunchbase', 'description': 'Finding similar companies', 'weight': 8},
            {'key': 'sorting', 'name': 'Ranking Results', 'description': 'Sorting by relevance', 'weight': 2},
            {'key': 'fetching_details', 'name': 'Fetching Company Details', 'description': 'Scraping company data', 'weight': 4},
            {'key': 'company_overview', 'name': 'Company Overview', 'description': 'Generating market overview', 'weight': 6},
            {'key': 'tech_product', 'name': 'Technology & Product Analysis', 'description': 'Analyzing tech stack and products', 'weight': 10},
            {'key': 'market_demand', 'name': 'Market Demand Analysis', 'description': 'Evaluating web traffic and demand', 'weight': 10},
            {'key': 'competitor', 'name': 'Competitor Analysis', 'description': 'Mapping competitive landscape', 'weight': 10},
            {'key': 'market_funding', 'name': 'Funding Analysis', 'description': 'Analyzing funding and investors', 'weight': 10},
            {'key': 'growth_potential', 'name': 'Growth Analysis', 'description': 'Assessing growth opportunities', 'weight': 10},
            {'key': 'swot', 'name': 'SWOT Analysis', 'description': 'Strategic SWOT assessment', 'weight': 10},
            {'key': 'summaries', 'name': 'Executive Summaries', 'description': 'Generating category summaries', 'weight': 6},
            {'key': 'html_gen', 'name': 'Generating Report', 'description': 'Creating HTML report', 'weight': 2},
            {'key': 'save', 'name': 'Saving', 'description': 'Saving report and analysis sections', 'weight': 2},
        ],
        'tracxn': [
            {'key': 'init', 'name': 'Generating Keywords', 'description': 'Creating AI-powered search keywords', 'weight': 3},
            {'key': 'api_search', 'name': 'Searching Tracxn', 'description': 'Finding similar startups', 'weight': 15},
            {'key': 'sorting', 'name': 'Ranking Results', 'description': 'Sorting by relevance and scoring', 'weight': 3},
            {'key': 'fetching_details', 'name': 'Fetching Startup Details', 'description': 'Scraping detailed startup data', 'weight': 10},
            {'key': 'competitor', 'name': 'Competitor Analysis', 'description': 'Analyzing competitive landscape per startup', 'weight': 15},
            {'key': 'market_funding', 'name': 'Market & Funding Analysis', 'description': 'Evaluating funding patterns and market fit', 'weight': 15},
            {'key': 'growth_potential', 'name': 'Growth Potential Analysis', 'description': 'Assessing growth signals and scalability', 'weight': 15},
            {'key': 'summaries', 'name': 'Executive Summaries', 'description': 'Generating category summaries', 'weight': 12},
            {'key': 'html_gen', 'name': 'Generating Report', 'description': 'Creating HTML report', 'weight': 6},
            {'key': 'save', 'name': 'Saving', 'description': 'Saving report and analysis sections', 'weight': 6},
        ],
        'social': [
            {'key': 'init', 'name': 'Generating Keywords', 'description': 'Creating AI-powered social search keywords', 'weight': 5},
            {'key': 'api_search', 'name': 'Searching Twitter', 'description': 'Searching for relevant discussions and tweets', 'weight': 35},
            {'key': 'analysis', 'name': 'Analyzing Tweets', 'description': 'analyzing market sentiment and customer needs', 'weight': 55},
            {'key': 'save', 'name': 'Saving', 'description': 'Saving report and analysis sections', 'weight': 5},
        ],
        'pitch_deck': [
            {'key': 'init', 'name': 'Initializing', 'description': 'Gathering project data', 'weight': 10},
            {'key': 'gather_data', 'name': 'Gathering Reports', 'description': 'Collecting Crunchbase and Tracxn data', 'weight': 15},
            {'key': 'ai_generation', 'name': 'Generating Slides', 'description': 'Creating slide content with AI', 'weight': 45},
            {'key': 'html_gen', 'name': 'Generating HTML', 'description': 'Creating presentation slides', 'weight': 20},
            {'key': 'save', 'name': 'Saving', 'description': 'Saving pitch deck', 'weight': 10},
        ],
    }
    
    # Number of DB operations before triggering connection cleanup
    CONNECTION_CLEANUP_INTERVAL = 10
    
    def __init__(self, report):
        """
        Initialize tracker for a report.
        
        Args:
            report: Report model instance
        """
        self.report = report
        self.steps_config = self.REPORT_STEPS.get(report.report_type, [])
        self._channel_layer = None
        self._operation_count = 0  # Track DB operations for periodic cleanup
    
    @property
    def channel_layer(self):
        """Lazy load channel layer."""
        if self._channel_layer is None:
            self._channel_layer = get_channel_layer()
        return self._channel_layer
    
    def _maybe_cleanup_connection(self):
        """Periodically close DB connection to prevent pool exhaustion."""
        self._operation_count += 1
        if self._operation_count >= self.CONNECTION_CLEANUP_INTERVAL:
            connection.close()
            self._operation_count = 0
            logger.debug("Progress tracker: Released DB connection")
    
    def initialize_steps(self) -> List:
        """
        Create all step records in pending state.
        Clears any existing steps from previous runs.
        
        Returns:
            List of created ReportProgressStep instances
        """
        from .models import ReportProgressStep
        
        # Delete existing steps from previous runs
        ReportProgressStep.objects.filter(report=self.report).delete()
        
        created_steps = []
        for i, step_config in enumerate(self.steps_config):
            step = ReportProgressStep.objects.create(
                report=self.report,
                step_number=i + 1,
                step_key=step_config['key'],
                step_name=step_config['name'],
                step_description=step_config.get('description', ''),
                weight=step_config.get('weight', 10),
                status='pending'
            )
            created_steps.append(step)
        
        logger.info(f"📋 Initialized {len(created_steps)} progress steps for {self.report.report_type}")
        self._maybe_cleanup_connection()  # Release connection after batch of creates
        self._broadcast_update()
        return created_steps
    
    def start_step(self, step_key: str) -> Optional['ReportProgressStep']:
        """
        Mark a step as running and record start time.
        
        Args:
            step_key: The key identifier for the step
            
        Returns:
            The updated ReportProgressStep instance
        """
        from .models import ReportProgressStep
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.status = 'running'
            step.started_at = timezone.now()
            step.save(update_fields=['status', 'started_at', 'updated_at'])
            
            # Update report's current_step
            self.report.current_step = step.step_name
            self.report.progress = self._calculate_overall_progress()
            self.report.save(update_fields=['current_step', 'progress', 'updated_at'])
            
            logger.info(f"▶️ Started step: {step.step_name}")
            self._maybe_cleanup_connection()
            self._broadcast_update()
            return step
        except ReportProgressStep.DoesNotExist:
            logger.warning(f"⚠️ Step not found: {step_key}")
            return None
    
    def update_step_progress(self, step_key: str, progress_percent: int):
        """
        Update the progress percentage of a running step.
        
        Args:
            step_key: The key identifier for the step
            progress_percent: Progress within this step (0-100)
        """
        from .models import ReportProgressStep
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.progress_percent = min(100, max(0, progress_percent))
            step.save(update_fields=['progress_percent', 'updated_at'])
            
            # Update overall progress
            self.report.progress = self._calculate_overall_progress()
            self.report.save(update_fields=['progress', 'updated_at'])
            
            self._broadcast_update()
        except ReportProgressStep.DoesNotExist:
            pass
    
    def update_step_message(self, step_key: str, message: str, progress_percent: int = None):
        """
        Update the message/description of a running step dynamically.
        This allows showing detailed status like "Searching keyword 3/12: 'fintech'"
        
        Args:
            step_key: The key identifier for the step
            message: New message to display for this step
            progress_percent: Optional progress update (0-100)
        """
        from .models import ReportProgressStep
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.step_description = message
            update_fields = ['step_description', 'updated_at']
            
            if progress_percent is not None:
                step.progress_percent = min(100, max(0, progress_percent))
                update_fields.append('progress_percent')
            
            step.save(update_fields=update_fields)
            
            # Update report's current_step to show the message
            self.report.current_step = message
            self.report.save(update_fields=['current_step', 'updated_at'])
            
            self._broadcast_update()
        except ReportProgressStep.DoesNotExist:
            pass
    
    def add_step_detail(self, step_key: str, detail_type: str, message: str, data: Dict[str, Any] = None):
        """
        Add a real-time detail item to a step's details array.
        This is used to show granular progress like individual keyword searches.
        
        Args:
            step_key: The key identifier for the step
            detail_type: Type of detail (e.g., 'keywords', 'search_result', 'company_found')
            message: Human-readable message
            data: Optional data to include (e.g., {'count': 20, 'companies': [...]})
        """
        from .models import ReportProgressStep
        import time
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            
            # Build detail item
            detail_item = {
                'type': detail_type,
                'message': message,
                'timestamp': time.time(),
            }
            if data:
                detail_item['data'] = data
            
            # Append to details array (limit to last 50 items to prevent bloat)
            details = step.details or []
            details.append(detail_item)
            if len(details) > 50:
                details = details[-50:]
            
            step.details = details
            step.save(update_fields=['details', 'updated_at'])
            
            logger.info(f"📝 Added detail to step {step_key}: {detail_type} - {message[:50]}...")
            
            self._maybe_cleanup_connection()  # Periodic cleanup for frequent detail adds
            self._broadcast_update()
        except ReportProgressStep.DoesNotExist:
            logger.warning(f"⚠️ Step {step_key} not found for adding detail")
    
    def clear_step_details(self, step_key: str):
        """Clear all details for a step (useful when restarting)."""
        from .models import ReportProgressStep
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.details = []
            step.save(update_fields=['details', 'updated_at'])
        except ReportProgressStep.DoesNotExist:
            pass
    
    def complete_step(self, step_key: str, metadata: Dict[str, Any] = None) -> Optional['ReportProgressStep']:
        """
        Mark a step as completed and record end time.
        Also records timing for future predictions.
        
        Args:
            step_key: The key identifier for the step
            metadata: Optional metadata to store (e.g., {'companies_found': 50})
            
        Returns:
            The updated ReportProgressStep instance
        """
        from .models import ReportProgressStep
        from .time_estimator import TimeEstimator
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.progress_percent = 100
            if metadata:
                step.metadata = metadata
            step.calculate_duration()
            # Use update_fields to avoid overwriting 'details' added by real-time updates
            update_fields = ['status', 'completed_at', 'progress_percent', 'duration_seconds', 'updated_at']
            if metadata:
                update_fields.append('metadata')
            step.save(update_fields=update_fields)
            
            # Record timing for future predictions
            if step.duration_seconds and step.duration_seconds > 0:
                TimeEstimator.record_step_completion(
                    report_type=self.report.report_type,
                    step_key=step_key,
                    duration_seconds=step.duration_seconds,
                    context=metadata
                )
            
            # Update overall progress
            self.report.progress = self._calculate_overall_progress()
            self.report.save(update_fields=['progress', 'updated_at'])
            
            duration_str = f"{step.duration_seconds:.1f}s" if step.duration_seconds else "N/A"
            logger.info(f"✅ Completed step: {step.step_name} (duration: {duration_str})")
            self._maybe_cleanup_connection()
            self._broadcast_update()
            return step
        except ReportProgressStep.DoesNotExist:
            logger.warning(f"⚠️ Step not found: {step_key}")
            return None
    
    def fail_step(self, step_key: str, error_message: str) -> Optional['ReportProgressStep']:
        """
        Mark a step as failed with an error message.
        
        Args:
            step_key: The key identifier for the step
            error_message: Description of the error
            
        Returns:
            The updated ReportProgressStep instance
        """
        from .models import ReportProgressStep
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.status = 'failed'
            step.completed_at = timezone.now()
            step.error_message = error_message
            step.calculate_duration()
            # Use update_fields to avoid overwriting 'details' added by real-time updates
            step.save(update_fields=['status', 'completed_at', 'error_message', 'duration_seconds', 'updated_at'])
            
            logger.error(f"❌ Failed step: {step.step_name} - {error_message}")
            self._broadcast_update()
            return step
        except ReportProgressStep.DoesNotExist:
            logger.warning(f"⚠️ Step not found: {step_key}")
            return None
    
    def skip_step(self, step_key: str, reason: str = "") -> Optional['ReportProgressStep']:
        """
        Mark a step as skipped.
        
        Args:
            step_key: The key identifier for the step
            reason: Optional reason for skipping
            
        Returns:
            The updated ReportProgressStep instance
        """
        from .models import ReportProgressStep
        
        try:
            step = ReportProgressStep.objects.get(report=self.report, step_key=step_key)
            step.status = 'skipped'
            step.completed_at = timezone.now()
            step.progress_percent = 100
            if reason:
                step.metadata = {'skip_reason': reason}
            # Use update_fields to avoid overwriting 'details' added by real-time updates
            update_fields = ['status', 'completed_at', 'progress_percent', 'updated_at']
            if reason:
                update_fields.append('metadata')
            step.save(update_fields=update_fields)
            
            logger.info(f"⏭️ Skipped step: {step.step_name}")
            self._broadcast_update()
            return step
        except ReportProgressStep.DoesNotExist:
            return None
    
    def _calculate_overall_progress(self) -> int:
        """
        Calculate weighted overall progress based on step completions.
        
        Returns:
            Overall progress percentage (0-100)
        """
        from .models import ReportProgressStep
        
        steps = ReportProgressStep.objects.filter(report=self.report)
        
        if not steps.exists():
            return 0
        
        total_weight = sum(s.weight for s in steps)
        if total_weight == 0:
            return 0
        
        weighted_progress = 0
        for step in steps:
            if step.status == 'completed':
                weighted_progress += step.weight * 100
            elif step.status == 'running':
                weighted_progress += step.weight * step.progress_percent
            elif step.status == 'skipped':
                weighted_progress += step.weight * 100
            # pending and failed contribute 0
        
        return int(weighted_progress / total_weight)
    
    def get_steps_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all steps for WebSocket broadcast.
        
        Returns:
            List of step dictionaries with status and timing info
        """
        from .models import ReportProgressStep
        
        steps = ReportProgressStep.objects.filter(report=self.report).order_by('step_number')
        
        return [
            {
                'step_number': s.step_number,
                'step_key': s.step_key,
                'step_name': s.step_name,
                'step_description': s.step_description,
                'status': s.status,
                'progress_percent': s.progress_percent,
                'started_at': s.started_at.isoformat() if s.started_at else None,
                'completed_at': s.completed_at.isoformat() if s.completed_at else None,
                'duration_seconds': s.duration_seconds,
                'metadata': s.metadata,
                'details': s.details or [],  # Real-time sub-step details
                'error_message': s.error_message,
            }
            for s in steps
        ]
    
    def _broadcast_update(self):
        """Send progress update via WebSocket to all connected clients."""
        try:
            from .time_estimator import TimeEstimator
            
            project_id = str(self.report.project_id)
            steps_summary = self.get_steps_summary()
            
            # Find current running step
            current_step_key = None
            current_step_name = None
            for step in steps_summary:
                if step['status'] == 'running':
                    current_step_key = step['step_key']
                    current_step_name = step['step_name']
                    break
            
            # Get time estimate
            try:
                estimate = TimeEstimator.get_estimates_dict(self.report)
            except Exception as e:
                logger.warning(f"Failed to get time estimate: {e}")
                estimate = None
            
            async_to_sync(self.channel_layer.group_send)(
                f"project_{project_id}",
                {
                    "type": "report_progress",
                    "report_type": self.report.report_type,
                    "report_id": str(self.report.id),
                    "progress": self.report.progress,
                    "current_step": current_step_name or self.report.current_step,
                    "step_key": current_step_key,
                    "status": self.report.status,
                    "steps": steps_summary,
                    "time_estimate": estimate,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast progress update: {e}")

