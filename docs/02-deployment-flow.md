# Production Deployment Flow - MarketNavigator v2

## Purpose
Step-by-step production deployment procedure for Ubuntu servers. Follow this guide for initial deployments, updates, and rollbacks to ensure zero-downtime releases.

---

## Prerequisites

### Server Requirements
- **OS:** Ubuntu 22.04 LTS or newer
- **RAM:** 8GB minimum (16GB recommended)
- **CPU:** 4 cores minimum
- **Disk:** 50GB minimum (100GB recommended for data growth)
- **Network:** Public IP with ports 80/443 open

### Required Software
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

### Domain & DNS Setup
1. Point your domain to server IP: `market.kareonecompany.com → YOUR_SERVER_IP`
2. Verify DNS propagation: `dig market.kareonecompany.com`
3. Wait 5-10 minutes for propagation (up to 48 hours in some cases)

---

## Initial Deployment (First Time)

### Step 1: Clone Repository

```bash
# SSH into server
ssh your-user@your-server-ip

# Clone repository
cd /opt
sudo mkdir -p marketnavigator
sudo chown $USER:$USER marketnavigator
cd marketnavigator
git clone https://github.com/your-org/MarketNavigator2.0.git
cd MarketNavigator2.0

# Verify branch
git branch
# Should be on 'main' branch
```

### Step 2: Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit production environment
nano .env
```

**Required variables (update these):**
```bash
# Django
SECRET_KEY=GENERATE_STRONG_RANDOM_KEY_HERE
DEBUG=0
ALLOWED_HOSTS=market.kareonecompany.com,backend,localhost
CORS_ALLOWED_ORIGINS=https://market.kareonecompany.com

# Database (Liara Private Network)
DB_HOST=marketnavigator-v2
DB_PORT=5432
DB_NAME=postgres
DB_USER=root
DB_PASSWORD=YOUR_ACTUAL_PASSWORD

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# MinIO
USE_S3=True
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=CHANGE_THIS_IN_PRODUCTION
AWS_STORAGE_BUCKET_NAME=marketnavigator-files
AWS_S3_ENDPOINT_URL=http://minio:9000

# AI Keys
LIARA_API_KEY=your_liara_api_key
LIARA_BASE_URL=https://ai.liara.ir/api/YOUR_PROJECT_ID/v1
LIARA_MODEL=google/gemini-2.5-flash
METIS_API_KEY=your_metis_key
OPENAI_API_KEY=your_openai_key

# Scraper URLs (internal)
CRUNCHBASE_SCRAPER_URL=http://crunchbase_api:8003
TRACXN_SCRAPER_URL=http://tracxn_api:8008

# Next.js
NEXT_PUBLIC_API_URL=https://market.kareonecompany.com
NEXT_PUBLIC_WS_URL=wss://market.kareonecompany.com
```

**Generate strong SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 3: Configure Scraper APIs

```bash
# Crunchbase API environment
nano scrapers/Crunchbase_API/.env
```
Add Crunchbase database credentials.

```bash
# Tracxn API configuration
nano scrapers/Tracxn_API/config.py
```
Update MySQL connection details.

### Step 4: SSL Certificate Setup

```bash
# Create SSL directory
mkdir -p nginx/ssl

# Run SSL setup script (uses Let's Encrypt)
chmod +x scripts/setup-ssl.sh
./scripts/setup-ssl.sh market.kareonecompany.com
```

**Manual SSL (if script fails):**
```bash
# Install certbot
sudo apt install certbot

# Generate certificate
sudo certbot certonly --standalone -d market.kareonecompany.com

