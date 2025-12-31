# Environment Variable Examples - MarketNavigator v2

## Purpose
Complete reference of all required environment variables for local development and production deployment. Use this as a template for `.env` file configuration. **No sensitive values included** - placeholder values only.

---

## Development Environment Template

Create `.env` file in project root with these variables:

```bash
# ============================================================================
# Django Backend Configuration
# ============================================================================

# Debug & Development
DEBUG=1
DJANGO_LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# Security
SECRET_KEY=dev-secret-key-CHANGE-THIS-IN-PRODUCTION-use-50-random-chars
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend
CORS_ALLOWED_ORIGINS=http://localhost:3000

# ============================================================================
# Database Configuration (PostgreSQL)
# ============================================================================

# Remote Liara PostgreSQL (Development)
DB_HOST=table-mountain.liara.cloud
DB_PORT=32965
DB_NAME=postgres
DB_USER=root
DB_PASSWORD=<ASK_TEAM_FOR_PASSWORD>

# Alternative: Local PostgreSQL (if not using Liara)
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=marketnavigator_dev
# DB_USER=postgres
# DB_PASSWORD=postgres

# ============================================================================
# Redis Configuration
# ============================================================================

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ============================================================================
# MinIO (S3-Compatible Storage)
# ============================================================================

USE_S3=True
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
AWS_STORAGE_BUCKET_NAME=marketnavigator-files
AWS_S3_ENDPOINT_URL=http://minio:9000
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=localhost:9000/marketnavigator-files

# ============================================================================
# AI Services Configuration
# ============================================================================

# OpenAI (optional - for advanced features)
OPENAI_API_KEY=sk-<YOUR_OPENAI_API_KEY_HERE>
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=4000

# Liara AI (primary AI provider for keyword generation)
LIARA_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<YOUR_TOKEN_HERE>
LIARA_BASE_URL=https://ai.liara.ir/api/<YOUR_PROJECT_ID>/v1
LIARA_MODEL=google/gemini-2.5-flash
LIARA_MAX_TOKENS=4000

# Metis AI (alternative provider)
METIS_API_KEY=tpsg-<YOUR_METIS_KEY_HERE>
METIS_BASE_URL=https://api.metisai.ir/openai/v1
METIS_MODEL=gpt-4o-mini
METIS_MAX_TOKENS=4000

# ============================================================================
# Scraper API URLs (Internal Docker Network)
# ============================================================================

CRUNCHBASE_SCRAPER_URL=http://crunchbase_api:8003
TRACXN_SCRAPER_URL=http://tracxn_api:8008

# ============================================================================
# Celery Configuration
# ============================================================================

CELERY_CONCURRENCY=4
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=600
CELERY_WORKER_MAX_TASKS_PER_CHILD=50

# ============================================================================
# Email Configuration (Optional - for notifications)
# ============================================================================

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<YOUR_EMAIL@example.com>
EMAIL_HOST_PASSWORD=<YOUR_EMAIL_PASSWORD_OR_APP_PASSWORD>
DEFAULT_FROM_EMAIL=noreply@marketnavigator.com

# Alternative: Console backend for development (emails print to console)
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# ============================================================================
# Session & Security
# ============================================================================

SESSION_COOKIE_AGE=1209600
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL=INFO
LOG_TO_FILE=False
LOG_FILE_PATH=/app/logs/debug.log

# ============================================================================
# Feature Flags (Optional)
# ============================================================================

ENABLE_SOCIAL_REPORTS=True
ENABLE_PITCH_DECK_REPORTS=True
ENABLE_AI_CHAT=True
ENABLE_PUBLIC_SHARING=True
ENABLE_ANALYTICS=False
```

---

## Production Environment Template

Create `.env` file on production server with these variables:

