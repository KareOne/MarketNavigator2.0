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
