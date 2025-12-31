# Environment Variable Locations - MarketNavigator v2

## Purpose
Comprehensive map of where environment variables are defined, loaded, and used across local development and production environments. Use this to troubleshoot configuration issues and prevent environment drift.

---

## Environment Variable Flow

```
Source Files → Docker Compose → Containers → Application
```

---

## Local Development Environment

### 1. Root `.env` File
**Location:** `/path/to/MarketNavigator2.0/.env`  
**Purpose:** Main environment variables for local development  
**Loaded by:** Docker Compose (implicit)  
**Git Status:** **TRACKED** (per project .gitignore configuration)

**Contains:**
- Database credentials (Liara remote PostgreSQL)
- Redis configuration
- MinIO credentials
- API keys (OpenAI, Liara AI, Metis)
- Scraper API URLs
- Django settings (DEBUG, SECRET_KEY)
- Next.js public URLs

**Example structure:**
```bash
# Django
DEBUG=1
SECRET_KEY=dev-secret-key-change-in-production
DJANGO_LOG_LEVEL=INFO

# Database (Remote Liara)
DB_HOST=table-mountain.liara.cloud
DB_PORT=32965
DB_NAME=postgres
DB_USER=root
DB_PASSWORD=AZ6t2MguosDdJ8oCval6B7bU

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# MinIO
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123

# API Keys
OPENAI_API_KEY=sk-...
LIARA_API_KEY=eyJ...
METIS_API_KEY=tpsg-...
```

### 2. Scraper-Specific Environment Files

#### Crunchbase API Environment
**Location:** `scrapers/Crunchbase_API/.env`  
**Purpose:** Crunchbase scraper database and credentials  
**Loaded by:** crunchbase_api Docker container  
**Git Status:** **TRACKED** (contains remote DB credentials)

**Contains:**
```bash
# MySQL Database (Remote Liara)
MYSQL_HOST=your-mysql-host.liara.cloud
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=crunchbase_db

# Crunchbase Credentials
CRUNCHBASE_USERNAME=your_username
CRUNCHBASE_PASSWORD=your_password
```

#### Tracxn API Configuration
**Location:** `scrapers/Tracxn_API/config.py`  
**Purpose:** Tracxn scraper settings  
**Loaded by:** tracxn_api Docker container (hardcoded imports)  
**Git Status:** **TRACKED**

**Contains:**
```python
# Database configuration
DB_CONFIG = {
    'host': 'your-mysql-host.liara.cloud',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',
    'database': 'tracxn_db'
}

# Tracxn credentials
TRACXN_EMAIL = "your_email@example.com"
TRACXN_PASSWORD = "your_password"
```

### 3. Docker Compose Environment Sections

#### docker-compose.yml (Development)
**Location:** `docker-compose.yml`  
**Purpose:** Container-specific environment overrides  
**How it works:** Hardcoded `environment:` sections override `.env` values

**Services with inline environment:**
- `backend` - Full Django configuration
- `celery-worker` - Celery + Django settings
- `celery-beat` - Minimal Django settings
- `flower` - Celery monitoring auth
- `frontend` - Next.js public URLs
- `redis` - Command-line args (not env vars)
- `minio` - MinIO root credentials

**Loading priority:**
1. Inline `environment:` in docker-compose.yml (HIGHEST)
2. `.env` file variables referenced via `${VAR_NAME}`
3. Container defaults (LOWEST)

### 4. Next.js Build-Time Variables

**Location:** `frontend/.env.local` (if exists - NOT tracked)  
**Purpose:** Next.js build-time variables  
**Loaded by:** Next.js build process  
**Git Status:** **NOT TRACKED** (.gitignore)

**Note:** In this project, Next.js variables are defined in docker-compose.yml's `frontend` service environment section, NOT in a separate .env file.

**Variables:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Production Environment

### 1. Production `.env` File
**Location:** `/opt/marketnavigator/MarketNavigator2.0/.env` (on server)  
**Purpose:** Production-specific overrides  
**Loaded by:** Docker Compose production stack  
**Git Status:** **TRACKED** (contains production values)

**Differences from development:**
```bash
# Django
DEBUG=0  # Changed from DEBUG=1
SECRET_KEY=<STRONG_RANDOM_KEY>  # Changed from dev key
ALLOWED_HOSTS=market.kareonecompany.com,backend,localhost
CORS_ALLOWED_ORIGINS=https://market.kareonecompany.com

# Database (Liara Private Network)
DB_HOST=marketnavigator-v2  # Changed from public hostname
DB_PORT=5432

# Next.js URLs
NEXT_PUBLIC_API_URL=https://market.kareonecompany.com
NEXT_PUBLIC_WS_URL=wss://market.kareonecompany.com
```

