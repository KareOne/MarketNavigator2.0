# Local Development Commands - MarketNavigator v2

## Purpose
Standardized commands for running, stopping, and testing MarketNavigator locally with Docker Compose. Use these commands consistently across the team to ensure reproducible development environments.

---

## Quick Start (New Developers)

```bash
# 1. Clone repository
git clone https://github.com/your-org/MarketNavigator2.0.git
cd MarketNavigator2.0

# 2. Configure environment (if .env tracked)
# Project tracks .env in Git - verify values
cat .env

# OR if .env not tracked:
# cp .env.example .env
# nano .env  # Fill in required values

# 3. Start all services
docker-compose up -d

# 4. View logs
docker-compose logs -f

# 5. Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# MinIO Console: http://localhost:9001
# Flower (Celery): http://localhost:5555
```

---

## Core Commands

### Start Services

```bash
# Start all services in background
docker-compose up -d

# Start with logs visible
docker-compose up

# Start specific services only
docker-compose up -d backend frontend redis

# Start and rebuild if code changed
docker-compose up -d --build

# Force recreate containers (reset state)
docker-compose up -d --force-recreate
```

### Stop Services

```bash
# Stop all services (containers remain)
docker-compose stop

# Stop specific service
docker-compose stop backend

# Stop and remove containers (keeps volumes)
docker-compose down

# Stop and remove containers + volumes (⚠️ deletes data)
docker-compose down -v

# Stop and remove containers + images
docker-compose down --rmi all
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend

# Restart multiple services
docker-compose restart backend celery-worker
```

### View Status

```bash
# List running containers
docker-compose ps

# Show detailed status
docker-compose ps -a

# Show resource usage
docker stats

# Check service health
docker-compose ps | grep -E "Up|healthy"
```

---

## Viewing Logs

### Real-Time Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend

# View multiple services
docker-compose logs -f backend celery-worker

# View with timestamps
docker-compose logs -f -t backend

# View last N lines
docker-compose logs --tail=100 backend

# Follow logs from specific time
docker-compose logs -f --since="2025-12-31T10:00:00"
```

### Log Filtering

```bash
# Show only errors
docker-compose logs backend | grep ERROR

# Show only Django logs (not static file requests)
docker-compose logs backend | grep -v "GET /static"

# Search for specific pattern
docker-compose logs backend | grep "api/reports"

# Count log lines
docker-compose logs backend --tail=1000 | wc -l
```

---

## Database Operations

### Django Migrations

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create migrations
docker-compose exec backend python manage.py makemigrations

# Show migration status
docker-compose exec backend python manage.py showmigrations

# Migrate specific app
docker-compose exec backend python manage.py migrate chat

# Rollback migration
docker-compose exec backend python manage.py migrate chat 0003_previous_migration
```

### Database Shell

```bash
# PostgreSQL shell
docker-compose exec backend python manage.py dbshell

# Example queries
docker-compose exec backend python manage.py dbshell << 'EOF'
SELECT COUNT(*) FROM users_user;
SELECT * FROM reports_report ORDER BY created_at DESC LIMIT 5;
EOF
```

### Database Backup/Restore

```bash
# Backup database
docker-compose exec backend python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json

# Backup specific app
docker-compose exec backend python manage.py dumpdata users > users_backup.json

# Restore database
docker-compose exec -T backend python manage.py loaddata < backup.json

# Flush database (⚠️ deletes all data)
docker-compose exec backend python manage.py flush --noinput
```

---

## Django Management Commands

### Django Shell

```bash
# Python shell
docker-compose exec backend python manage.py shell

# Run one-liner
docker-compose exec backend python manage.py shell -c "from users.models import User; print(User.objects.count())"

# Interactive Python shell
docker-compose exec -it backend python manage.py shell
# >>> from users.models import User
# >>> User.objects.all()
```

### Create Superuser

```bash
# Interactive superuser creation
docker-compose exec -it backend python manage.py createsuperuser

# Non-interactive (for scripts)
docker-compose exec backend python manage.py createsuperuser \
  --username admin \
  --email admin@example.com \
  --noinput
```

### Static Files

```bash
# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput

# Clear static files
docker-compose exec backend python manage.py collectstatic --clear --noinput
```

---

## Celery Operations

### Monitor Celery Workers

