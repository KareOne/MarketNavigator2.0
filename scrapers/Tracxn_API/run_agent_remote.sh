#!/bin/bash

# Script to run Tracxn Worker Agent (Remote Deployment)

echo "🚀 Starting Tracxn Worker Agent (Remote System)..."

# Ensure we are in the script directory
cd "$(dirname "$0")"

# Check for venv and create/install if missing
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Setting up..."
    ./setup_env.sh
fi

source venv/bin/activate

# Go into worker_agent directory where agent.py resides
cd worker_agent

# Configuration for Remote Deployment
# Default to the server IP provided in previous contexts
export ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-ws://89.42.199.54:8010/ws/worker}"
# Allow token override via environment provided at runtime
export WORKER_TOKEN="${WORKER_TOKEN:-dev-tracxn-token}"

export API_TYPE="tracxn"
export WORKER_NAME="${WORKER_NAME:-tracxn-remote-script}"
export LOCAL_API_URL="http://127.0.0.1:8008"
export STATUS_PORT=9098  # Matches Tracxn config
export HEARTBEAT_INTERVAL=10
export RECONNECT_DELAY=5
export LOG_LEVEL="INFO"

echo "🔌 Connecting to Orchestrator: $ORCHESTRATOR_URL"
echo "📡 Local API: $LOCAL_API_URL"
echo "📶 Status Port: $STATUS_PORT"
echo "🔑 Worker Name: $WORKER_NAME"

# Run the agent
python agent.py
