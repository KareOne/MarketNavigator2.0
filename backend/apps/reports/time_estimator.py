"""
Time Estimation Service for Report Generation.
Uses historical step timing data to predict remaining time.
Designed to be reusable across all report types.
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@dataclass
class StepEstimate:
    """Estimate for a single step."""
    step_key: str
    step_name: str
    avg_duration: float  # seconds
    sample_count: int
    confidence: str  # high, medium, low
    is_completed: bool
    is_running: bool
    actual_duration: Optional[float] = None


@dataclass  
class TimeEstimate:
    """Complete time estimation for a report."""
    total_estimated_seconds: float
    remaining_seconds: float
    elapsed_seconds: float
    confidence: str  # high, medium, low
    steps: List[StepEstimate]
    progress_percent: int


class TimeEstimator:
    """
    Service for estimating report generation time using historical data.
    
    Algorithm:
    - Fetches last N completions per step
    - Calculates weighted average (recent runs = higher weight)
    - Adjusts based on context (e.g., company count)
    - Returns estimate with confidence level
    """
    
    # How many historical samples to consider
    SAMPLE_SIZE = 20
    
    # Default durations (seconds) when no history exists
    DEFAULT_DURATIONS = {
        'crunchbase': {
            'init': 3,
            'api_search': 120,
            'company_overview': 20,
            'tech_product': 90,
            'market_demand': 90,
            'competitor': 90,
            'market_funding': 90,
            'growth_potential': 90,
            'swot': 90,
            'summaries': 60,
            'html_gen': 5,
            'save': 3,
        },
        'tracxn': {
            'init': 3,
            'api_search': 180,
            'data_parse': 10,
            'html_gen': 5,
            'save': 3,
        },
        'pitch_deck': {
            'init': 5,
            'gather_data': 10,
            'ai_generation': 120,
            'html_gen': 10,
            'save': 5,
        },
    }
    
    def __init__(self, report_type: str):
        """Initialize estimator for a specific report type."""
        self.report_type = report_type
        self._cache = {}
        self._cache_time = None
    
    def get_step_average(self, step_key: str, context: Dict = None) -> tuple[float, int, str]:
        """
        Get average duration for a step.
        
        Returns:
            Tuple of (avg_seconds, sample_count, confidence)
        """
        from .models import StepTimingHistory
        
        # Get historical data
        records = StepTimingHistory.objects.filter(
            report_type=self.report_type,
            step_key=step_key
        ).order_by('-created_at')[:self.SAMPLE_SIZE]
        
        records_list = list(records)
        count = len(records_list)
        
        if count == 0:
            # Use default
            default = self.DEFAULT_DURATIONS.get(self.report_type, {}).get(step_key, 30)
            return (default, 0, 'low')
        
        # Calculate weighted average (more recent = higher weight)
        # Weight formula: w = (SAMPLE_SIZE - index) / sum(1..SAMPLE_SIZE)
        weight_sum = sum(range(1, count + 1))
        weighted_sum = 0
        
        for i, record in enumerate(records_list):
            weight = (count - i) / weight_sum
            weighted_sum += record.duration_seconds * weight
        
        # Determine confidence based on sample size
        if count >= 10:
            confidence = 'high'
        elif count >= 5:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return (weighted_sum, count, confidence)
    
    def estimate_remaining(self, report) -> TimeEstimate:
        """
        Estimate remaining time for a report.
        
        Args:
            report: Report model instance with progress_steps
            
        Returns:
            TimeEstimate with breakdown
        """
        from .models import ReportProgressStep
        
        steps = ReportProgressStep.objects.filter(report=report).order_by('step_number')
        
        step_estimates = []
        total_estimated = 0
        remaining = 0
        elapsed = 0
        
        lowest_confidence = 'high'
        
        for step in steps:
            avg_duration, sample_count, confidence = self.get_step_average(step.step_key)
            
            is_completed = step.status in ('completed', 'skipped')
            is_running = step.status == 'running'
            actual = step.duration_seconds
            
            estimate = StepEstimate(
                step_key=step.step_key,
                step_name=step.step_name,
                avg_duration=avg_duration,
                sample_count=sample_count,
                confidence=confidence,
                is_completed=is_completed,
                is_running=is_running,
                actual_duration=actual
            )
            step_estimates.append(estimate)
            
            total_estimated += avg_duration
            
            if is_completed:
                elapsed += actual if actual else avg_duration
            elif is_running:
                # For running step, estimate remaining time
                if step.started_at:
                    step_elapsed = (timezone.now() - step.started_at).total_seconds()
                    # Remaining = max(0, estimated - elapsed)
                    step_remaining = max(0, avg_duration - step_elapsed)
                    remaining += step_remaining
                    elapsed += step_elapsed
                else:
                    remaining += avg_duration
            else:
                # Pending
                remaining += avg_duration
            
            # Track lowest confidence
            if confidence == 'low':
                lowest_confidence = 'low'
            elif confidence == 'medium' and lowest_confidence == 'high':
                lowest_confidence = 'medium'
        
        # Calculate overall progress
        if total_estimated > 0:
            progress = int((elapsed / total_estimated) * 100)
            progress = min(99, max(0, progress))  # Cap at 99% until completed
        else:
            progress = 0
        
        return TimeEstimate(
            total_estimated_seconds=total_estimated,
            remaining_seconds=remaining,
            elapsed_seconds=elapsed,
            confidence=lowest_confidence,
            steps=step_estimates,
            progress_percent=progress
        )
    
    @classmethod
    def record_step_completion(cls, report_type: str, step_key: str, 
                               duration_seconds: float, context: Dict = None):
        """
        Record a step completion for future predictions.
        Called when a step completes successfully.
        """
        from .models import StepTimingHistory
        
        if duration_seconds <= 0:
            return
        
        try:
            StepTimingHistory.objects.create(
                report_type=report_type,
                step_key=step_key,
                duration_seconds=duration_seconds,
                context=context or {}
            )
            logger.debug(f"Recorded timing: {report_type}/{step_key} = {duration_seconds:.1f}s")
        except Exception as e:
            logger.warning(f"Failed to record step timing: {e}")
    
    @classmethod
    def get_estimates_dict(cls, report) -> Dict[str, Any]:
        """
        Get estimates as a dictionary for API response.
        """
        estimator = cls(report.report_type)
        estimate = estimator.estimate_remaining(report)
        
        return {
            'total_estimated_seconds': round(estimate.total_estimated_seconds, 1),
            'remaining_seconds': round(estimate.remaining_seconds, 1),
            'elapsed_seconds': round(estimate.elapsed_seconds, 1),
            'confidence': estimate.confidence,
            'progress_percent': estimate.progress_percent,
            'steps': [
                {
                    'step_key': s.step_key,
                    'step_name': s.step_name,
                    'avg_duration': round(s.avg_duration, 1),
                    'sample_count': s.sample_count,
                    'confidence': s.confidence,
                    'is_completed': s.is_completed,
                    'is_running': s.is_running,
                    'actual_duration': round(s.actual_duration, 1) if s.actual_duration else None,
                }
                for s in estimate.steps
            ]
        }