```bash
# View Celery worker logs
docker-compose logs -f celery-worker

# Check active tasks
docker-compose exec celery-worker celery -A config inspect active

# Check registered tasks
docker-compose exec celery-worker celery -A config inspect registered

# Check worker stats
docker-compose exec celery-worker celery -A config inspect stats
```

### Manage Celery Tasks

```bash
# Revoke running task
docker-compose exec celery-worker celery -A config revoke <task-id>

# Purge all pending tasks
docker-compose exec celery-worker celery -A config purge

# List scheduled tasks (Celery Beat)
docker-compose exec celery-beat celery -A config inspect scheduled
```

### Access Flower Dashboard

```bash
# Flower runs on http://localhost:5555
# Username: admin
# Password: admin123 (from docker-compose.yml)

# Open in browser
open http://localhost:5555  # macOS
xdg-open http://localhost:5555  # Linux
```

---

## Testing

### Run Django Tests

```bash
# Run all tests
docker-compose exec backend python manage.py test

# Run specific app tests
docker-compose exec backend python manage.py test users

# Run specific test file
docker-compose exec backend python manage.py test users.tests.test_models

# Run with verbose output
docker-compose exec backend python manage.py test --verbosity=2

# Run with coverage
docker-compose exec backend coverage run manage.py test
docker-compose exec backend coverage report
docker-compose exec backend coverage html
```

### Run Frontend Tests

```bash
# Run Next.js tests
docker-compose exec frontend npm test

# Run with watch mode
docker-compose exec frontend npm test -- --watch

# Run linting
docker-compose exec frontend npm run lint

# Run type checking
docker-compose exec frontend npm run type-check
```

### Integration Testing

```bash
# Test backend API endpoint
curl http://localhost:8000/api/health/
# Expected: {"status":"healthy"}

# Test frontend
curl -I http://localhost:3000
# Expected: HTTP/1.1 200 OK

# Test MinIO
curl http://localhost:9000/minio/health/live
# Expected: 200 OK

# Test Redis
docker-compose exec redis redis-cli ping
# Expected: PONG
```

---

## Rebuilding Services

### Full Rebuild

```bash
# Stop all services
docker-compose down

# Rebuild all images (no cache)
docker-compose build --no-cache

# Start with rebuilt images
docker-compose up -d

# Or combine into one command
docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

### Rebuild Specific Service

```bash
# Rebuild backend only
docker-compose build --no-cache backend

# Rebuild and restart backend
docker-compose up -d --build backend

# Rebuild frontend (needed after dependency changes)
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### When to Rebuild

**Rebuild backend if:**
- Changed `backend/requirements.txt`
- Changed `backend/Dockerfile`
- Python version changed

**Rebuild frontend if:**
- Changed `frontend/package.json`
- Changed `frontend/Dockerfile`
- Changed `NEXT_PUBLIC_*` environment variables
- Node.js version changed

---

## Cleaning Up

### Remove Stopped Containers

```bash
# Remove all stopped containers
docker container prune

# Remove specific stopped container
docker rm mn2-backend

# Remove all MarketNavigator containers
docker ps -a | grep mn2- | awk '{print $1}' | xargs docker rm
```

### Remove Unused Images

```bash
# Remove dangling images
docker image prune

# Remove all unused images
docker image prune -a

# Remove specific image
docker rmi marketnavigator20-backend
```

### Remove Volumes

```bash
# ⚠️ WARNING: This deletes data!

# List volumes
docker volume ls

# Remove specific volume
docker volume rm mn2_redis_data

# Remove all unused volumes
docker volume prune

# Remove all MarketNavigator volumes
docker volume ls | grep mn2_ | awk '{print $2}' | xargs docker volume rm
```

### Complete Cleanup

```bash
# ⚠️ WARNING: Deletes everything (containers, images, volumes)

# Stop all services
docker-compose down -v --rmi all

# Remove all MarketNavigator-related Docker resources
docker system prune -a --volumes

# Start fresh
docker-compose up -d --build
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs backend

# Check if port is already in use
sudo lsof -i :8000  # Backend
sudo lsof -i :3000  # Frontend
sudo lsof -i :6379  # Redis

# Force recreate container
docker-compose up -d --force-recreate backend

# Check Docker daemon
sudo systemctl status docker
```

### Database Connection Issues

