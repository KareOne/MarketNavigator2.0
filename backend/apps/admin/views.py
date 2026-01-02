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
