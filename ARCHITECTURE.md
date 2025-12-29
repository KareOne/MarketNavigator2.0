# MarketNavigator v2 - Technical Architecture Improvements

This document summarizes the key technical architecture improvements in v2 compared to the MVP version.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Next.js 14    │────▶│   Django 5.0    │────▶│   PostgreSQL    │
│   Frontend      │     │   + Daphne      │     │   (Remote)      │
└─────────────────┘     └──────┬───────────┘     └─────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│    Redis     │     │    MinIO     │     │  Celery Workers  │
│ (Cache/Queue)│     │ (S3 Storage) │     │  + Flower        │
└──────────────┘     └──────────────┘     └──────────────────┘
                                                   │
                     ┌─────────────────────────────┼───────────────┐
                     ▼                             ▼               ▼
              ┌─────────────┐             ┌─────────────┐   ┌──────────┐
              │ Crunchbase  │             │   Tracxn    │   │   AI     │
              │ Scraper API │             │ Scraper API │   │ Services │
              └─────────────┘             └─────────────┘   └──────────┘
```

---

## Key Improvements

### 1. Microservices Architecture

| MVP | v2 |
|-----|-----|
| Monolithic Django app | Microservices with separate containers |
| Scrapers embedded in backend | Dedicated scraper APIs (Crunchbase, Tracxn) |
| Tight coupling | Loosely coupled services via HTTP/REST |

### 2. Async Task Processing

| MVP | v2 |
|-----|-----|
| Synchronous report generation | Celery workers with Redis broker |
| UI freezes during long operations | Background task queues (celery, default, reports) |
| No visibility into progress | Real-time progress tracking via WebSocket |
| No task monitoring | Flower dashboard for worker monitoring |

### 3. Real-Time Communication

| MVP | v2 |
|-----|-----|
| HTTP polling for updates | Django Channels + Daphne (ASGI) |
| No live progress updates | WebSocket-based real-time updates |
| Static UI during processing | Live progress steps with granular details |

### 4. Progress Tracking System

- **ReportProgressTracker** service with step-by-step tracking
- Weighted progress calculation across multiple steps
- Historical timing data for future predictions
- Real-time WebSocket broadcasts to all connected clients

### 5. Object Storage

| MVP | v2 |
|-----|-----|
| Local filesystem storage | MinIO (S3-compatible) object storage |
| No scalability | Horizontally scalable storage layer |
| Manual file management | Automatic bucket initialization |

### 6. Frontend Architecture

| MVP | v2 |
|-----|-----|
| Basic React components | Next.js 14 with App Router |
| No real mobile support | Responsive mobile panels (fullscreen mode) |
| Basic state management | Context-based auth with useAuth hook |
| Simple layouts | Collapsible panels with smooth transitions |

### 7. AI Integration

| MVP | v2 |
|-----|-----|
| Single AI provider | Multi-provider support (OpenAI, Liara, Metis) |
| Basic completions | Structured AI functions with confidence scoring |
| No auto-fill | AI auto-fill for form fields via WebSocket |
| Fixed prompts | Mode-based system prompts (e.g., Editing Mode) |

### 8. Database & Caching

| MVP | v2 |
|-----|-----|
| Local SQLite/PostgreSQL | Remote PostgreSQL (Liara hosted) |
| No caching layer | Redis with LRU eviction policy |
| No session persistence | Redis-backed sessions and cache |

### 9. Containerization

| MVP | v2 |
|-----|-----|
| Manual setup required | Full Docker Compose orchestration |
| Environment-dependent | Reproducible multi-container deployment |
| No health checks | Health checks for all critical services |
| Manual dependencies | Automatic service dependency management |

---

## Service Inventory

| Service | Port | Purpose |
|---------|------|---------|
| frontend | 3000 | Next.js UI |
| backend | 8000 | Django API + WebSocket |
| redis | 6379 | Cache + Message Broker |
| minio | 9000/9001 | Object Storage |
| crunchbase_api | 8003 | Crunchbase Scraper |
| tracxn_api | 8008 | Tracxn Scraper |
| celery-worker | - | Background Tasks |
| celery-beat | - | Scheduled Tasks |
| flower | 5555 | Task Monitoring |

---

## Summary

v2 represents a significant evolution from the MVP, introducing:
- **Scalability** through microservices and async processing
- **Reliability** with health checks and managed dependencies
- **Real-time UX** via WebSocket-based progress tracking
- **Flexibility** with multi-provider AI and S3-compatible storage
- **Mobile support** with responsive fullscreen panel modes
