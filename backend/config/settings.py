"""
Django settings for MarketNavigator v2 - High-Scale Production Configuration.

Based on HIGH_SCALE_ARCHITECTURE_PLAN.md and FINAL_ARCHITECTURE_SPECIFICATION.md
"""

import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', '0') == '1'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,backend').split(',')

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',
    'django_filters',
    'storages',  # S3 storage
    'drf_spectacular',  # API documentation
    
    # Local apps
    'apps.users',
    'apps.organizations',
    'apps.projects',
    'apps.reports',
    'apps.chat',
    'apps.sharing',
    'apps.files',
    'apps.audit',  # Audit logging
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.AuditMiddleware',  # Custom audit logging
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# =============================================================================
# DATABASE - PostgreSQL with Connection Pooling
# Per HIGH_SCALE_ARCHITECTURE_PLAN.md
# =============================================================================
DATABASES = {
    'default': {
        'ENGINE': 'dj_db_conn_pool.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'postgres'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'POOL_OPTIONS': {
            'POOL_SIZE': 10,  # Min connections
            'MAX_OVERFLOW': 20,  # Additional connections under load
            'RECYCLE': 300,  # Recycle connections after 5 minutes
            'PRE_PING': True,  # Verify connection before use
        },
        'CONN_MAX_AGE': None,  # Managed by pool
    }
}

# =============================================================================
# CACHING - Redis Cluster Configuration
# Per HIGH_SCALE_ARCHITECTURE_PLAN.md Cache Strategy
# =============================================================================
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'mn2',
    },
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"{REDIS_URL.rsplit('/', 1)[0]}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'mn2_session',
    },
}

# Cache TTL Settings (per HIGH_SCALE_ARCHITECTURE_PLAN)
CACHE_TTL = {
    'user_session': 60 * 60 * 24,  # 24 hours
    'api_response': 60 * 5,  # 5 minutes
    'research_results': 60 * 60 * 24,  # 24 hours
    'company_data': 60 * 60 * 24 * 7,  # 7 days
    'project_data': 60 * 60,  # 1 hour
}

# Use Redis for session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

# =============================================================================
# CHANNELS - WebSocket with Redis
# =============================================================================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
            'capacity': 1000,
            'expiry': 60,
        },
    },
}

# =============================================================================
# CELERY - Task Queue Configuration
# =============================================================================
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
# Time limits must exceed orchestrator TASK_TIMEOUT (2 hours) since Celery waits for orchestrator
CELERY_TASK_TIME_LIMIT = 3 * 60 * 60  # 3 hours max
CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_CONCURRENCY', '4'))
CELERY_TASK_SOFT_TIME_LIMIT = int(2.5 * 60 * 60)  # 2.5 hours soft limit

# Celery Beat scheduled tasks
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-tokens': {
        'task': 'apps.sharing.tasks.cleanup_expired_tokens',
        'schedule': 60 * 60,  # Every hour
    },
    'cleanup-old-audit-logs': {
        'task': 'apps.audit.tasks.cleanup_old_logs',
        'schedule': 60 * 60 * 24,  # Daily
    },
}

# =============================================================================
# S3 / OBJECT STORAGE - Per UI_AND_STORAGE_SPECIFICATIONS.md
# =============================================================================
USE_S3 = os.getenv('USE_S3', 'True').lower() == 'true'

if USE_S3:
    # S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'minioadmin')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'minioadmin')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'marketnavigator-files')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', 'http://minio:9000')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour presigned URL expiry
    
    # Storage backends
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

# S3 Bucket Structure (per UI_AND_STORAGE_SPECIFICATIONS.md)
S3_PATHS = {
    'organizations': 'organizations/{org_id}',
    'projects': 'organizations/{org_id}/projects/{project_id}',
    'reports': 'organizations/{org_id}/projects/{project_id}/reports/{report_type}',
    'uploads': 'organizations/{org_id}/projects/{project_id}/uploads',
    'pitch_decks': 'organizations/{org_id}/projects/{project_id}/pitch_decks',
    'public_shared': 'public/shared/{token}',
}

# =============================================================================
# AUTHENTICATION & AUTHORIZATION
# =============================================================================
AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# =============================================================================
# REST FRAMEWORK - With Rate Limiting
# Per HIGH_SCALE_ARCHITECTURE_PLAN.md
# =============================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'burst': '60/minute',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# API Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'MarketNavigator v2 API',
    'DESCRIPTION': 'High-scale market research platform API',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# =============================================================================
# CORS
# =============================================================================
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS', 
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all in development
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# =============================================================================
# EXTERNAL API KEYS
# Per FINAL_ARCHITECTURE_SPECIFICATION.md
# =============================================================================
# Liara AI (OpenAI-compatible API - Primary AI backend)
LIARA_API_KEY = os.getenv('LIARA_API_KEY', '')
LIARA_BASE_URL = os.getenv('LIARA_BASE_URL', 'https://ai.liara.ir/api/6918348a8376cb0a3e18fdef/v1')
LIARA_MODEL = os.getenv('LIARA_MODEL', 'google/gemini-2.5-flash')

# OpenAI (Fallback)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Metis AI (OpenAI-compatible API proxy)
METIS_API_KEY = os.getenv('METIS_API_KEY', '')
METIS_BASE_URL = os.getenv('METIS_BASE_URL', 'https://api.metisai.ir/openai/v1')
METIS_MODEL = os.getenv('METIS_MODEL', 'gpt-4o-mini')

CRUNCHBASE_API_KEY = os.getenv('CRUNCHBASE_API_KEY', '')
CRUNCHBASE_API_URL = 'https://api.crunchbase.com/api/v4'

TRACXN_API_KEY = os.getenv('TRACXN_API_KEY', '')
TRACXN_API_URL = 'https://api.tracxn.com/2.2'

TWITTER_API_KEY = os.getenv('TWITTER_API_KEY', '')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET', '')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')

LINKEDIN_CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID', '')
LINKEDIN_CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET', '')

# =============================================================================
# MVP SCRAPER API URLS
# Crunchbase and Tracxn scrapers only
# Per MARKETNAVIGATOR_MVP_REFERENCE.md
# =============================================================================
CRUNCHBASE_SCRAPER_URL = os.getenv('CRUNCHBASE_SCRAPER_URL', 'http://crunchbase_api:8003')
TRACXN_SCRAPER_URL = os.getenv('TRACXN_SCRAPER_URL', 'http://tracxn_api:8008')

# =============================================================================
# ORCHESTRATOR (Remote Workers)
# Routes scraper tasks to remote workers when enabled
# =============================================================================
USE_ORCHESTRATOR = os.getenv('USE_ORCHESTRATOR', 'false').lower() in ('true', '1', 'yes')
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://orchestrator:8010')

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# LOGGING - Production Grade
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter' if not DEBUG else 'django.utils.log.ServerFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': True,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
    },
}

# =============================================================================
# SENTRY (Error Tracking - Optional)
# =============================================================================
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# =============================================================================
# AUDIT SETTINGS
# Per HIGH_SCALE_ARCHITECTURE_PLAN.md
# =============================================================================
AUDIT_LOG_ENABLED = True
AUDIT_LOG_RETENTION_DAYS = 90
API_USAGE_TRACKING_ENABLED = True
