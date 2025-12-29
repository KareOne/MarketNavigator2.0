"""
Sharing URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('report/<uuid:report_id>/create/', views.create_share_link, name='create-share-link'),
    path('report/<uuid:report_id>/links/', views.list_share_links, name='list-share-links'),
    path('link/<str:token>/deactivate/', views.deactivate_share_link, name='deactivate-share-link'),
    path('r/<str:token>/', views.view_shared_report, name='view-shared-report'),
    path('r/<str:token>/download/', views.download_shared_report, name='download-shared-report'),
]