```bash
# ============================================================================
# Django Backend Configuration
# ============================================================================

# Debug & Development
DEBUG=0
DJANGO_LOG_LEVEL=WARNING
PYTHONUNBUFFERED=1

# Security
SECRET_KEY=<GENERATE_50_CHAR_RANDOM_STRING_SEE_BELOW>
ALLOWED_HOSTS=market.kareonecompany.com,backend,localhost
CORS_ALLOWED_ORIGINS=https://market.kareonecompany.com

# ============================================================================
# Database Configuration (PostgreSQL)
# ============================================================================

# Liara Private Network (Production)
DB_HOST=marketnavigator-v2
DB_PORT=5432
DB_NAME=postgres
DB_USER=root
DB_PASSWORD=<PRODUCTION_DATABASE_PASSWORD>

# ============================================================================
# Redis Configuration
# ============================================================================

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ============================================================================
# MinIO (S3-Compatible Storage)
# ============================================================================

USE_S3=True
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=<STRONG_RANDOM_PASSWORD_20_CHARS>
AWS_STORAGE_BUCKET_NAME=marketnavigator-files
AWS_S3_ENDPOINT_URL=http://minio:9000
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=market.kareonecompany.com/files

# ============================================================================
# AI Services Configuration
# ============================================================================

# OpenAI (production keys)
OPENAI_API_KEY=sk-proj-<PRODUCTION_KEY>
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=4000

# Liara AI
LIARA_API_KEY=<PRODUCTION_LIARA_KEY>
LIARA_BASE_URL=https://ai.liara.ir/api/<PROD_PROJECT_ID>/v1
LIARA_MODEL=google/gemini-2.5-flash
LIARA_MAX_TOKENS=4000

# Metis AI
METIS_API_KEY=<PRODUCTION_METIS_KEY>
METIS_BASE_URL=https://api.metisai.ir/openai/v1
METIS_MODEL=gpt-4o-mini
METIS_MAX_TOKENS=4000

# ============================================================================
# Scraper API URLs (Internal Docker Network)
# ============================================================================

CRUNCHBASE_SCRAPER_URL=http://crunchbase_api:8003
TRACXN_SCRAPER_URL=http://tracxn_api:8008

# ============================================================================
# Celery Configuration
# ============================================================================

CELERY_CONCURRENCY=8
CELERY_TASK_SOFT_TIME_LIMIT=600
CELERY_TASK_TIME_LIMIT=1200
CELERY_WORKER_MAX_TASKS_PER_CHILD=100

# ============================================================================
# Email Configuration
# ============================================================================

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<PRODUCTION_EMAIL@company.com>
EMAIL_HOST_PASSWORD=<APP_SPECIFIC_PASSWORD>
DEFAULT_FROM_EMAIL=noreply@marketnavigator.com

# ============================================================================
# Session & Security (Production Hardening)
# ============================================================================

SESSION_COOKIE_AGE=1209600
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_BROWSER_XSS_FILTER=True
X_FRAME_OPTIONS=DENY

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL=WARNING
LOG_TO_FILE=True
LOG_FILE_PATH=/app/logs/production.log

# ============================================================================
# Monitoring & Sentry (Optional)
# ============================================================================

SENTRY_DSN=https://<KEY>@<ORGANIZATION>.ingest.sentry.io/<PROJECT_ID>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# ============================================================================
# Feature Flags
# ============================================================================

ENABLE_SOCIAL_REPORTS=True
ENABLE_PITCH_DECK_REPORTS=True
ENABLE_AI_CHAT=True
ENABLE_PUBLIC_SHARING=True
ENABLE_ANALYTICS=True
```

---

## Frontend Environment Variables

### Development (Next.js)

These are set in `docker-compose.yml` for frontend service:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Production (Next.js)

These are set in `docker-compose.prod.yml`:

```bash
NEXT_PUBLIC_API_URL=https://market.kareonecompany.com
NEXT_PUBLIC_WS_URL=wss://market.kareonecompany.com
```

**Note:** `NEXT_PUBLIC_*` variables are baked into the frontend build. Changing them requires rebuilding the frontend container.

---

## Scraper-Specific Environment Files

### Crunchbase API Environment

**File:** `scrapers/Crunchbase_API/.env`

```bash
# MySQL Database (Remote Liara)
MYSQL_HOST=<YOUR_MYSQL_HOST>.liara.cloud
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=<MYSQL_PASSWORD>
MYSQL_DATABASE=crunchbase_db

# Crunchbase Credentials
CRUNCHBASE_USERNAME=<YOUR_CRUNCHBASE_EMAIL>
CRUNCHBASE_PASSWORD=<YOUR_CRUNCHBASE_PASSWORD>

# Scraper Configuration
HEADLESS_MODE=true
MAX_RETRIES=3
REQUEST_TIMEOUT=30
RATE_LIMIT_DELAY=2

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/crunchbase_scraper.log
```

### Tracxn API Configuration

**File:** `scrapers/Tracxn_API/config.py`

```python
# Database configuration
DB_CONFIG = {
    'host': '<YOUR_MYSQL_HOST>.liara.cloud',
    'port': 3306,
    'user': 'root',
    'password': '<MYSQL_PASSWORD>',
    'database': 'tracxn_db'
}

# Tracxn credentials
TRACXN_EMAIL = "<YOUR_TRACXN_EMAIL>"
TRACXN_PASSWORD = "<YOUR_TRACXN_PASSWORD>"

# Scraper settings
HEADLESS_MODE = True
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
```

---

## How to Generate Secure Values

### Django SECRET_KEY

```bash
# Method 1: Using Python
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Method 2: Using OpenSSL
openssl rand -base64 50

# Example output:
# 7jK9mN2pQ8rT6vW1xY4zA3bC5dE8fG0hJ2kL4mN6pR9sT2uV5xZ8
```

### MinIO Password (AWS_SECRET_ACCESS_KEY)

```bash
# Generate 20-character random password
python3 -c "import secrets, string; chars = string.ascii_letters + string.digits; print(''.join(secrets.choice(chars) for _ in range(20)))"

# Example output:
# aB3dE7fG9hJ2kL5mN8
```

### Database Password

```bash
# Generate 32-character password with special characters
python3 -c "import secrets, string; chars = string.ascii_letters + string.digits + '!@#$%^&*'; print(''.join(secrets.choice(chars) for _ in range(32)))"

# Example output:
# aB3!dE7@fG9#hJ2$kL5%mN8^pQ1&rT4*
```

---

## Variable Validation

### Required Variables Checklist

