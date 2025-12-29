# MarketNavigator v2

Modern market research and startup analysis platform.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Development Setup

1. Copy environment variables:
```bash
cp .env.example .env
```

2. Start all services:
```bash
docker-compose up -d
```

3. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

## Project Structure

```
marketnavigator-v2/
├── frontend/          # Next.js 14 (TypeScript)
├── backend/           # Django 5.0 (Python)
├── docker-compose.yml # Local development
└── .env               # Environment variables
```

## Features

- 4 Report Panels: Crunchbase, Tracxn, Social, Pitch Deck
- Interactive HTML Reports
- AI Chat Assistant
- Role-based Permissions
- Shareable Report Links