### 2. Docker Compose Production Override
**Location:** `docker-compose.prod.yml`  
**Purpose:** Production-specific environment overrides  
**Usage:** `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

**Override mechanism:**
- Merges with base `docker-compose.yml`
- `environment:` sections REPLACE base environment
- Values can reference `.env` file via `${VAR_NAME:-default}`

**Production overrides for backend:**
```yaml
backend:
  environment:
    - DEBUG=0
    - SECRET_KEY=${SECRET_KEY:-change-this-to-a-strong-secret-key}
    - DB_HOST=marketnavigator-v2
    - ALLOWED_HOSTS=market.kareonecompany.com,backend,localhost
    - CORS_ALLOWED_ORIGINS=https://market.kareonecompany.com
```

### 3. Nginx Environment (SSL Paths)
**Location:** `nginx/nginx.conf` (NOT environment variables)  
**Purpose:** SSL certificate paths, proxy settings  
**Loaded by:** Nginx on startup

**SSL certificates:**
```nginx
ssl_certificate /etc/nginx/ssl/fullchain.pem;
ssl_certificate_key /etc/nginx/ssl/privkey.pem;
```

**Certificate source:**
- Let's Encrypt: `/etc/letsencrypt/live/market.kareonecompany.com/`
- Copied to: `nginx/ssl/` directory

---

## Environment Variable Reference by Service

### Backend (Django)

**Defined in:** `docker-compose.yml` + `docker-compose.prod.yml`

| Variable | Development Value | Production Value | Purpose |
|----------|------------------|------------------|---------|
| `DEBUG` | 1 | 0 | Enable/disable debug mode |
| `SECRET_KEY` | dev-secret-key... | <random-50-char> | Django cryptographic signing |
| `DB_HOST` | table-mountain.liara.cloud | marketnavigator-v2 | PostgreSQL hostname |
| `DB_PORT` | 32965 | 5432 | PostgreSQL port |
| `DB_NAME` | postgres | postgres | Database name |
| `DB_USER` | root | root | Database user |
| `DB_PASSWORD` | AZ6t2Mgu... | AZ6t2Mgu... | Database password |
| `REDIS_URL` | redis://redis:6379/0 | redis://redis:6379/0 | Redis connection |
| `CELERY_BROKER_URL` | redis://redis:6379/0 | redis://redis:6379/0 | Celery message broker |
| `ALLOWED_HOSTS` | localhost,127.0.0.1,backend | market.kareonecompany.com,backend | Django allowed hosts |
| `CORS_ALLOWED_ORIGINS` | http://localhost:3000 | https://market.kareonecompany.com | CORS whitelist |
| `USE_S3` | True | True | Enable MinIO storage |
| `AWS_ACCESS_KEY_ID` | minioadmin | minioadmin | MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | minioadmin123 | <strong-password> | MinIO secret key |
| `AWS_STORAGE_BUCKET_NAME` | marketnavigator-files | marketnavigator-files | MinIO bucket |
| `AWS_S3_ENDPOINT_URL` | http://minio:9000 | http://minio:9000 | MinIO endpoint |
| `LIARA_API_KEY` | eyJhbGciOi... | eyJhbGciOi... | Liara AI API key |
| `LIARA_BASE_URL` | https://ai.liara.ir/api/.../v1 | https://ai.liara.ir/api/.../v1 | Liara AI endpoint |
| `OPENAI_API_KEY` | sk-... | sk-... | OpenAI API key |
| `CRUNCHBASE_SCRAPER_URL` | http://crunchbase_api:8003 | http://crunchbase_api:8003 | Scraper URL |
| `TRACXN_SCRAPER_URL` | http://tracxn_api:8008 | http://tracxn_api:8008 | Scraper URL |

### Celery Worker

**Defined in:** `docker-compose.yml` + `docker-compose.prod.yml`

**Same as Backend** plus:
| Variable | Value | Purpose |
|----------|-------|---------|
| `CELERY_CONCURRENCY` | 4 | Number of concurrent worker processes |
| `PYTHONUNBUFFERED` | 1 | Disable Python output buffering |

### Celery Beat

**Defined in:** `docker-compose.yml` + `docker-compose.prod.yml`

**Minimal set:**
- `DEBUG`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_URL`, `CELERY_BROKER_URL`
- `SECRET_KEY`

