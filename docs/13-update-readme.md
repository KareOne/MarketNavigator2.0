# README Update Guide - MarketNavigator v2

## Purpose
Guidelines for maintaining a comprehensive README that enables new developers to set up and run the project independently, without requiring external help or tribal knowledge.

---

## Current README Assessment

### ✅ What's Good
- Clear project structure overview
- Technology stack badges
- Docker Compose usage documented
- Quick start section exists

### ⚠️ Needs Improvement
- Missing prerequisites section
- No troubleshooting guide
- Environment variables not fully documented
- Testing instructions missing
- Contribution guidelines absent

---

## Recommended README Structure

```markdown
# MarketNavigator v2

> Modern market research and startup analysis platform with AI-powered insights

![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![Frontend](https://img.shields.io/badge/Frontend-Next.js%2014-black)
![Backend](https://img.shields.io/badge/Backend-Django%205.0-green)
![Database](https://img.shields.io/badge/Database-PostgreSQL-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Documentation](#documentation)
- [Support](#support)

---

## ✨ Features

### Core Functionality
- **4 Report Panels**: Crunchbase, Tracxn, Social Media, Pitch Deck analysis
- **Real-time Progress**: WebSocket-based live updates during report generation
- **AI Chat Assistant**: Multi-provider support (OpenAI, Liara AI, Metis AI)
- **Interactive HTML Reports**: Beautiful, exportable reports with charts and insights
- **Role-based Permissions**: Organization-level access control
- **Shareable Report Links**: Public sharing with expiration and access controls

### Technical Features
- Microservices architecture with Docker Compose
- Async task processing with Celery
- S3-compatible object storage with MinIO
- Real-time monitoring with Flower
- Scalable data scraping services

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Next.js   │────▶│   Django     │────▶│ PostgreSQL  │
│  Frontend   │     │   Backend    │     │   Database  │
│   :3000     │     │    :8000     │     │   (Remote)  │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                    ┌───────┼───────┐
                    │       │       │
            ┌───────▼──┐  ┌─▼────┐  ┌──▼──────┐
            │  Celery  │  │Redis │  │  MinIO  │
            │  Worker  │  │:6379 │  │  :9000  │
            └──────────┘  └──────┘  └─────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
    ┌─────▼──────┐    ┌──────▼─────┐
    │ Crunchbase │    │   Tracxn   │
    │   Scraper  │    │  Scraper   │
    │   :8003    │    │   :8008    │
    └────────────┘    └────────────┘
```

**Services:**
- **Frontend**: Next.js 14 with TypeScript
- **Backend**: Django 5.0 REST Framework + WebSockets (Daphne)
- **Database**: PostgreSQL (managed on Liara Cloud)
- **Cache/Queue**: Redis
- **Task Queue**: Celery + Celery Beat
- **Storage**: MinIO (S3-compatible)
- **Monitoring**: Flower (Celery monitoring)
- **Scrapers**: Crunchbase & Tracxn API services

---

## 📦 Prerequisites

### Required Software

