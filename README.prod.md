# MarketNavigator v2 - Production Deployment

> **Domain**: https://marketnavigator.ir  
> **Server IP**: 89.42.199.54

---

## Prerequisites

- Docker & Docker Compose installed
- Domain DNS pointing to server IP
- SSH access to server

---

## Quick Start

```bash
# Clone and navigate to project
git clone <repository-url>
cd marketnavigator-v2

# Setup SSL certificates (first time only)
./scripts/setup-ssl.sh

# Start all services
docker compose -f docker-compose.prod.yml up -d --build
```

---

## SSL Certificate Setup

### Option 1: Let's Encrypt (Recommended)

```bash
# Create required directories
mkdir -p nginx/ssl nginx/certbot

# Install certbot on server
sudo apt install certbot

# Obtain certificate (standalone mode - stop nginx first if running)
sudo certbot certonly --standalone -d marketnavigator.ir -d www.marketnavigator.ir

# Copy certificates to nginx/ssl
sudo cp /etc/letsencrypt/live/marketnavigator.ir/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/marketnavigator.ir/privkey.pem nginx/ssl/

# Set permissions
sudo chmod 644 nginx/ssl/*.pem
```

### Option 2: Self-Signed (Development/Testing)

```bash
mkdir -p nginx/ssl

# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=marketnavigator.ir"
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Worker Tokens (change these in production)
WORKER_TOKEN_CRUNCHBASE=your-secure-token-1
WORKER_TOKEN_TRACXN=your-secure-token-2
WORKER_TOKEN_SOCIAL=your-secure-token-3
WORKER_TOKEN_LINKEDIN=your-secure-token-4

# AI API Keys
OPENAI_API_KEY=your-openai-key
```

---

## Commands

### Start Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d --build

# Start specific service
docker compose -f docker-compose.prod.yml up -d backend
```

### Stop Services

```bash
# Stop all services
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (WARNING: deletes data)
docker compose -f docker-compose.prod.yml down -v
```

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
```

### Restart Services

```bash
# Restart all
docker compose -f docker-compose.prod.yml restart

# Restart specific service
docker compose -f docker-compose.prod.yml restart nginx
```

### Rebuild After Code Changes

```bash
docker compose -f docker-compose.prod.yml up -d --build backend frontend
```

---

## Service Ports

| Service      | Internal Port | External Access         |
|--------------|---------------|-------------------------|
| nginx        | 80, 443       | https://marketnavigator.ir |
| frontend     | 3000          | via nginx               |
| backend      | 8000          | via nginx `/api/`       |
| orchestrator | 8010          | via nginx `/ws/worker`  |
| redis        | 6379          | internal only           |
| minio        | 9000, 9001    | internal only           |
| flower       | 5555          | http://IP:5555          |

---

## SSL Certificate Renewal

Let's Encrypt certificates expire every 90 days. Set up auto-renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab (runs twice daily)
echo "0 0,12 * * * root certbot renew --quiet && cp /etc/letsencrypt/live/marketnavigator.ir/*.pem /path/to/nginx/ssl/ && docker compose -f docker-compose.prod.yml restart nginx" | sudo tee /etc/cron.d/certbot-renew
```

---

## Troubleshooting

### Check container status
```bash
docker compose -f docker-compose.prod.yml ps
```

### Check nginx configuration
```bash
docker exec mn2-nginx nginx -t
```

### Check SSL certificate
```bash
openssl x509 -in nginx/ssl/fullchain.pem -text -noout | grep -A2 "Validity"
```

### Reset everything
```bash
docker compose -f docker-compose.prod.yml down -v
docker system prune -af
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Directory Structure

```
marketnavigator-v2/
├── docker-compose.prod.yml    # Production compose file
├── nginx/
│   ├── nginx.conf             # Nginx configuration
│   ├── ssl/                   # SSL certificates
│   │   ├── fullchain.pem
│   │   └── privkey.pem
│   └── certbot/               # Let's Encrypt challenges
├── backend/
├── frontend/
└── orchestrator/
```
