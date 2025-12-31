# Container Restart Policies & Log Management - MarketNavigator v2

## Purpose
Document container restart policies, log rotation configurations, and procedures for accessing logs across development and production environments. Ensure services recover automatically from failures while maintaining accessible logs for debugging.

---

## Container Restart Policies

### Current Configuration (docker-compose.yml)

All MarketNavigator services use **`restart: unless-stopped`** policy (except `minio-init`).

```yaml
services:
  backend:
    restart: unless-stopped
  
  redis:
    restart: unless-stopped
  
  minio:
    restart: unless-stopped
  
  minio-init:
    # No restart policy (runs once and exits)
```

---

## Docker Restart Policy Options

### 1. `no` (Default)

**Behavior:**
- Container never restarts automatically
- Manual restart required: `docker start <container>`

**When to use:**
- Development debugging (prevent auto-restart during troubleshooting)
- One-time initialization containers

**Example:**
```yaml
services:
  debug-container:
    restart: no
```

### 2. `always`

**Behavior:**
- Always restart on failure
- Restart on server reboot
- **Even restarts if manually stopped** (keeps restarting until `docker stop` used)

**When to use:**
- Critical production services that must always run
- Services that should survive server reboots

**Example:**
```yaml
services:
  backend:
    restart: always
```

**Production recommendation:**
```bash
# Change to "always" for production
docker update --restart=always mn2-backend mn2-celery-worker
```

### 3. `on-failure[:max-retries]`

**Behavior:**
- Restart only if container exits with non-zero status
- Optional: Limit retry attempts
- Does NOT restart if manually stopped

**When to use:**
- Services that might fail temporarily (network issues, external dependencies)
- Want to limit restart storms

**Example:**
```yaml
services:
  scraper:
    restart: on-failure:5  # Retry max 5 times
```

### 4. `unless-stopped` (Current Setting)

**Behavior:**
- Restart on failure
- Restart on server reboot
- **Does NOT restart if manually stopped** (respects `docker stop`)

**When to use:**
- Development environments (can stop services without them restarting)
- Production with manual control (can stop for maintenance)

**Example:**
```yaml
services:
  backend:
    restart: unless-stopped
```

---

## Recommended Restart Policies by Environment

### Development

```yaml
services:
  redis:
    restart: unless-stopped  # Can stop for debugging
  
  backend:
    restart: unless-stopped  # Can stop for testing
  
  frontend:
    restart: unless-stopped
  
  celery-worker:
    restart: unless-stopped
  
  minio-init:
    # No restart (one-time setup)
```

### Production

```yaml
services:
  redis:
    restart: always  # Critical - must always run
  
  backend:
    restart: always  # Critical - must always run
  
  frontend:
    restart: always  # Critical - must always run
  
  celery-worker:
    restart: always  # Critical - must always run
  
  nginx:
    restart: always  # Critical - must always run
```

---

## Changing Restart Policies

### Via docker-compose.yml

```yaml
# Edit docker-compose.prod.yml
services:
  backend:
    restart: always  # Change from unless-stopped to always
```

Then apply:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Via Docker CLI (Without Recreating Container)

```bash
# Change single service
docker update --restart=always mn2-backend

# Change multiple services
docker update --restart=always mn2-backend mn2-frontend mn2-celery-worker

# Change all MarketNavigator containers
docker ps --filter "name=mn2-" --format "{{.Names}}" | xargs docker update --restart=always

# Verify changes
docker inspect mn2-backend | grep -A 5 RestartPolicy
```

---

## Restart Behavior Examples

### Scenario 1: Container Crashes

```bash
# Service exits with error
# Restart policy: unless-stopped

# What happens:
# - Docker automatically restarts container
# - Exponential backoff delay (starts at 100ms, increases to max 1 minute)
# - Logs show restart reason
```

**View restart count:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep mn2-
# Output: mn2-backend    Up 2 minutes (restarted 3 times)
```

### Scenario 2: Manual Stop

```bash
# Stop service manually
docker stop mn2-backend

# Restart policy: unless-stopped
# Result: Container stays stopped

# Restart policy: always
# Result: Container restarts immediately
```

### Scenario 3: Server Reboot

```bash
# Server reboots
sudo reboot

# After reboot, with restart: unless-stopped
# - Containers that were running before reboot: START
# - Containers that were manually stopped: STAY STOPPED

# After reboot, with restart: always
# - All containers: START (regardless of previous state)
```

### Scenario 4: Docker Daemon Restart

```bash
# Restart Docker daemon
sudo systemctl restart docker

# Restart policy: unless-stopped or always
# Result: All containers restart (as if server rebooted)