### Flower

**Defined in:** `docker-compose.yml`

| Variable | Value | Purpose |
|----------|-------|---------|
| `CELERY_BROKER_URL` | redis://redis:6379/0 | Connect to Celery broker |
| `FLOWER_PORT` | 5555 | Web UI port |
| `FLOWER_BASIC_AUTH` | admin:admin123 | HTTP Basic Auth |

### Frontend (Next.js)

**Defined in:** `docker-compose.yml` (implicit override in production)

| Variable | Development Value | Production Value | Purpose |
|----------|------------------|------------------|---------|
| `NEXT_PUBLIC_API_URL` | http://localhost:8000 | https://market.kareonecompany.com | Backend API base URL |
| `NEXT_PUBLIC_WS_URL` | ws://localhost:8000 | wss://market.kareonecompany.com | WebSocket URL |

**Note:** `NEXT_PUBLIC_*` variables are embedded into frontend build at build-time, not runtime.

### Redis

**Defined in:** `docker-compose.yml` (command-line args)

```yaml
command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

**No environment variables used.**

### MinIO

**Defined in:** `docker-compose.yml`

| Variable | Value | Purpose |
|----------|-------|---------|
| `MINIO_ROOT_USER` | minioadmin | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | minioadmin123 (dev) / <strong> (prod) | MinIO admin password |

### Crunchbase API

**Defined in:** `scrapers/Crunchbase_API/.env`

Loaded automatically by the container (not via docker-compose environment section).

### Tracxn API

**Defined in:** `scrapers/Tracxn_API/config.py`

Hardcoded configuration, not environment variables.

---

## Environment Variable Precedence

**Highest to Lowest Priority:**

1. **docker-compose.prod.yml `environment:`** - Overrides everything in production
2. **docker-compose.yml `environment:`** - Overrides .env and defaults
3. **Container's .env file** (e.g., scrapers/Crunchbase_API/.env)
4. **Root `.env` file** - Referenced via `${VAR_NAME}` syntax
5. **Container Dockerfile ENV** - Build-time defaults
6. **Application defaults** - Hardcoded in Django settings.py, etc.

**Example resolution:**
```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - DEBUG=${DEBUG:-1}  # Uses .env's DEBUG, defaults to 1 if missing

# docker-compose.prod.yml
services:
  backend:
    environment:
      - DEBUG=0  # ALWAYS 0 in production (overrides everything)
```

---

## How to Verify Environment Variables

### Inside Running Container

```bash
# View all environment variables
docker exec mn2-backend env

# Check specific variable
docker exec mn2-backend env | grep DEBUG

# Check Django settings
docker exec mn2-backend python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"
```

### From Docker Compose

```bash
# Show resolved configuration
docker-compose config

# Show environment for specific service
docker-compose config | grep -A 50 "backend:"
```

### Check Next.js Build-Time Variables

```bash
# Next.js bundles NEXT_PUBLIC_* into JavaScript
docker exec mn2-frontend cat /app/.next/server/app-paths-manifest.json

# Or check browser Network tab → any API call → Request Headers → Origin
```

---

## Environment Variable Templates

### `.env.example` (Development Template)
Create this file to help new developers:

```bash
# Django
DEBUG=1
SECRET_KEY=dev-secret-key-DO-NOT-USE-IN-PRODUCTION
DJANGO_LOG_LEVEL=INFO

# Database (Liara Remote)
DB_HOST=table-mountain.liara.cloud
DB_PORT=32965
DB_NAME=postgres
DB_USER=root
DB_PASSWORD=<ASK_TEAM_FOR_PASSWORD>

# Redis (Local Docker)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# MinIO (Local Docker)
USE_S3=True
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
AWS_STORAGE_BUCKET_NAME=marketnavigator-files
AWS_S3_ENDPOINT_URL=http://minio:9000

# Security
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend
CORS_ALLOWED_ORIGINS=http://localhost:3000

# AI Keys (Get from team)
OPENAI_API_KEY=<ASK_TEAM>
LIARA_API_KEY=<ASK_TEAM>
METIS_API_KEY=<ASK_TEAM>

