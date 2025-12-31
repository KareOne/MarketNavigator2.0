# Docker Compose Environment File Loading - MarketNavigator v2

## Purpose
Comprehensive guide on how Docker Compose loads environment variables from `.env` files, with explicit configurations to prevent misconfigurations and environment drift.

---

## How Docker Compose Loads Environment Variables

### Loading Priority (Highest to Lowest)

1. **docker-compose.yml `environment:` section** (inline values)
2. **Shell environment variables** (exported in current shell)
3. **`.env` file** in project root (implicit loading)
4. **`env_file:` directive** (explicit file loading)
5. **Dockerfile `ENV` instructions** (build-time defaults)
6. **Application defaults** (hardcoded in code)

---

## Method 1: Root `.env` File (Implicit Loading)

### How It Works

Docker Compose **automatically** loads `.env` file from project root:

```bash
MarketNavigator2.0/
├── .env                    # ← Automatically loaded
├── docker-compose.yml
└── docker-compose.prod.yml
```

**When loaded:**
- When running any `docker-compose` command
- Variables available for **substitution** in docker-compose.yml
- **NOT** automatically passed to containers (must reference explicitly)

### Example: .env File

```bash
# .env
DB_PASSWORD=secretpassword123
REDIS_URL=redis://redis:6379/0
DEBUG=1
```

### Example: docker-compose.yml

```yaml
services:
  backend:
    environment:
      # Reference .env variables with ${VAR_NAME}
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_URL=${REDIS_URL}
      - DEBUG=${DEBUG}
      
      # Can provide defaults
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      
      # Mix with hardcoded values
      - DB_HOST=localhost
      - DB_PORT=5432
```

**Result:** Container gets `DB_PASSWORD=secretpassword123`, `DEBUG=1`, `LOG_LEVEL=INFO` (default)

---

## Method 2: Explicit `env_file:` Directive

### How It Works

Explicitly specify which `.env` files to load **into containers**:

```yaml
services:
  backend:
    env_file:
      - .env              # Load root .env
      - backend/.env      # Load backend-specific .env
      - .env.production   # Load production overrides
```

**Key difference from implicit loading:**
- Variables are passed **directly to container**
- No `${VAR_NAME}` substitution needed in `environment:` section
- Later files override earlier files
- Can specify multiple files

### Example: Multi-File Loading

```yaml
services:
  backend:
    env_file:
      - .env.defaults     # Base configuration
      - .env              # Environment-specific
      - .env.local        # Local overrides (not tracked)
    environment:
      # Can still override specific variables
      - DEBUG=0
```

**Load order:**
1. `.env.defaults` loaded
2. `.env` loaded (overrides defaults)
3. `.env.local` loaded (overrides previous)
4. `environment:` overrides everything

---

## Method 3: Inline `environment:` Section (Recommended for MarketNavigator)

### How It Works

Define all environment variables directly in `docker-compose.yml`:

```yaml
services:
  backend:
    environment:
      # Hardcoded values
      - DEBUG=1
      - DB_HOST=localhost
      - DB_PORT=5432
      
      # Values from .env file (substitution)
      - DB_PASSWORD=${DB_PASSWORD}
      - SECRET_KEY=${SECRET_KEY:-dev-secret-key}
      
      # Values from shell environment
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

**Benefits:**
- Explicit: All variables visible in docker-compose.yml
- Validation: Can see which variables are required
- Defaults: Can specify fallback values
- Override: Production compose file can override completely

**MarketNavigator uses this method** for all services.

---

## Current MarketNavigator Configuration

### Development (docker-compose.yml)

```yaml
services:
  backend:
    environment:
      - DEBUG=1
      - SECRET_KEY=dev-secret-key-change-in-production
      - DB_HOST=table-mountain.liara.cloud
      - DB_PORT=32965
      - DB_NAME=postgres
      - DB_USER=root
      - DB_PASSWORD=AZ6t2MguosDdJ8oCval6B7bU  # Hardcoded (not recommended for prod)
      - REDIS_URL=redis://redis:6379/0
      - AWS_ACCESS_KEY_ID=minioadmin
      - AWS_SECRET_ACCESS_KEY=minioadmin123
      # ... more variables