# Restart policy: no
# Result: Containers stay stopped
```

---

## Health Checks and Restart Logic

### Current Health Checks

```yaml
services:
  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
  
  minio:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
  
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**How health checks affect restarts:**
- If health check fails `retries` times → Container marked "unhealthy"
- Container continues running (NOT restarted automatically)
- Dependent services won't start until dependency is healthy
- Use `docker-compose ps` to see health status

**Check health status:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# Shows: Up 10 minutes (healthy) or Up 10 minutes (unhealthy)
```

---

## Log Management

### Log Drivers

#### Default JSON File Driver (Current)

```yaml
services:
  backend:
    logging:
      driver: json-file
      options:
        max-size: "10m"      # Max log file size
        max-file: "3"        # Number of rotated files
        labels: "service"
        env: "ENVIRONMENT"
```

**Pros:**
- Simple, no external dependencies
- Works with `docker logs` command
- Automatic rotation

**Cons:**
- Limited to local storage
- No centralized logging
- Manual cleanup needed for old containers

#### Alternative: Syslog Driver

```yaml
services:
  backend:
    logging:
      driver: syslog
      options:
        syslog-address: "tcp://log-server:514"
        tag: "{{.Name}}/{{.ID}}"
```

#### Alternative: Loki Driver (Grafana)

```yaml
services:
  backend:
    logging:
      driver: loki
      options:
        loki-url: "http://loki:3100/loki/api/v1/push"
        loki-batch-size: "400"
```

---

### Accessing Logs

#### View Real-Time Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Multiple services
docker-compose logs -f backend celery-worker

# With timestamps
docker-compose logs -f -t backend

# Last N lines
docker-compose logs --tail=100 backend
```

#### View Historical Logs

```bash
# All logs for backend
docker-compose logs backend > backend_logs.txt

# Logs since specific time
docker-compose logs --since="2025-12-31T10:00:00" backend

# Logs between time range
docker-compose logs --since="2025-12-31T10:00:00" --until="2025-12-31T12:00:00" backend

# Logs for stopped container
docker logs mn2-backend
```

#### Search Logs

```bash
# Search for errors
docker-compose logs backend | grep ERROR

# Search for specific request
docker-compose logs backend | grep "/api/reports/123"

# Count errors
docker-compose logs backend | grep ERROR | wc -l

# Show context around match
docker-compose logs backend | grep -A 5 -B 5 ERROR
```

---

### Log Rotation Configuration

#### Recommended Production Settings

Add to `docker-compose.prod.yml`:

```yaml
services:
  backend:
    logging:
      driver: json-file
      options:
        max-size: "50m"     # 50 MB per file
        max-file: "10"      # Keep 10 rotated files = 500 MB total
        compress: "true"    # Compress rotated files
        labels: "service,environment"
  
  celery-worker:
    logging:
      driver: json-file
      options:
        max-size: "100m"    # Larger for worker (more verbose)
        max-file: "5"
        compress: "true"
  
  frontend:
    logging:
      driver: json-file
      options:
        max-size: "20m"     # Smaller for frontend
        max-file: "5"
        compress: "true"
```

#### Apply Log Rotation

```bash
# Restart services to apply new logging config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or update running container
docker update --log-opt max-size=50m --log-opt max-file=10 mn2-backend
```

---

### Log Location on Host

#### Find Log Files

```bash
# Show log file path for container
docker inspect mn2-backend | grep LogPath
# Output: "LogPath": "/var/lib/docker/containers/<container-id>/<container-id>-json.log"

# View log file directly
sudo tail -f /var/lib/docker/containers/<container-id>/<container-id>-json.log
```

#### Log Disk Usage

```bash
# Check Docker log disk usage
sudo du -sh /var/lib/docker/containers/*/

# Find largest log files
sudo du -h /var/lib/docker/containers/*/*.log | sort -h | tail -10

# Check specific container logs
docker inspect mn2-backend --format='{{.LogPath}}' | xargs sudo du -h
```

---

### Centralized Logging (Production)

#### Option 1: Loki + Grafana Stack

**docker-compose.prod.yml:**
```yaml
services:
  loki:
    image: grafana/loki:latest
    container_name: mn2-loki
    ports:
      - "3100:3100"
    volumes:
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
  
  grafana:
    image: grafana/grafana:latest
    container_name: mn2-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
  
  promtail:
    image: grafana/promtail:latest
    container_name: mn2-promtail
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail-config.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml

volumes:
  loki_data:
  grafana_data:
```

#### Option 2: ELK Stack (Elasticsearch, Logstash, Kibana)

```yaml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
    volumes:
      - es_data:/usr/share/elasticsearch/data
  
  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
  
  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200

volumes:
  es_data:
```

---

## Monitoring Restart Events

### View Restart History