# Scraper URLs (Local Docker)
CRUNCHBASE_SCRAPER_URL=http://crunchbase_api:8003
TRACXN_SCRAPER_URL=http://tracxn_api:8008
```

### `.env.production` (Production Template)
Create this file for production deployment reference:

```bash
# Django
DEBUG=0
SECRET_KEY=<GENERATE_WITH_python3 -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_LOG_LEVEL=WARNING

# Database (Liara Private Network)
DB_HOST=marketnavigator-v2
DB_PORT=5432
DB_NAME=postgres
DB_USER=root
DB_PASSWORD=<PRODUCTION_PASSWORD>

# Redis (Docker Internal)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# MinIO (Docker Internal)
USE_S3=True
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=<GENERATE_STRONG_PASSWORD>
AWS_STORAGE_BUCKET_NAME=marketnavigator-files
AWS_S3_ENDPOINT_URL=http://minio:9000

# Security
ALLOWED_HOSTS=market.kareonecompany.com,backend,localhost
CORS_ALLOWED_ORIGINS=https://market.kareonecompany.com

# AI Keys (Production)
OPENAI_API_KEY=<PRODUCTION_KEY>
LIARA_API_KEY=<PRODUCTION_KEY>
METIS_API_KEY=<PRODUCTION_KEY>

# Scraper URLs (Docker Internal)
CRUNCHBASE_SCRAPER_URL=http://crunchbase_api:8003
TRACXN_SCRAPER_URL=http://tracxn_api:8008

# Next.js Public URLs
NEXT_PUBLIC_API_URL=https://market.kareonecompany.com
NEXT_PUBLIC_WS_URL=wss://market.kareonecompany.com
```

---

## Common Issues & Solutions

### Issue: Variable Not Loaded
**Symptom:** Container uses default value instead of .env value

**Solution:**
```bash
# 1. Check if variable is defined in docker-compose.yml
docker-compose config | grep YOUR_VARIABLE

# 2. Variable must be referenced with ${} syntax in docker-compose.yml
environment:
  - MY_VAR=${MY_VAR}  # Correct
  # NOT: MY_VAR=$MY_VAR (shell syntax, doesn't work)

# 3. Rebuild if it's a build-time variable
docker-compose build --no-cache backend
```

### Issue: NEXT_PUBLIC Variables Not Working
**Symptom:** Frontend uses old API URL

**Solution:**
```bash
# Next.js bakes NEXT_PUBLIC_* into build
# Must REBUILD frontend after changing these variables
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### Issue: Scraper Can't Connect to Database
**Symptom:** Crunchbase/Tracxn API errors about database connection

**Solution:**
```bash
# Check scraper-specific .env file
cat scrapers/Crunchbase_API/.env

# Verify it's mounted in container
docker exec mn2-crunchbase-api cat /app/.env

# If missing, check volume mount in docker-compose.yml
volumes:
  - ./scrapers/Crunchbase_API:/app  # Should mount .env file
```

### Issue: Environment Drift Between Dev and Prod
**Symptom:** Works locally but fails in production

**Solution:**
```bash
# Compare environments
docker-compose config > dev_config.yml
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config > prod_config.yml
diff dev_config.yml prod_config.yml

# Look for differences in:
# - DEBUG setting
# - Database hostnames
# - ALLOWED_HOSTS / CORS_ALLOWED_ORIGINS
# - API URLs
```

---

## Best Practices

1. **Never hardcode secrets in docker-compose.yml**
   ```yaml
   # BAD
   environment:
     - SECRET_KEY=hardcoded-secret
   
   # GOOD
   environment:
     - SECRET_KEY=${SECRET_KEY}
   ```

2. **Use defaults for non-sensitive values**
   ```yaml
   environment:
     - DEBUG=${DEBUG:-1}  # Defaults to 1 if not in .env
     - CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-4}
   ```

3. **Document required variables**
   - Maintain `.env.example` with all required variables
   - Mark sensitive values with `<ASK_TEAM>` or `<CHANGE_ME>`

4. **Separate build-time and runtime variables**
   - Build-time: Baked into image (NEXT_PUBLIC_*, ARG in Dockerfile)
   - Runtime: Can be changed without rebuild (most Django settings)

5. **Validate environment on startup**
   ```python
   # In Django settings.py
   import os
   
   REQUIRED_ENV_VARS = ['SECRET_KEY', 'DB_HOST', 'DB_PASSWORD']
   missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
   if missing:
       raise Exception(f"Missing required env vars: {missing}")
   ```

---

**Last Updated:** 2025-12-31  
**Maintainer:** DevOps Team