**Backend (Django):**
- [ ] `SECRET_KEY` - Must be 50+ characters, random
- [ ] `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Database connection
- [ ] `REDIS_URL` - Redis connection
- [ ] `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - MinIO credentials
- [ ] `ALLOWED_HOSTS` - Must include production domain
- [ ] `CORS_ALLOWED_ORIGINS` - Must match frontend URL

**Frontend (Next.js):**
- [ ] `NEXT_PUBLIC_API_URL` - Must match backend URL
- [ ] `NEXT_PUBLIC_WS_URL` - Must match backend WebSocket URL

**AI Services (At least one):**
- [ ] `OPENAI_API_KEY` OR `LIARA_API_KEY` OR `METIS_API_KEY`

### Validation Script

Save as `scripts/validate-env.sh`:

```bash
#!/bin/bash

echo "Validating environment variables..."

REQUIRED_VARS=(
    "SECRET_KEY"
    "DB_HOST"
    "DB_PASSWORD"
    "REDIS_URL"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "ALLOWED_HOSTS"
)

MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables:"
    printf '  - %s\n' "${MISSING_VARS[@]}"
    exit 1
fi

# Check SECRET_KEY length
if [ ${#SECRET_KEY} -lt 50 ]; then
    echo "⚠️  Warning: SECRET_KEY should be at least 50 characters (current: ${#SECRET_KEY})"
fi

# Check if using default values in production
if [ "$DEBUG" = "0" ]; then
    if [ "$SECRET_KEY" = "dev-secret-key-CHANGE-THIS-IN-PRODUCTION-use-50-random-chars" ]; then
        echo "❌ ERROR: Using default SECRET_KEY in production!"
        exit 1
    fi
    
    if [ "$AWS_SECRET_ACCESS_KEY" = "minioadmin123" ]; then
        echo "❌ ERROR: Using default MinIO password in production!"
        exit 1
    fi
fi

echo "✅ Environment variables validation passed"
```

**Usage:**
```bash
chmod +x scripts/validate-env.sh

# Load .env and validate
set -a; source .env; set +a
./scripts/validate-env.sh
```

---

## Environment-Specific Differences

| Variable | Development | Production | Notes |
|----------|------------|------------|-------|
| `DEBUG` | `1` | `0` | Disable debug in production |
| `SECRET_KEY` | Simple string | 50-char random | Generate new for prod |
| `DB_HOST` | Public hostname | Private network DNS | Faster connection |
| `ALLOWED_HOSTS` | `localhost` | `market.kareonecompany.com` | Domain whitelist |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | `https://market.kareonecompany.com` | Must use HTTPS |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin123` | Strong password | Change default |
| `SESSION_COOKIE_SECURE` | `False` | `True` | Requires HTTPS |
| `CSRF_COOKIE_SECURE` | `False` | `True` | Requires HTTPS |
| `SECURE_SSL_REDIRECT` | `False` | `True` | Force HTTPS |
| `LOG_LEVEL` | `INFO` | `WARNING` | Reduce noise |
| `CELERY_CONCURRENCY` | `4` | `8` | More workers for prod |

---

## Common Pitfalls

### ❌ Using Development Values in Production

```bash
# BAD - Default passwords in production
SECRET_KEY=dev-secret-key
AWS_SECRET_ACCESS_KEY=minioadmin123
```

**Solution:** Generate strong random values (see "How to Generate Secure Values" section)

### ❌ Hardcoding Secrets in docker-compose.yml

```yaml
# BAD
environment:
  - SECRET_KEY=hardcoded-secret-key
```

**Solution:** Reference .env file
```yaml
# GOOD
environment:
  - SECRET_KEY=${SECRET_KEY}
```

### ❌ Forgetting to Rebuild After Changing NEXT_PUBLIC_*

```bash
# Change NEXT_PUBLIC_API_URL in .env
# Frontend still uses old value!
```

**Solution:**
```bash
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### ❌ Using HTTP URLs in Production

```bash
# BAD
NEXT_PUBLIC_API_URL=http://market.kareonecompany.com
CORS_ALLOWED_ORIGINS=http://market.kareonecompany.com
```

**Solution:** Always use HTTPS in production
```bash
# GOOD
NEXT_PUBLIC_API_URL=https://market.kareonecompany.com
CORS_ALLOWED_ORIGINS=https://market.kareonecompany.com
```

---

## Quick Reference

### Copy Template for New Setup

```bash
# Clone repository
git clone <repo-url>
cd MarketNavigator2.0

# Copy this document's "Development Environment Template" section
# Create .env file
nano .env
# Paste template, replace placeholders

# Validate
set -a; source .env; set +a
./scripts/validate-env.sh

# Start services
docker-compose up -d
```

### Update Production Environment

```bash
# SSH to production server
ssh user@production-server

cd /opt/marketnavigator/MarketNavigator2.0

# Backup current .env
cp .env .env.backup.$(date +%Y%m%d)

# Edit .env
nano .env

# Restart services to apply changes
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart backend celery-worker

# Verify
docker-compose logs backend --tail 50
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** DevOps Team  
**Review Schedule:** After any new feature requiring new environment variables