# Copy certificates
sudo cp /etc/letsencrypt/live/market.kareonecompany.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/market.kareonecompany.com/privkey.pem nginx/ssl/
sudo chown $USER:$USER nginx/ssl/*.pem
```

### Step 5: Build and Start Services

```bash
# Build images (first time only)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache

# Start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Monitor startup logs
docker-compose logs -f
# Press Ctrl+C when all services are healthy
```

### Step 6: Database Migrations

```bash
# Run Django migrations
docker exec mn2-backend python manage.py migrate

# Create superuser
docker exec -it mn2-backend python manage.py createsuperuser

# Collect static files
docker exec mn2-backend python manage.py collectstatic --noinput
```

### Step 7: Verify Deployment

```bash
# Check all services are running
docker-compose ps
# All services should show "Up" or "Up (healthy)"

# Test backend health
curl https://market.kareonecompany.com/api/health/
# Expected: {"status": "healthy"}

# Test frontend
curl -I https://market.kareonecompany.com
# Expected: HTTP/2 200

# Check Celery workers
docker exec mn2-celery-worker celery -A config inspect active

# View logs
docker-compose logs backend --tail 100
docker-compose logs frontend --tail 100
```

### Step 8: Configure Auto-Restart on Reboot

```bash
# Enable Docker service
sudo systemctl enable docker

# Verify services restart on reboot
sudo reboot

# After reboot, check services
docker-compose ps
```

---

## Regular Updates (Code Deployment)

### Pre-Deployment Checklist
- [ ] Changes tested locally
- [ ] All tests passing
- [ ] PR reviewed and merged to `main`
- [ ] Database migrations reviewed (if any)
- [ ] Backup completed (see step 1)

### Deployment Steps

#### 1. Backup Current State

```bash
cd /opt/marketnavigator/MarketNavigator2.0

# Backup database (if using local PostgreSQL)
docker exec mn2-backend python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json

# Backup volumes
docker run --rm -v mn2_minio_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/minio_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
docker run --rm -v mn2_redis_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/redis_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

#### 2. Pull Latest Code

```bash
# Fetch latest changes
git fetch origin main

# Check what's changing
git log HEAD..origin/main --oneline

# Pull changes
git pull origin main
```

#### 3. Update Dependencies (if needed)

```bash
# Check if requirements changed
git diff HEAD@{1} backend/requirements.txt
git diff HEAD@{1} frontend/package.json

# Rebuild if dependencies changed
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build backend
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build frontend
```

#### 4. Apply Migrations

```bash
# Check for new migrations
docker exec mn2-backend python manage.py showmigrations

# Apply migrations
docker exec mn2-backend python manage.py migrate

# Collect static files (if static files changed)
docker exec mn2-backend python manage.py collectstatic --noinput
```

#### 5. Restart Services (Zero-Downtime)

```bash
# Restart backend (Daphne reloads automatically in dev, but not prod)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# Restart Celery workers (to pick up task changes)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart celery-worker celery-beat

# Restart frontend (Next.js)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart frontend

# Reload nginx (config changes)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
```

#### 6. Verify Deployment

```bash
# Check service status
docker-compose ps

# Test health endpoint
curl https://market.kareonecompany.com/api/health/

# Check logs for errors
docker-compose logs backend --tail 100 --follow
docker-compose logs frontend --tail 50
docker-compose logs celery-worker --tail 50
```

#### 7. Monitor for Issues (First 15 Minutes)

```bash
# Watch logs in real-time
docker-compose logs -f backend celery-worker frontend

# Check Celery task queue
docker exec mn2-celery-worker celery -A config inspect active

# Monitor resource usage
docker stats
```

---

## Rollback Procedure (If Deployment Fails)

### Quick Rollback (Within 30 Minutes)

```bash
# Stop current services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Revert to previous commit
git log --oneline -10
git reset --hard <PREVIOUS_COMMIT_HASH>

# Rebuild and restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify
curl https://market.kareonecompany.com/api/health/
```

### Database Rollback (If Migrations Failed)

```bash
# Restore database backup
docker exec -i mn2-backend python manage.py loaddata < backup_TIMESTAMP.json

# Or revert migrations
docker exec mn2-backend python manage.py migrate app_name PREVIOUS_MIGRATION_NUMBER
```

---

## Emergency Procedures

### Complete Service Restart

```bash
cd /opt/marketnavigator/MarketNavigator2.0

# Stop all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Remove stopped containers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml rm -f

# Start fresh
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Monitor startup
docker-compose logs -f
```

### Container Rebuild (Corrupted State)

```bash
# Stop service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop backend

# Remove container
docker rm mn2-backend

# Rebuild image
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build backend

# Start service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
```

### Clear Cache (Redis Issues)

```bash
# Flush Redis cache
docker exec mn2-redis redis-cli FLUSHDB

# Or restart Redis
docker-compose restart redis
```

---

## Deployment Script (Automated)

Create `scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting MarketNavigator v2 Deployment..."

# Navigate to project directory
cd /opt/marketnavigator/MarketNavigator2.0

# Pull latest code
echo "📥 Pulling latest code from main branch..."
git pull origin main

# Build services
echo "🔨 Building Docker images..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Apply migrations
echo "🗃️  Applying database migrations..."
docker exec mn2-backend python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
docker exec mn2-backend python manage.py collectstatic --noinput

# Restart services
echo "♻️  Restarting services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart backend celery-worker celery-beat frontend

# Health check
echo "🏥 Running health check..."
sleep 5
curl -f https://market.kareonecompany.com/api/health/ || {
    echo "❌ Health check failed! Check logs with: docker-compose logs backend"
    exit 1
}

echo "✅ Deployment completed successfully!"
echo "📊 View logs: docker-compose logs -f backend"
```

**Usage:**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

---

## Common Deployment Issues

### Issue: Port Already in Use
**Symptom:** `bind: address already in use`

**Solution:**
```bash
# Find process using port
sudo lsof -i :80
sudo lsof -i :443

# Kill process or stop conflicting service
sudo systemctl stop apache2
sudo systemctl stop nginx
```

### Issue: Container Won't Start
**Symptom:** Container exits immediately

**Solution:**
```bash
# Check logs
docker logs mn2-backend --tail 100

# Common causes:
# - Missing environment variables
# - Database connection failed
# - Port conflict
```

### Issue: 502 Bad Gateway
**Symptom:** Nginx shows 502 error

**Solution:**
```bash
# Check backend is running
docker ps | grep backend

# Check backend logs
docker logs mn2-backend --tail 50

# Restart backend
docker-compose restart backend

# Check nginx logs
docker logs mn2-nginx --tail 50
```

### Issue: Static Files Not Loading
**Symptom:** CSS/JS 404 errors

**Solution:**
```bash
# Collect static files
docker exec mn2-backend python manage.py collectstatic --noinput

# Verify volume mount
docker inspect mn2-backend | grep -A 10 Mounts

# Restart nginx
docker-compose restart nginx
```

---

## Post-Deployment Monitoring

### First 24 Hours Checklist
- [ ] Monitor error logs: `docker-compose logs -f | grep ERROR`
- [ ] Check Celery task success rate: Access Flower at `http://YOUR_IP:5555`
- [ ] Verify file uploads work (MinIO)
- [ ] Test report generation end-to-end
- [ ] Monitor disk usage: `df -h`
- [ ] Monitor memory usage: `free -h`
- [ ] Check SSL certificate: `curl -vI https://market.kareonecompany.com 2>&1 | grep subject`

### Automated Monitoring (Recommended)

```bash
# Install monitoring agent (example: Prometheus + Grafana)
# Or use cloud monitoring (Datadog, New Relic, etc.)

# Set up log aggregation
docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions

# Configure alerts for:
# - Container down
# - High memory usage (>80%)
# - High disk usage (>85%)
# - SSL expiring (<30 days)
```

---

## SSL Certificate Renewal

SSL certificates expire every 90 days. Set up auto-renewal:

```bash
# Add cron job for auto-renewal
sudo crontab -e
```

Add this line:
```cron
0 0 * * 0 certbot renew --quiet --post-hook "docker-compose -f /opt/marketnavigator/MarketNavigator2.0/docker-compose.yml -f /opt/marketnavigator/MarketNavigator2.0/docker-compose.prod.yml restart nginx"
```

**Manual renewal:**
```bash
sudo certbot renew
docker-compose restart nginx
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** DevOps Team  
**Next Review:** 2026-03-31
