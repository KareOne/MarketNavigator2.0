#!/bin/bash

# Script to run Tracxn Worker Agent (Local Development)

echo "🚀 Starting Tracxn Worker Agent (Local)..."

# Ensure we are in the script directory
cd "$(dirname "$0")"

# Activate venv
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup_env.sh first."
    exit 1
fi
source venv/bin/activate

# Go into worker_agent directory where agent.py resides
cd worker_agent

# Configuration for Local Development
export ORCHESTRATOR_URL="ws://localhost:8010/ws/worker"
export WORKER_TOKEN="dev-tracxn-token"  # Default dev token
export API_TYPE="tracxn"
export WORKER_NAME="tracxn-local-script"
export LOCAL_API_URL="http://127.0.0.1:8008"
export STATUS_PORT=9098  # Matches Tracxn config
export HEARTBEAT_INTERVAL=10
export RECONNECT_DELAY=5
export LOG_LEVEL="INFO"

echo "🔌 Connecting to Orchestrator: $ORCHESTRATOR_URL"
echo "📡 Local API: $LOCAL_API_URL"
echo "📶 Status Port: $STATUS_PORT"

# Run the agent
python agent.py
