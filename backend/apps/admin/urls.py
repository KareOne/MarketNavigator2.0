"""
Admin API URLs - Orchestrator monitoring endpoints.
"""
from django.urls import path
from .views import (
    OrchestratorHealthView,
    OrchestratorWorkersView,
    OrchestratorQueueView,
    OrchestratorWorkerStatsView,
    OrchestratorTestTaskView,
)

urlpatterns = [
    path('orchestrator/health/', OrchestratorHealthView.as_view(), name='orchestrator-health'),
    path('orchestrator/workers/', OrchestratorWorkersView.as_view(), name='orchestrator-workers'),
    path('orchestrator/queue/', OrchestratorQueueView.as_view(), name='orchestrator-queue'),
    path('orchestrator/workers/<str:api_type>/stats/', OrchestratorWorkerStatsView.as_view(), name='orchestrator-worker-stats'),
    path('orchestrator/test-task/', OrchestratorTestTaskView.as_view(), name='orchestrator-test-task'),
]
