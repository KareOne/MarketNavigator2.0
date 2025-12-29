"""
Report URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('project/<uuid:project_id>/', views.ReportViewSet.as_view({
        'get': 'list',
    }), name='report-list'),
    path('project/<uuid:project_id>/<uuid:pk>/', views.ReportViewSet.as_view({
        'get': 'retrieve',
    }), name='report-detail'),
    path('project/<uuid:project_id>/<uuid:pk>/start/', views.ReportViewSet.as_view({
        'post': 'start',
    }), name='report-start'),
    path('project/<uuid:project_id>/<uuid:pk>/versions/', views.ReportViewSet.as_view({
        'get': 'versions',
    }), name='report-versions'),
    path('project/<uuid:project_id>/<uuid:pk>/compare/', views.ReportViewSet.as_view({
        'get': 'compare',
    }), name='report-compare'),
    # Internal API for crunchbase_api container to send status updates
    path('status-update/', views.StatusUpdateView.as_view(), name='report-status-update'),
]