| Tool | Version | Download | Purpose |
|------|---------|----------|---------|
| **Docker** | 24.0+ | [Get Docker](https://docs.docker.com/get-docker/) | Container runtime |
| **Docker Compose** | 2.20+ | Included with Docker Desktop | Multi-container orchestration |
| **Git** | 2.30+ | [Download](https://git-scm.com/) | Version control |

### Optional Tools

| Tool | Purpose |
|------|---------|
| **Python 3.11+** | Running Django commands outside Docker |
| **Node.js 20+** | Running frontend outside Docker |
| **PostgreSQL Client** | Database access |

### System Requirements

- **OS**: macOS, Linux, or Windows with WSL2
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 10GB free space
- **Network**: Stable internet connection (for pulling images)

### Verify Installation

```bash
# Check Docker
docker --version
# Expected: Docker version 24.0.0 or higher

# Check Docker Compose
docker-compose --version
# Expected: Docker Compose version 2.20.0 or higher

# Check Docker is running
docker ps
# Should not error
```

---

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/MarketNavigator2.0.git
cd MarketNavigator2.0
```

### 2. Configure Environment

**Option A: If .env is tracked in repository (current setup)**
```bash
# Verify .env exists
cat .env

# Update any credentials if needed
nano .env
```

**Option B: If .env not tracked (recommended best practice)**
```bash
# Copy template
cp .env.example .env

# Fill in required values
nano .env

# Required variables:
# - SECRET_KEY (generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))")
# - DB_PASSWORD (get from team)
# - API keys (OpenAI, Liara, etc.)
```

### 3. Start Services

```bash
# Start all services in background
docker-compose up -d

# View logs (optional)
docker-compose logs -f
```

### 4. Run Initial Setup

```bash
# Run database migrations
docker-compose exec backend python manage.py migrate

# Create superuser (admin account)
docker-compose exec -it backend python manage.py createsuperuser
# Follow prompts to create admin user

# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput
```

### 5. Access Application

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | (Register new account) |
| **Backend Admin** | http://localhost:8000/admin | (Superuser created above) |
| **API Docs** | http://localhost:8000/api/docs | N/A |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin123 |
| **Flower** | http://localhost:5555 | admin / admin123 |

### 6. Test Setup

```bash
# Test backend API
curl http://localhost:8000/api/health/
# Expected: {"status":"healthy"}

# Test frontend
curl -I http://localhost:3000
# Expected: HTTP/1.1 200 OK

# Test Redis
docker-compose exec redis redis-cli ping
# Expected: PONG

# Test Celery workers
docker-compose exec celery-worker celery -A config inspect ping
# Expected: {"celery@...": "pong"}
```

**🎉 Success!** Your development environment is ready.

---

## ⚙️ Environment Configuration

### Required Environment Variables

#### Django Backend

| Variable | Example | Description |
|----------|---------|-------------|
| `DEBUG` | `1` | Enable debug mode (0 for production) |
| `SECRET_KEY` | `your-secret-key` | Django cryptographic key (50+ chars) |
| `DB_HOST` | `table-mountain.liara.cloud` | PostgreSQL hostname |
| `DB_PORT` | `32965` | PostgreSQL port |
| `DB_NAME` | `postgres` | Database name |
| `DB_USER` | `root` | Database user |
| `DB_PASSWORD` | `<password>` | Database password |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |

#### MinIO Storage

| Variable | Example | Description |
|----------|---------|-------------|
| `USE_S3` | `True` | Enable MinIO storage |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin123` | MinIO secret key |
| `AWS_STORAGE_BUCKET_NAME` | `marketnavigator-files` | Storage bucket name |
| `AWS_S3_ENDPOINT_URL` | `http://minio:9000` | MinIO endpoint |

#### AI Services (At least one required)

| Variable | Example | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `sk-...` | OpenAI API key |
| `LIARA_API_KEY` | `eyJ...` | Liara AI API key |
| `METIS_API_KEY` | `tpsg-...` | Metis AI API key |

#### Next.js Frontend

| Variable | Example | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | WebSocket URL |

**💡 Tip:** See `docs/07-env-example.md` for complete list and production values.

---

## 🔧 Development

### Common Development Tasks

#### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

#### Run Django Commands

```bash
# Django shell
docker-compose exec backend python manage.py shell

# Database migrations
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec -it backend python manage.py createsuperuser

# Database shell
docker-compose exec backend python manage.py dbshell
```

#### Frontend Development

```bash
# View Next.js logs
docker-compose logs -f frontend

# Restart frontend
docker-compose restart frontend

# Rebuild after dependency changes
docker-compose build frontend
docker-compose up -d frontend
```

#### Celery Management

```bash
# View Celery logs
docker-compose logs -f celery-worker

# Check active tasks
docker-compose exec celery-worker celery -A config inspect active

# Purge pending tasks
docker-compose exec celery-worker celery -A config purge
```

### Useful Development Scripts

See `docs/12-local-commands.md` for comprehensive command reference.

---

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
docker-compose exec backend python manage.py test

# Run specific app tests
docker-compose exec backend python manage.py test users

# Run with coverage
docker-compose exec backend coverage run manage.py test
docker-compose exec backend coverage report

# Run linting
docker-compose exec backend flake8 backend/
```

### Frontend Tests

```bash
# Run tests
docker-compose exec frontend npm test

# Run linting
docker-compose exec frontend npm run lint

# Type checking
docker-compose exec frontend npm run type-check
```

### Integration Tests

```bash
# Test API endpoints
curl http://localhost:8000/api/health/
curl http://localhost:8000/api/users/me

# Test WebSocket connection
# (Use browser DevTools or WebSocket client)
```

---

## 🚢 Deployment

### Production Deployment

See `docs/02-deployment-flow.md` for comprehensive production deployment guide.

**Quick production start:**

```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec backend python manage.py migrate

# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput
```

### Environment-Specific Configurations

| Environment | Compose Files | Purpose |
|-------------|--------------|---------|
| **Development** | `docker-compose.yml` | Local development with hot reload |
| **Production** | `docker-compose.yml` + `docker-compose.prod.yml` | Production with nginx, SSL |

---

## 🔍 Troubleshooting

### Common Issues

#### Services Won't Start

```bash
# Check if ports are in use
sudo lsof -i :3000  # Frontend
sudo lsof -i :8000  # Backend
sudo lsof -i :6379  # Redis

# Check Docker status
docker ps
docker-compose ps

# View error logs
docker-compose logs backend
```

#### Database Connection Failed

```bash
# Verify database credentials
docker-compose exec backend env | grep DB_

# Test connection
docker-compose exec backend python manage.py check --database default

# Check database logs (if local)
docker-compose logs postgres
```

#### Frontend Not Loading

```bash
# Check logs
docker-compose logs frontend

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend

# Verify environment variables
docker-compose exec frontend env | grep NEXT_PUBLIC
```

#### Celery Tasks Not Running

```bash
# Check worker status
docker-compose exec celery-worker celery -A config inspect ping

# Restart worker
docker-compose restart celery-worker

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Getting Help

1. **Check Documentation**: See `docs/` folder for detailed guides
2. **View Logs**: `docker-compose logs -f [service]`
3. **Ask Team**: Post in Slack #engineering channel
4. **Open Issue**: [GitHub Issues](https://github.com/your-org/MarketNavigator2.0/issues)

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [System Mapping](docs/01-system-mapping.md) | Service architecture and dependencies |
| [Deployment Flow](docs/02-deployment-flow.md) | Production deployment procedures |
| [Environment Variables](docs/03-env-locations.md) | Environment configuration guide |
| [Branch Protection](docs/04-protect-main-branch.md) | Git workflow and branch rules |
| [Pull Request Requirements](docs/05-require-prs-develop.md) | Code review process |
| [Branch Naming](docs/06-branch-naming.md) | Branch naming conventions |
| [Environment Examples](docs/07-env-example.md) | Environment variable templates |
| [GitIgnore Rules](docs/08-gitignore-env.md) | Secret management |
| [Docker Compose Env](docs/09-compose-env-file.md) | Docker environment loading |
| [Secure Production Env](docs/10-secure-prod-env.md) | Production secret storage |
| [Scan Secrets](docs/11-scan-secrets.md) | Detect leaked secrets |
| [Local Commands](docs/12-local-commands.md) | Development commands reference |
| [Restart & Logs](docs/14-restart-logs.md) | Container restart policies |

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Workflow

1. **Create Feature Branch**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow code style guidelines
   - Add tests for new features
   - Update documentation

3. **Test Locally**
   ```bash
   docker-compose exec backend python manage.py test
   docker-compose exec frontend npm run lint
   ```

4. **Create Pull Request**
   - Push branch: `git push origin feature/your-feature-name`
   - Open PR on GitHub targeting `develop` branch
   - Fill in PR template
   - Request review

5. **Code Review**
   - Address feedback
   - All CI checks must pass
   - Requires 1 approval

### Code Style

- **Python**: Follow PEP 8, use Black formatter
- **JavaScript/TypeScript**: Follow ESLint configuration
- **Commit Messages**: Use conventional commits (`feat:`, `fix:`, `docs:`)

### Branch Naming

- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Critical production fixes
- `docs/` - Documentation updates

See `docs/06-branch-naming.md` for complete guidelines.

---

## 📞 Support

### Team Contacts

- **Tech Lead**: tech-lead@company.com
- **DevOps**: devops@company.com
- **Security**: security@company.com

### Communication Channels

- **Slack**: #engineering (general), #devops (deployment)
- **GitHub Issues**: Bug reports and feature requests
- **Email**: dev-team@company.com

### Office Hours

- **Code Review**: Daily 2-4 PM
- **DevOps Support**: Mon/Wed/Fri 10 AM - 12 PM
- **Team Standup**: Daily 9:30 AM

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [Django REST Framework](https://www.django-rest-framework.org/)
- Frontend powered by [Next.js](https://nextjs.org/)
- Task queue by [Celery](https://docs.celeryproject.org/)
- Storage by [MinIO](https://min.io/)

---

**Last Updated:** 2025-12-31  
**Version:** 2.0.0  
**Maintainer:** Engineering Team

```

---

## README Maintenance Checklist

### When to Update README

- [ ] New service added to docker-compose.yml
- [ ] New environment variable required
- [ ] Port number changed
- [ ] New prerequisite software needed
- [ ] Deployment procedure changed
- [ ] New documentation file created
- [ ] Team structure changed (contacts)
- [ ] New common issue discovered

### Quarterly Review

- [ ] Test quick start instructions from scratch
- [ ] Verify all links work
- [ ] Update version numbers
- [ ] Check for outdated screenshots
- [ ] Validate all commands still work
- [ ] Review troubleshooting section
- [ ] Update technology stack badges

---

## Best Practices

### ✅ Do This

1. **Keep it DRY** - Link to detailed docs instead of duplicating
2. **Test instructions** - Verify setup works on fresh machine
3. **Use examples** - Show actual commands, not just descriptions
4. **Visual aids** - Add architecture diagrams and screenshots
5. **Version badges** - Show technology versions clearly
6. **TOC** - Add table of contents for long READMEs
7. **Update regularly** - Review after every major change

### ❌ Avoid This

1. **Outdated info** - Remove obsolete instructions
2. **Tribal knowledge** - Document everything, assume no prior knowledge
3. **Long walls of text** - Use sections, lists, and tables
4. **Missing troubleshooting** - Include common issues and solutions
5. **No examples** - Show actual commands and expected output
6. **Dead links** - Regularly check and update links
7. **Vague instructions** - Be specific and actionable

---

**Last Updated:** 2025-12-31  
**Maintainer:** Documentation Team  
**Review Schedule:** Quarterly + After major releases
