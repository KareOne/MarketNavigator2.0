# Crunchbase API - Remote Deployment

This folder can be deployed to a remote server to run the Crunchbase API scraper as a distributed worker connected to the main MarketNavigator orchestrator.

## Quick Start

### 1. Copy the worker agent
First, copy the `worker_agent` folder from the main project into this folder:

```bash
cp -r /path/to/marketnavigator-v2/worker_agent ./worker_agent
```

### 2. Configure environment
```bash
cp .env.remote.example .env.remote
nano .env.remote
```

Set your worker token (get from admin):
```
WORKER_TOKEN=your-secure-token
```

### 3. Start the services
```bash
docker-compose -f docker-compose.remote.yml --env-file .env.remote up -d --build
```

### 4. Check status
```bash
# View logs
docker-compose -f docker-compose.remote.yml logs -f

# Check if worker is connected
docker-compose -f docker-compose.remote.yml logs worker_agent
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    This Remote Server                        │
│  ┌─────────────────┐      ┌─────────────────────────────┐   │
│  │  Worker Agent   │◄────►│  Crunchbase API (port 8003) │   │
│  │  (connects to   │      │  (scraping logic)            │   │
│  │   main server)  │      └─────────────────────────────┘   │
│  └────────┬────────┘                                        │
└───────────┼─────────────────────────────────────────────────┘
            │
            │ WebSocket (ws://89.42.199.54:8010/ws/worker)
            │
┌───────────▼─────────────────────────────────────────────────┐
│                   Main Server (89.42.199.54)                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │
│  │ Orchestrator│◄───►│   Backend   │◄───►│  Frontend   │    │
│  │  (8010)     │     │   (8000)    │     │  (3000)     │    │
│  └─────────────┘     └─────────────┘     └─────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ORCHESTRATOR_URL` | Main server WebSocket URL | `ws://89.42.199.54:8010/ws/worker` |
| `WORKER_TOKEN` | Authentication token | (required) |
| `WORKER_NAME` | Display name in admin | `crunchbase-remote-1` |

## Troubleshooting

### Worker not connecting
```bash
# Check worker logs
docker-compose -f docker-compose.remote.yml logs worker_agent

# Common issues:
# - Wrong WORKER_TOKEN (must match main server's WORKER_TOKENS_CRUNCHBASE)
# - Main server not reachable (check firewall for port 8010)
# - Orchestrator not running on main server
```

### API not responding
```bash
# Check API logs
docker-compose -f docker-compose.remote.yml logs crunchbase_api

# Restart services
docker-compose -f docker-compose.remote.yml restart
```

## Scaling

To run multiple workers on different servers, deploy this folder to each server with a unique `WORKER_NAME`:

```bash
# Server 1
WORKER_NAME=cb-worker-1

# Server 2  
WORKER_NAME=cb-worker-2
```

The orchestrator will distribute tasks across all connected workers.
