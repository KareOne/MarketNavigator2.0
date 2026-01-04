"""
Admin API URLs - Orchestrator monitoring and enrichment endpoints.
"""
from django.urls import path
from .views import (
    OrchestratorHealthView,
    OrchestratorWorkersView,
    OrchestratorQueueView,
    OrchestratorWorkerStatsView,
    OrchestratorTestTaskView,
    # Enrichment views
    EnrichmentKeywordListCreateView,
    EnrichmentKeywordDetailView,
    EnrichmentHistoryListView,
    EnrichmentStatusView,
    EnrichmentPauseResumeView,
    EnrichmentSettingsView,
    EnrichmentResetStuckView,
    EnrichmentCallbackView,
    # Internal orchestrator views
    EnrichmentInternalStatusView,
    EnrichmentInternalKeywordsView,
)


urlpatterns = [
    # Orchestrator endpoints
    path('orchestrator/health/', OrchestratorHealthView.as_view(), name='orchestrator-health'),
    path('orchestrator/workers/', OrchestratorWorkersView.as_view(), name='orchestrator-workers'),
    path('orchestrator/queue/', OrchestratorQueueView.as_view(), name='orchestrator-queue'),
    path('orchestrator/workers/<str:api_type>/stats/', OrchestratorWorkerStatsView.as_view(), name='orchestrator-worker-stats'),
    path('orchestrator/test-task/', OrchestratorTestTaskView.as_view(), name='orchestrator-test-task'),
    
    # Enrichment endpoints (authenticated - for frontend)
    path('enrichment/keywords/', EnrichmentKeywordListCreateView.as_view(), name='enrichment-keywords'),
    path('enrichment/keywords/<int:pk>/', EnrichmentKeywordDetailView.as_view(), name='enrichment-keyword-detail'),
    path('enrichment/history/', EnrichmentHistoryListView.as_view(), name='enrichment-history'),
    path('enrichment/status/', EnrichmentStatusView.as_view(), name='enrichment-status'),
    path('enrichment/pause-resume/', EnrichmentPauseResumeView.as_view(), name='enrichment-pause-resume'),
    path('enrichment/settings/', EnrichmentSettingsView.as_view(), name='enrichment-settings'),
    path('enrichment/reset-stuck/', EnrichmentResetStuckView.as_view(), name='enrichment-reset-stuck'),
    
    # Internal endpoints (no auth - for orchestrator)
    path('enrichment/callback/', EnrichmentCallbackView.as_view(), name='enrichment-callback'),
    path('enrichment/internal/status/', EnrichmentInternalStatusView.as_view(), name='enrichment-internal-status'),
    path('enrichment/internal/keywords/', EnrichmentInternalKeywordsView.as_view(), name='enrichment-internal-keywords'),
]