```

**Current issues:**
1. Passwords are hardcoded in `docker-compose.yml` (visible in Git)
2. No `.env` file substitution for sensitive values
3. Same configuration for all developers

### Recommended Improvement

**Step 1:** Create `.env` file with sensitive values:

```bash
# .env (NOT tracked in Git)
DB_PASSWORD=AZ6t2MguosDdJ8oCval6B7bU
SECRET_KEY=dev-secret-key-change-in-production
AWS_SECRET_ACCESS_KEY=minioadmin123
LIARA_API_KEY=eyJhbGciOi...
OPENAI_API_KEY=sk-...
```

**Step 2:** Update `docker-compose.yml` to reference `.env`:

```yaml
services:
  backend:
    environment:
      - DEBUG=1
      - SECRET_KEY=${SECRET_KEY}
      - DB_HOST=table-mountain.liara.cloud
      - DB_PORT=32965
      - DB_NAME=postgres
      - DB_USER=root
      - DB_PASSWORD=${DB_PASSWORD}  # ← From .env
      - REDIS_URL=redis://redis:6379/0
      - AWS_ACCESS_KEY_ID=minioadmin
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}  # ← From .env
      - LIARA_API_KEY=${LIARA_API_KEY}  # ← From .env
```

**Benefits:**
- Secrets not in Git
- Each developer can have different values
- Easy to update without editing docker-compose.yml

---

## Production Override Pattern

### Using docker-compose.prod.yml

**Base:** `docker-compose.yml` (development defaults)  
**Override:** `docker-compose.prod.yml` (production values)

**docker-compose.yml (dev):**
```yaml
services:
  backend:
    environment:
      - DEBUG=1
      - SECRET_KEY=${SECRET_KEY:-dev-secret-key}
      - DB_HOST=table-mountain.liara.cloud
      - DB_PORT=32965
      - ALLOWED_HOSTS=localhost,127.0.0.1
```

**docker-compose.prod.yml (production override):**
```yaml
services:
  backend:
    environment:
      - DEBUG=0  # Override to disable debug
      - SECRET_KEY=${SECRET_KEY}  # Require from .env (no default)
      - DB_HOST=marketnavigator-v2  # Private network
      - DB_PORT=5432
      - ALLOWED_HOSTS=market.kareonecompany.com,backend
```

**Usage:**
```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**How override works:**
- `environment:` sections are **REPLACED**, not merged
- Production override defines **all** variables again
- Variables not in prod override keep dev values

---

## Variable Substitution Syntax

### Basic Substitution

```yaml
environment:
  - VAR_NAME=${VAR_NAME}
```

**Behavior:**
- Loads value from `.env` file or shell environment
- **ERROR** if variable not set (compose will fail)

### With Default Value

```yaml
environment:
  - VAR_NAME=${VAR_NAME:-default_value}
```

**Behavior:**
- Uses `.env` value if set
- Falls back to `default_value` if not set
- **Safe:** Won't error if variable missing

### With Empty String Default

```yaml
environment:
  - VAR_NAME=${VAR_NAME:-}
```

**Behavior:**
- Uses `.env` value if set
- Sets to empty string if not set

### Require Variable (No Default)

```yaml
environment:
  - VAR_NAME=${VAR_NAME:?ERROR: VAR_NAME is required}
```

**Behavior:**
- Uses `.env` value if set
- **ERROR** with custom message if not set
- Good for mandatory variables

### Use Alternative Value

```yaml
environment:
  - VAR_NAME=${VAR_NAME:+alternative_value}
```

**Behavior:**
- If `VAR_NAME` is set, use `alternative_value`
- If not set, use empty string
- Rarely used

---

## Debugging Environment Variables

### Check Resolved Configuration

```bash
# See fully resolved docker-compose.yml with all substitutions
docker-compose config

# See only backend service config
docker-compose config backend

# Save resolved config to file
docker-compose config > resolved-compose.yml
```

**Output shows:**
- All `${VAR}` substitutions resolved
- Default values applied
- Final configuration that will be used

### Check Container Environment

```bash
# List all environment variables in running container
docker exec mn2-backend env

# Check specific variable
docker exec mn2-backend env | grep DB_PASSWORD

# Pretty print sorted
docker exec mn2-backend env | sort
```

### Check What .env File is Loaded

```bash
# Docker Compose looks for .env in:
# 1. Current directory
# 2. Project directory (if different)

# Verify which .env is being used
cat .env | head -5

# Check if variable is in .env
grep DB_PASSWORD .env
```

### Validate Before Starting

```bash
# Check if all required variables are set
docker-compose config --quiet && echo "✅ Config valid" || echo "❌ Config error"

# List undefined variables
docker-compose config 2>&1 | grep "variable is not set"
```

---

## Common Issues & Solutions

### Issue 1: Variable Not Substituted

**Symptom:**
```bash
docker exec mn2-backend env | grep DB_PASSWORD
# Shows: DB_PASSWORD=${DB_PASSWORD}
# Should show: DB_PASSWORD=secretpassword123
```

**Cause:** Using `env_file:` instead of `environment:` + substitution

**Solution:**
```yaml
# DON'T DO THIS (variable passed as-is)
services:
  backend:
    env_file:
      - .env

# DO THIS (variable substituted)
services:
  backend:
    environment:
      - DB_PASSWORD=${DB_PASSWORD}
```

### Issue 2: Variable Not Found

