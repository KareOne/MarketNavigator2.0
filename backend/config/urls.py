"""
URL configuration for MarketNavigator v2.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.utils import timezone


def health_check(request):
    """Health check endpoint for Docker/Kubernetes."""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': '2.0.0',
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Health check
    path('api/health/', health_check, name='health_check'),
    
    # API endpoints
    path('api/auth/', include('apps.users.urls')),
    path('api/organizations/', include('apps.organizations.urls')),
    path('api/projects/', include('apps.projects.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/chat/', include('apps.chat.urls')),
    path('api/share/', include('apps.sharing.urls')),
    path('api/files/', include('apps.files.urls')),
    path('api/admin/', include('apps.admin.urls')),  # Admin/monitoring endpoints
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

