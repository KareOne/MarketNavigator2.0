#!/bin/bash

# Script to run Tracxn API

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Setting up..."
    ./setup_env.sh
fi

echo "🚀 Starting Tracxn API..."
source venv/bin/activate

# Set environment variables if needed
export PYTHONWARNINGS="ignore::FutureWarning"
export PANDAS_FUTURE_NO_SILENT_DOWNCASTING="True"

# Status callbacks go to worker_agent which relays via WebSocket
# When running locally via script, agent typically runs on localhost:9098 (per docker-compose.remote.yml port)
# Adjust if necessary, but 9098 is the standard port for Tracxn agent status proxy
export STATUS_CALLBACK_URL="http://127.0.0.1:9098"

# Run the API
python api.py
