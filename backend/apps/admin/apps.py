"""
Admin app configuration.
"""
from django.apps import AppConfig


class AdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.admin'
    label = 'admin_panel'  # Use a unique label to avoid conflict with django.contrib.admin
    verbose_name = 'Admin Panel'
