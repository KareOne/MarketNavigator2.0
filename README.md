# MarketNavigator v2

Modern market research and startup analysis platform with AI-powered insights.

![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![Frontend](https://img.shields.io/badge/Frontend-Next.js%2014-black)
![Backend](https://img.shields.io/badge/Backend-Django%205.0-green)
![Database](https://img.shields.io/badge/Database-PostgreSQL-blue)

## Features

- **4 Report Panels**: Crunchbase, Tracxn, Social, Pitch Deck
- **Real-time Progress**: WebSocket-based live updates
- **AI Chat Assistant**: Multi-provider support (Liara, OpenAI, Metis)
- **Interactive HTML Reports**: Beautiful, exportable reports
- **Role-based Permissions**: Organization-level access control
- **Shareable Report Links**: Public sharing with expiration

---

## Project Structure

```
marketnavigator-v2/
├── frontend/              # Next.js 14 (TypeScript)
├── backend/               # Django 5.0 (Python)
├── scrapers/
│   ├── Crunchbase_API/    # Crunchbase scraper service
│   └── Tracxn_API/        # Tracxn scraper service
├── nginx/                 # Production reverse proxy
├── scripts/               # Deployment scripts
├── docker-compose.yml     # Local development
├── docker-compose.prod.yml # Production overrides
├── .env                   # Local environment
└── .env.production        # Production environment template
```

---

## Local Development

### Prerequisites

- Docker & Docker Compose
- Git

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/KareOne/MarketNavigator2.0.git
cd MarketNavigator2.0

# 2. Start all services
docker-compose up -d

# 3. Wait for services to start (first time may take a few minutes)
docker-compose logs -f
```

### Access Points (Local)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/docs |
| Flower (Celery) | http://localhost:5555 |
| MinIO Console | http://localhost:9001 |

### Common Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Rebuild after code changes
docker-compose up -d --build

# Run database migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Access Django shell
docker-compose exec backend python manage.py shell
```

---

## Production Deployment

Deploy to your own server (e.g., Liara VPS, DigitalOcean, AWS).

### Prerequisites

- Linux server with Docker installed
- Domain pointed to server IP
- SSH access

### Step 1: Install Docker (if not installed)

```bash
# SSH into your server
ssh root@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt-get install -y docker-compose-plugin
```

### Step 2: Clone & Configure

```bash
# Clone repository
git clone https://github.com/KareOne/MarketNavigator2.0.git /opt/marketnavigator
cd /opt/marketnavigator

# Create production environment
cp .env.production .env

# Edit environment variables
nano .env
```

**Important**: Generate a secure `SECRET_KEY`:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 3: Deploy

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run deployment
./scripts/deploy.sh
```

### Step 4: Setup SSL (HTTPS)

```bash
# Run SSL setup script (requires domain pointed to server)
sudo ./scripts/setup-ssl.sh
```

### Step 5: Verify Deployment

| Service | URL |
|---------|-----|
| Frontend | https://your-domain.com |
| Backend API | https://your-domain.com/api/ |
| Health Check | https://your-domain.com/api/health/ |

---

## Environment Variables

### Key Variables

| Variable | Local | Production |
|----------|-------|------------|
| `DEBUG` | `1` | `0` |
| `SECRET_KEY` | dev-key | Strong random key |
| `DB_HOST` | table-mountain.liara.cloud | marketnavigator-v2 |
| `DB_PORT` | 32965 | 5432 |
| `ALLOWED_HOSTS` | localhost,127.0.0.1 | your-domain.com |
| `CORS_ALLOWED_ORIGINS` | http://localhost:3000 | https://your-domain.com |
| `NEXT_PUBLIC_API_URL` | http://localhost:8000 | https://your-domain.com |
| `NEXT_PUBLIC_WS_URL` | ws://localhost:8000 | wss://your-domain.com |

---

## Architecture

```
                         ┌─────────────────────┐
                         │   Nginx (SSL/Proxy) │
                         └──────────┬──────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    Frontend     │       │    Backend      │       │    MinIO S3     │
│   (Next.js)     │       │  (Django/Daphne)│       │  (File Storage) │
│   Port 3000     │       │   Port 8000     │       │   Port 9000     │
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     Redis       │       │  Celery Workers │       │   PostgreSQL    │
│  (Cache/Queue)  │       │ (Background Jobs)│      │   (Database)    │
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
           ┌─────────────────┐           ┌─────────────────┐
           │  Crunchbase API │           │   Tracxn API    │
           │  (Port 8003)    │           │   (Port 8008)   │
           └─────────────────┘           └─────────────────┘
```

---

## Services Overview

| Service | Port | Description |
|---------|------|-------------|
| frontend | 3000 | Next.js 14 React application |
| backend | 8000 | Django REST API + WebSocket |
| redis | 6379 | Cache & Celery message broker |
| minio | 9000/9001 | S3-compatible file storage |
| crunchbase_api | 8003 | Crunchbase scraper microservice |
| tracxn_api | 8008 | Tracxn scraper microservice |
| celery-worker | - | Background task processing |
| celery-beat | - | Scheduled tasks |
| flower | 5555 | Celery monitoring dashboard |
| nginx | 80/443 | Reverse proxy (production only) |

---

## Troubleshooting

### Services not starting
```bash
# Check service health
docker-compose ps

# Check logs for errors
docker-compose logs backend
docker-compose logs frontend
```

### Database connection issues
```bash
# Verify database is accessible
docker-compose exec backend python manage.py dbshell
```

### Frontend not connecting to backend
- Ensure `NEXT_PUBLIC_API_URL` matches your backend URL
- Check CORS settings in backend environment

### SSL certificate issues
```bash
# Renew certificate manually
certbot renew
cp /etc/letsencrypt/live/your-domain.com/*.pem /opt/marketnavigator/nginx/ssl/
docker-compose restart nginx
```

---

## License

Proprietary - KareOne Company
