# Remote Worker Deployment

This directory contains configuration for deploying remote API workers that connect to the main MarketNavigator orchestrator.

## Prerequisites

- Docker and Docker Compose installed
- Network access to the main server (orchestrator port 8010)
- Worker authentication token from the admin

## Quick Start

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Configure your environment:**
   Edit `.env` and set:
   - `ORCHESTRATOR_URL` - WebSocket URL of the main server
   - `WORKER_TOKEN` - Your authentication token
   - `API_TYPE` - Type of API (crunchbase, tracxn, or social)

3. **Start the worker:**
   ```bash
   docker-compose up -d
   ```

4. **Check logs:**
   ```bash
   docker-compose logs -f worker_agent
   ```

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ORCHESTRATOR_URL` | Main server WebSocket URL | `ws://your-server-ip:8010/ws/worker` |
| `WORKER_TOKEN` | Authentication token | `your-secure-token` |
| `API_TYPE` | Type of API this worker runs | `crunchbase`, `tracxn`, `social` |
| `WORKER_NAME` | Optional worker name for identification | `cb-worker-1` |
| `LOCAL_API_URL` | URL of the local scraper API | `http://crunchbase_api:8003` |

## Architecture

```
┌─────────────────────────────────────────────────┐
│            Remote Server                         │
│  ┌─────────────┐      ┌─────────────────────┐   │
│  │ Worker Agent│──────│ Crunchbase API      │   │
│  │  (connects  │      │ (existing scraper)  │   │
│  │   to main)  │      │                     │   │
│  └──────┬──────┘      └─────────────────────┘   │
└─────────┼───────────────────────────────────────┘
          │
          │ WebSocket
          │ (wss://your-main-server:8010/ws/worker)
          │
┌─────────▼───────────────────────────────────────┐
│            Main Server                           │
│  ┌─────────────┐                                │
│  │ Orchestrator│                                │
│  └─────────────┘                                │
└─────────────────────────────────────────────────┘
```

## Scaling

To run multiple workers on the same server:

```bash
docker-compose up -d --scale worker_agent=3
```

Or create separate compose files for each worker type.

## Troubleshooting

### Worker not connecting
- Check that the orchestrator URL is correct
- Verify the token is in the orchestrator's allowed tokens
- Ensure port 8010 is accessible from the remote server

### Tasks not being assigned
- Check worker logs: `docker-compose logs worker_agent`
- Verify the API type matches what the backend is requesting
- Check orchestrator logs on the main server

### API errors
- Ensure the local API (Crunchbase/Tracxn) is running
- Check LOCAL_API_URL is correct
- Review API container logs