```bash
# Show container restart count
docker ps --format "table {{.Names}}\t{{.Status}}"
# Output shows: Up 2 hours (restarted 5 times)

# View container events
docker events --filter container=mn2-backend --since 24h

# View restart timestamps
docker inspect mn2-backend | jq '.[0].State'
```

### Alerts for Restart Loops

#### Create Alert Script

```bash
# Save as /usr/local/bin/alert-restart-loop.sh
#!/bin/bash

THRESHOLD=5
CONTAINERS=$(docker ps --filter "name=mn2-" --format "{{.Names}}")

for container in $CONTAINERS; do
    RESTARTS=$(docker inspect $container --format='{{.RestartCount}}')
    
    if [ "$RESTARTS" -gt "$THRESHOLD" ]; then
        echo "Alert: $container has restarted $RESTARTS times"
        
        # Send alert (example: email)
        echo "$container restarted $RESTARTS times" | \
          mail -s "Docker Container Restart Alert" admin@company.com
        
        # Log to syslog
        logger -t docker-alert "$container restarted $RESTARTS times"
    fi
done
```

**Run via cron:**
```bash
# Run every 5 minutes
*/5 * * * * /usr/local/bin/alert-restart-loop.sh
```

---

## Best Practices

### ✅ Production Recommendations

1. **Use `restart: always`** for all critical services
2. **Configure health checks** for all services
3. **Set log rotation** (max-size: 50m, max-file: 10)
4. **Enable log compression** for rotated files
5. **Monitor restart counts** with alerts
6. **Use centralized logging** (Loki/ELK)
7. **Set up log aggregation** before production
8. **Regular log cleanup** (automated)

### ⚠️ Development Recommendations

1. **Use `restart: unless-stopped`** for flexibility
2. **Keep detailed logs** (less rotation)
3. **Monitor logs during development** (docker-compose logs -f)
4. **Test restart behavior** before production
5. **Document restart policies** in docker-compose.yml

---

## Troubleshooting

### Container Keeps Restarting (Restart Loop)

```bash
# 1. Check restart count
docker ps --format "{{.Names}}: {{.Status}}"

# 2. View logs for errors
docker logs --tail=100 mn2-backend

# 3. Check health status
docker inspect mn2-backend | jq '.[0].State.Health'

# 4. Stop auto-restart temporarily
docker update --restart=no mn2-backend
docker logs mn2-backend  # Debug without restarts

# 5. Fix issue, then re-enable restart
docker update --restart=always mn2-backend
```

### Logs Not Rotating

```bash
# 1. Check current logging config
docker inspect mn2-backend | jq '.[0].HostConfig.LogConfig'

# 2. Verify max-size and max-file are set
# Should show: "max-size": "50m", "max-file": "10"

# 3. If not set, update
docker update --log-opt max-size=50m --log-opt max-file=10 mn2-backend

# 4. Restart container to apply
docker restart mn2-backend
```

### Cannot Access Logs

```bash
# 1. Check if container exists
docker ps -a | grep mn2-backend

# 2. If stopped, view logs
docker logs mn2-backend

# 3. If removed, check Docker logs directory
sudo ls -lh /var/lib/docker/containers/

# 4. If log driver changed, check new location
docker inspect mn2-backend | jq '.[0].HostConfig.LogConfig'
```

### Logs Consuming Too Much Disk Space

```bash
# 1. Check disk usage
sudo du -sh /var/lib/docker/containers/*/

# 2. Find largest logs
sudo du -h /var/lib/docker/containers/*/*.log | sort -h | tail -10

# 3. Reduce log retention
docker update --log-opt max-size=10m --log-opt max-file=3 mn2-backend

# 4. Clean up old logs (CAUTION: deletes logs)
docker system prune -a --volumes
```

---

## Quick Reference

### Restart Policy Commands

```bash
# View current restart policy
docker inspect mn2-backend | grep RestartPolicy -A 3

# Change to always restart
docker update --restart=always mn2-backend

# Disable auto-restart
docker update --restart=no mn2-backend

# Set restart on-failure with max retries
docker update --restart=on-failure:5 mn2-backend
```

### Log Commands

```bash
# View live logs
docker-compose logs -f backend

# View last 100 lines
docker-compose logs --tail=100 backend

# Search logs for errors
docker-compose logs backend | grep ERROR

# View logs with timestamps
docker-compose logs -t backend

# Export logs to file
docker-compose logs backend > logs_$(date +%Y%m%d_%H%M%S).txt

# Check log rotation settings
docker inspect mn2-backend | jq '.[0].HostConfig.LogConfig'

# Find log file location
docker inspect mn2-backend --format='{{.LogPath}}'
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** DevOps Team  
**Review Schedule:** Quarterly + After incidents involving service restarts
