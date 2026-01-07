"""
Admin API Views - Proxy endpoints for orchestrator monitoring.
"""
import logging
import httpx
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)

# Orchestrator URL from settings or default
ORCHESTRATOR_URL = getattr(settings, 'ORCHESTRATOR_URL', 'http://orchestrator:8010')


class OrchestratorHealthView(APIView):
    """Proxy endpoint for orchestrator health check."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{ORCHESTRATOR_URL}/health")
                if response.status_code == 200:
                    return Response(response.json())
                else:
                    return Response(
                        {"error": "Orchestrator returned error", "status_code": response.status_code},
                        status=status.HTTP_502_BAD_GATEWAY
                    )
        except Exception as e:
            logger.error(f"Failed to connect to orchestrator: {e}")
            return Response(
                {"error": "Failed to connect to orchestrator", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class OrchestratorWorkersView(APIView):
    """Proxy endpoint for orchestrator workers list."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{ORCHESTRATOR_URL}/workers")
                if response.status_code == 200:
                    return Response(response.json())
                else:
                    return Response(
                        {"error": "Orchestrator returned error"},
                        status=status.HTTP_502_BAD_GATEWAY
                    )
        except Exception as e:
            logger.error(f"Failed to get workers from orchestrator: {e}")
            return Response(
                {"error": "Failed to connect to orchestrator", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )



class OrchestratorQueueView(APIView):
    """Proxy endpoint for orchestrator queue statistics."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{ORCHESTRATOR_URL}/queue/stats")
                if response.status_code == 200:
                    return Response(response.json())
                else:
                    return Response(
                        {"error": "Orchestrator returned error"},
                        status=status.HTTP_502_BAD_GATEWAY
                    )
        except Exception as e:
            logger.error(f"Failed to get queue stats from orchestrator: {e}")
            return Response(
                {"error": "Failed to connect to orchestrator", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class OrchestratorClearQueueView(APIView):
    """Proxy endpoint to clear pending tasks or cancel a specific task."""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        api_type = request.query_params.get('api_type')
        task_id = request.query_params.get('task_id')
        
        if task_id:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.delete(f"{ORCHESTRATOR_URL}/tasks/{task_id}")
                    if response.status_code == 200:
                        return Response(response.json())
                    else:
                        return Response(
                            {"error": "Orchestrator returned error", "details": response.text},
                            status=status.HTTP_502_BAD_GATEWAY
                        )
            except Exception as e:
                logger.error(f"Failed to cancel task on orchestrator: {e}")
                return Response(
                    {"error": "Failed to connect to orchestrator", "details": str(e)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        
        elif api_type:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.delete(f"{ORCHESTRATOR_URL}/tasks/pending", params={"api_type": api_type})
                    if response.status_code == 200:
                        return Response(response.json())
                    else:
                        return Response(
                            {"error": "Orchestrator returned error", "details": response.text},
                            status=status.HTTP_502_BAD_GATEWAY
                        )
            except Exception as e:
                logger.error(f"Failed to clear queue on orchestrator: {e}")
                return Response(
                    {"error": "Failed to connect to orchestrator", "details": str(e)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        
        else:
             return Response(
                {"error": "Either api_type or task_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )



class OrchestratorWorkerStatsView(APIView):
    """Proxy endpoint for worker stats by API type."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, api_type):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{ORCHESTRATOR_URL}/workers/{api_type}/stats")
                if response.status_code == 200:
                    return Response(response.json())
                else:
                    return Response(
                        {"error": "Orchestrator returned error"},
                        status=status.HTTP_502_BAD_GATEWAY
                    )
        except Exception as e:
            logger.error(f"Failed to get worker stats from orchestrator: {e}")
            return Response(
                {"error": "Failed to connect to orchestrator", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class OrchestratorTestTaskView(APIView):
    """
    Submit a test task to a worker via orchestrator.
    Used by admin dashboard to test worker endpoints.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Submit a test task.
        
        Request body:
        {
            "api_type": "crunchbase",
            "action": "health",
            "payload": {}
        }
        """
        api_type = request.data.get('api_type', 'crunchbase')
        action = request.data.get('action', 'health')
        payload = request.data.get('payload', {})
        
        # Generate a test report ID
        import uuid
        test_report_id = f"test-{uuid.uuid4()}"
        
        # 3 hour timeout (10800 seconds)
        TIMEOUT_SECONDS = 10800
        POLL_INTERVAL = 5  # Check every 5 seconds
        
        try:
            with httpx.Client(timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=30.0)) as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/tasks/submit",
                    json={
                        "api_type": api_type,
                        "action": action,
                        "report_id": test_report_id,
                        "payload": payload,
                        "priority": 10  # High priority for tests
                    }
                )
                
                if response.status_code == 200:
                    task_data = response.json()
                    task_id = task_data.get("task_id")
                    
                    # Wait for task completion (max 3 hours)
                    import time
                    max_iterations = TIMEOUT_SECONDS // POLL_INTERVAL
                    for _ in range(max_iterations):
                        time.sleep(POLL_INTERVAL)
                        status_response = client.get(f"{ORCHESTRATOR_URL}/tasks/{task_id}")
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            task_status = status_data.get("status")
                            
                            if task_status == "completed":
                                return Response({
                                    "success": True,
                                    "task_id": task_id,
                                    "status": "completed",
                                    "result": status_data.get("result")
                                })
                            elif task_status in ("failed", "cancelled"):
                                return Response({
                                    "success": False,
                                    "task_id": task_id,
                                    "status": task_status,
                                    "error": status_data.get("error")
                                }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Timeout (should rarely happen with 3 hour limit)
                    return Response({
                        "success": False,
                        "task_id": task_id,
                        "status": "timeout",
                        "error": f"Task did not complete within {TIMEOUT_SECONDS} seconds"
                    }, status=status.HTTP_408_REQUEST_TIMEOUT)
                else:
                    return Response(
                        {"error": "Failed to submit task", "details": response.text},
                        status=status.HTTP_502_BAD_GATEWAY
                    )
        except Exception as e:
            logger.error(f"Failed to submit test task: {e}")
            return Response(
                {"error": "Failed to connect to orchestrator", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


# =============================================================================
# Enrichment Feature Views
# =============================================================================

from django.db.models import Sum
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from .models import EnrichmentKeyword, EnrichmentHistory, EnrichmentSettings
from .serializers import (
    EnrichmentKeywordSerializer,
    EnrichmentKeywordCreateSerializer,
    EnrichmentHistorySerializer,
    EnrichmentSettingsSerializer,
)


class EnrichmentKeywordListCreateView(ListCreateAPIView):
    """
    List all enrichment keywords or create new ones.
    
    GET: List all keywords with filtering options
    POST: Create single or multiple keywords
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EnrichmentKeywordSerializer
    
    def get_queryset(self):
        queryset = EnrichmentKeyword.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def post(self, request):
        """Create single or multiple keywords."""
        create_serializer = EnrichmentKeywordCreateSerializer(data=request.data)
        
        if not create_serializer.is_valid():
            return Response(create_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        keywords = create_serializer.validated_data['keywords']
        num_companies = create_serializer.validated_data['num_companies']
        priority = create_serializer.validated_data['priority']
        
        created_keywords = []
        for keyword_text in keywords:
            # Skip duplicates
            if EnrichmentKeyword.objects.filter(keyword=keyword_text, status='pending').exists():
                continue
            
            keyword = EnrichmentKeyword.objects.create(
                keyword=keyword_text,
                num_companies=num_companies,
                priority=priority,
                created_by=request.user
            )
            created_keywords.append(keyword)
        
        serializer = EnrichmentKeywordSerializer(created_keywords, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EnrichmentKeywordDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an enrichment keyword.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EnrichmentKeywordSerializer
    queryset = EnrichmentKeyword.objects.all()


class EnrichmentHistoryListView(ListCreateAPIView):
    """
    List enrichment history with filtering and pagination.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EnrichmentHistorySerializer
    
    def get_queryset(self):
        queryset = EnrichmentHistory.objects.select_related('keyword').all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by keyword
        keyword_id = self.request.query_params.get('keyword_id')
        if keyword_id:
            queryset = queryset.filter(keyword_id=keyword_id)
        
        # Limit results
        limit = self.request.query_params.get('limit', 50)
        try:
            limit = int(limit)
        except ValueError:
            limit = 50
        
        return queryset[:limit]


class EnrichmentStatusView(APIView):
    """
    Get overall enrichment status including current processing state.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        settings_obj = EnrichmentSettings.get_settings()
        
        # Get counts
        pending_count = EnrichmentKeyword.objects.filter(status='pending').count()
        processing_count = EnrichmentKeyword.objects.filter(status='processing').count()
        completed_count = EnrichmentKeyword.objects.filter(status='completed').count()
        
        # Get total companies scraped
        total_scraped = EnrichmentHistory.objects.filter(
            status='completed'
        ).aggregate(total=Sum('companies_scraped'))['total'] or 0
        
        # Get current processing keyword
        current_keyword = None
        current_processing = EnrichmentKeyword.objects.filter(status='processing').first()
        if current_processing:
            current_keyword = current_processing.keyword
        
        # Get idle crunchbase workers from orchestrator
        idle_workers = 0
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{ORCHESTRATOR_URL}/workers/crunchbase/stats")
                if response.status_code == 200:
                    stats = response.json()
                    idle_workers = stats.get('idle', 0)
        except Exception as e:
            logger.warning(f"Could not get worker stats: {e}")
        
        return Response({
            'is_paused': settings_obj.is_paused,
            'is_active': processing_count > 0,
            'current_keyword': current_keyword,
            'pending_count': pending_count,
            'processing_count': processing_count,
            'completed_count': completed_count,
            'total_companies_scraped': total_scraped,
            'idle_workers': idle_workers,
            'days_threshold': settings_obj.days_threshold,
        })


class EnrichmentPauseResumeView(APIView):
    """
    Pause or resume enrichment processing.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        action = request.data.get('action')  # 'pause' or 'resume'
        
        if action not in ['pause', 'resume']:
            return Response(
                {'error': "Action must be 'pause' or 'resume'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings_obj = EnrichmentSettings.get_settings()
        settings_obj.is_paused = (action == 'pause')
        settings_obj.updated_by = request.user
        settings_obj.save()
        
        # If pausing, update any processing keywords to paused
        if action == 'pause':
            EnrichmentKeyword.objects.filter(status='processing').update(status='paused')
            EnrichmentHistory.objects.filter(status='running').update(status='paused')
        # If resuming, set paused keywords back to pending
        elif action == 'resume':
            EnrichmentKeyword.objects.filter(status='paused').update(status='pending')
        
        return Response({
            'success': True,
            'is_paused': settings_obj.is_paused,
            'message': f"Enrichment {'paused' if settings_obj.is_paused else 'resumed'}"
        })


class EnrichmentSettingsView(APIView):
    """
    Get or update enrichment settings.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        settings_obj = EnrichmentSettings.get_settings()
        serializer = EnrichmentSettingsSerializer(settings_obj)
        return Response(serializer.data)
    
    def patch(self, request):
        settings_obj = EnrichmentSettings.get_settings()
        serializer = EnrichmentSettingsSerializer(settings_obj, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EnrichmentResetStuckView(APIView):
    """
    Reset stuck keywords that are in 'processing' status back to 'pending'.
    This is useful when a task failed without proper cleanup.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Find keywords stuck in processing
        stuck_keywords = EnrichmentKeyword.objects.filter(status='processing')
        count = stuck_keywords.count()
        
        if count == 0:
            return Response({
                'message': 'No stuck keywords found',
                'reset_count': 0
            })
        
        # Reset them to pending
        stuck_keywords.update(status='pending')
        
        # Also mark any running history entries as failed
        EnrichmentHistory.objects.filter(status='running').update(
            status='failed',
            completed_at=timezone.now(),
            error_message='Reset by admin due to stuck processing'
        )
        
        logger.info(f"Admin reset {count} stuck enrichment keywords")
        
        return Response({
            'message': f'Reset {count} stuck keyword(s) to pending',
            'reset_count': count
        })


class EnrichmentCallbackView(APIView):
    """
    Callback endpoint for orchestrator to update enrichment status.
    Called when an enrichment task starts, completes, or fails.
    """
    permission_classes = []  # No auth required - internal call from orchestrator
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'status_updates'
    
    def post(self, request):
        """
        Receive status updates from orchestrator.
        
        Request body:
        {
            "keyword_id": 123,
            "action": "start" | "complete" | "error",
            "task_id": "...",
            "worker_id": "...",
            "companies_found": 10,
            "companies_scraped": 8,
            "companies_skipped": 2,
            "error_message": "..."
        }
        """
        keyword_id = request.data.get('keyword_id')
        action = request.data.get('action')
        task_id = request.data.get('task_id')
        worker_id = request.data.get('worker_id')
        
        if not keyword_id or not action:
            return Response(
                {'error': 'keyword_id and action are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            keyword = EnrichmentKeyword.objects.get(id=keyword_id)
        except EnrichmentKeyword.DoesNotExist:
            return Response(
                {'error': 'Keyword not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if action == 'start':
            # Mark keyword as processing
            keyword.status = 'processing'
            keyword.save()
            
            # Create history entry
            EnrichmentHistory.objects.create(
                keyword=keyword,
                status='running',
                task_id=task_id,
                worker_id=worker_id
            )
            
        elif action == 'complete':
            # Update keyword
            keyword.status = 'completed'
            keyword.times_processed += 1
            keyword.last_processed_at = timezone.now()
            keyword.save()
            
            # Update history entry
            history = EnrichmentHistory.objects.filter(
                keyword=keyword,
                status='running'
            ).order_by('-started_at').first()
            
            if history:
                history.status = 'completed'
                history.completed_at = timezone.now()
                history.companies_found = request.data.get('companies_found', 0)
                history.companies_scraped = request.data.get('companies_scraped', 0)
                history.companies_skipped = request.data.get('companies_skipped', 0)
                history.save()
        
        elif action == 'error':
            # Update keyword
            keyword.status = 'failed'
            keyword.save()
            
            # Update history entry
            history = EnrichmentHistory.objects.filter(
                keyword=keyword,
                status='running'
            ).order_by('-started_at').first()
            
            if history:
                history.status = 'failed'
                history.completed_at = timezone.now()
                history.error_message = request.data.get('error_message', 'Unknown error')
                history.save()
        
        return Response({'success': True})


# =============================================================================
# Internal Orchestrator Endpoints (No Auth)
# =============================================================================

class EnrichmentInternalStatusView(APIView):
    """
    Internal status endpoint for orchestrator.
    Returns minimal status info needed for enrichment dispatch decisions.
    """
    permission_classes = []  # No auth - internal use only
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'status_updates'
    
    def get(self, request):
        settings_obj = EnrichmentSettings.get_settings()
        pending_count = EnrichmentKeyword.objects.filter(status='pending').count()
        
        return Response({
            'is_paused': settings_obj.is_paused,
            'pending_count': pending_count,
            'days_threshold': settings_obj.days_threshold,
        })


class EnrichmentInternalKeywordsView(APIView):
    """
    Internal keywords endpoint for orchestrator.
    Returns pending keywords ordered by priority.
    """
    permission_classes = []  # No auth - internal use only
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'status_updates'
    
    def get(self, request):
        keywords = EnrichmentKeyword.objects.filter(status='pending').order_by('-priority', 'created_at')[:10]
        return Response([{
            'id': k.id,
            'keyword': k.keyword,
            'num_companies': k.num_companies,
            'priority': k.priority,
        } for k in keywords])