```bash
# Test database connection
docker-compose exec backend python manage.py check --database default

# Verify database credentials
docker-compose exec backend env | grep DB_

# Check PostgreSQL logs (if running locally)
docker-compose logs postgres

# Test connection manually
docker-compose exec backend python manage.py shell -c "
from django.db import connection
connection.ensure_connection()
print('Database connection successful')
"
```

### Redis Issues

```bash
# Test Redis connection
docker-compose exec redis redis-cli ping
# Expected: PONG

# Check Redis logs
docker-compose logs redis

# Flush Redis cache
docker-compose exec redis redis-cli FLUSHALL

# Restart Redis
docker-compose restart redis
```

### Frontend Won't Load

```bash
# Check frontend logs
docker-compose logs frontend

# Check if Next.js build succeeded
docker-compose exec frontend ls -la /app/.next

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend

# Check environment variables
docker-compose exec frontend env | grep NEXT_PUBLIC
```

### Celery Tasks Not Running

```bash
# Check Celery worker logs
docker-compose logs celery-worker

# Check if workers are consuming tasks
docker-compose exec celery-worker celery -A config inspect active

# Restart Celery worker
docker-compose restart celery-worker

# Purge stuck tasks
docker-compose exec celery-worker celery -A config purge
```

---

## Development Workflow Aliases

### Bash Aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# MarketNavigator aliases
alias mnu='docker-compose up -d'  # Start all services
alias mnd='docker-compose down'  # Stop all services
alias mnr='docker-compose restart'  # Restart services
alias mnl='docker-compose logs -f'  # View logs
alias mnps='docker-compose ps'  # List services
alias mnsh='docker-compose exec backend python manage.py shell'  # Django shell
alias mndb='docker-compose exec backend python manage.py dbshell'  # DB shell
alias mntest='docker-compose exec backend python manage.py test'  # Run tests
alias mnmig='docker-compose exec backend python manage.py migrate'  # Run migrations
alias mnmake='docker-compose exec backend python manage.py makemigrations'  # Create migrations
alias mnbuild='docker-compose build --no-cache'  # Rebuild all images
alias mnclean='docker-compose down -v && docker system prune -f'  # Clean everything
```

**Usage after adding aliases:**
```bash
source ~/.bashrc  # Reload config
mnu  # Start services
mnl backend  # View backend logs
mnsh  # Open Django shell
```

---

## Useful Scripts

### Start Fresh Development Environment

Save as `scripts/dev-start.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting MarketNavigator development environment..."

# Ensure we're in project root
cd "$(dirname "$0")/.."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull origin develop

# Stop existing services
echo "🛑 Stopping existing services..."
docker-compose down

# Rebuild images
echo "🔨 Rebuilding images..."
docker-compose build

# Start services
echo "▶️  Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Run migrations
echo "🗄️  Running database migrations..."
docker-compose exec backend python manage.py migrate

# Check status
echo "✅ Services started:"
docker-compose ps

echo ""
echo "🎉 Development environment ready!"
echo "Frontend: http://localhost:3000"
echo "Backend: http://localhost:8000"
echo "Flower: http://localhost:5555"
echo ""
echo "View logs with: docker-compose logs -f"
```

**Usage:**
```bash
chmod +x scripts/dev-start.sh
./scripts/dev-start.sh
```

### Run All Tests

Save as `scripts/test-all.sh`:

```bash
#!/bin/bash
set -e

echo "🧪 Running all tests..."

# Backend tests
echo "Testing backend..."
docker-compose exec backend python manage.py test --verbosity=2

# Frontend linting
echo "Linting frontend..."
docker-compose exec frontend npm run lint

# Frontend tests (if exists)
# docker-compose exec frontend npm test

echo "✅ All tests passed!"
```

---

## Quick Reference

```bash
# Start development
docker-compose up -d

# Stop development
docker-compose down

# View logs
docker-compose logs -f backend

# Django shell
docker-compose exec backend python manage.py shell

# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec -it backend python manage.py createsuperuser

# Run tests
docker-compose exec backend python manage.py test

# Rebuild service
docker-compose up -d --build backend

# Clean and restart
docker-compose down -v && docker-compose up -d --build

# Check service status
docker-compose ps

# Monitor Celery
open http://localhost:5555

# Check Redis
docker-compose exec redis redis-cli ping
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** Development Team  
**Review Schedule:** When new services added or workflow changes