**Symptom:**
```bash
docker-compose up
# ERROR: The DB_PASSWORD variable is not set.
```

**Cause:** Variable not in `.env` file or shell environment

**Solution:**
```bash
# Check if .env exists
ls -la .env

# Check if variable is defined
grep DB_PASSWORD .env

# If missing, add to .env
echo "DB_PASSWORD=secretpassword" >> .env

# Or export in shell
export DB_PASSWORD=secretpassword
docker-compose up
```

### Issue 3: Using Old Variable Value

**Symptom:** Changed `.env` value but container still uses old value

**Cause:** Container wasn't recreated after `.env` change

**Solution:**
```bash
# Restart is NOT enough (uses same environment)
docker-compose restart backend  # ❌ Wrong

# Must recreate container
docker-compose up -d --force-recreate backend  # ✅ Correct

# Or stop and start
docker-compose stop backend
docker-compose up -d backend
```

### Issue 4: Production Using Development Values

**Symptom:** Production runs with `DEBUG=1`

**Cause:** Not using `docker-compose.prod.yml` override

**Solution:**
```bash
# WRONG (only uses docker-compose.yml)
docker-compose up -d

# CORRECT (merges prod overrides)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify
docker exec mn2-backend env | grep DEBUG
# Should show: DEBUG=0
```

### Issue 5: NEXT_PUBLIC_* Variables Not Working

**Symptom:** Frontend uses old API URL

**Cause:** Next.js bakes `NEXT_PUBLIC_*` variables at **build time**

**Solution:**
```bash
# Must rebuild after changing NEXT_PUBLIC_* variables
docker-compose build --no-cache frontend
docker-compose up -d frontend

# Or force rebuild
docker-compose up -d --build frontend
```

---

## Best Practices for MarketNavigator

### 1. Separate Sensitive from Non-Sensitive

**docker-compose.yml (public):**
```yaml
services:
  backend:
    environment:
      # Non-sensitive (hardcoded OK)
      - DEBUG=1
      - DB_HOST=table-mountain.liara.cloud
      - DB_PORT=32965
      - REDIS_URL=redis://redis:6379/0
      
      # Sensitive (from .env)
      - SECRET_KEY=${SECRET_KEY}
      - DB_PASSWORD=${DB_PASSWORD}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
```

**.env (private, not in Git):**
```bash
SECRET_KEY=dev-secret-key-change-in-production
DB_PASSWORD=AZ6t2MguosDdJ8oCval6B7bU
AWS_SECRET_ACCESS_KEY=minioadmin123
```

### 2. Provide Defaults for Optional Variables

```yaml
environment:
  # Required (no default)
  - DB_PASSWORD=${DB_PASSWORD}
  
  # Optional (with default)
  - LOG_LEVEL=${LOG_LEVEL:-INFO}
  - CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-4}
  - DEBUG=${DEBUG:-1}
```

### 3. Use docker-compose.prod.yml for All Production Differences

```yaml
# docker-compose.prod.yml
services:
  backend:
    environment:
      # Override ALL environment variables
      - DEBUG=0
      - SECRET_KEY=${SECRET_KEY:?Production SECRET_KEY required}
      - DB_HOST=marketnavigator-v2
      - ALLOWED_HOSTS=market.kareonecompany.com
      # ... all variables
```

### 4. Document Required Variables

Create `.env.example`:
```bash
# Required for all environments
SECRET_KEY=<GENERATE_RANDOM_50_CHARS>
DB_PASSWORD=<ASK_TEAM_FOR_PASSWORD>

# Optional (have defaults)
DEBUG=1
LOG_LEVEL=INFO
```

### 5. Validate Environment Before Deploy

Create `scripts/validate-env-compose.sh`:
```bash
#!/bin/bash

echo "Validating Docker Compose configuration..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi

# Test configuration
if ! docker-compose config --quiet; then
    echo "❌ Docker Compose configuration invalid"
    docker-compose config
    exit 1
fi

# Check for undefined variables
UNDEFINED=$(docker-compose config 2>&1 | grep "variable is not set")
if [ -n "$UNDEFINED" ]; then
    echo "❌ Undefined variables:"
    echo "$UNDEFINED"
    exit 1
fi

echo "✅ Docker Compose configuration valid"
```

---

## Quick Reference

```bash
# View resolved configuration
docker-compose config

# Start with explicit files
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check container environment
docker exec mn2-backend env

# Recreate container with new environment
docker-compose up -d --force-recreate backend

# Validate configuration
docker-compose config --quiet && echo "Valid" || echo "Invalid"

# Check which variables are substituted
docker-compose config | grep -E "DB_PASSWORD|SECRET_KEY"

# Test with different .env file
docker-compose --env-file .env.staging config
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** DevOps Team  
**Review Schedule:** When Docker Compose version updates or environment structure changes
