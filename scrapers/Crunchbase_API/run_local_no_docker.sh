#!/bin/bash

# Configuration
VENV_DIR="venv_local_runner"
API_PORT=8003
ORCHESTRATOR_URL="ws://localhost:8010/ws/worker"
WORKER_TOKEN="dev-crunchbase-token"
LOG_LEVEL="INFO"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Crunchbase API & Worker Agent (Local Mode)${NC}"

# 1. Setup Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}📦 Creating virtual environment in $VENV_DIR...${NC}"
    python3 -m venv $VENV_DIR
else
    echo -e "${GREEN}✅ Virtual environment exists.${NC}"
fi

# Activate venv
source $VENV_DIR/bin/activate

# 2. Install Dependencies
echo -e "${BLUE}⬇️  Installing/Updating dependencies...${NC}"
pip install -r requirements.txt
pip install -r worker_agent/requirements.txt

# Install Playwright browsers manually if needed
if [ ! -d "$VENV_DIR/lib/python3.*/site-packages/playwright/driver/package/.local-browsers" ]; then
   echo -e "${BLUE}🎭 Installing Playwright browsers...${NC}"
   playwright install chromium
fi

# 3. Load Environment Variables
if [ -f .env ]; then
    echo -e "${GREEN}📄 Loading .env file...${NC}"
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${RED}⚠️  No .env file found! Using defaults.${NC}"
fi

# Set additional env vars for local execution
export STATUS_CALLBACK_URL="http://localhost:9099"
export PYTHONWARNINGS="ignore::FutureWarning"
export PANDAS_FUTURE_NO_SILENT_DOWNCASTING="True"
export ORCHESTRATOR_URL=$ORCHESTRATOR_URL
export WORKER_TOKEN=$WORKER_TOKEN
export API_TYPE="crunchbase"
export WORKER_NAME="crunchbase-local-script"
export LOCAL_API_URL="http://localhost:$API_PORT"
export HEARTBEAT_INTERVAL=10
export RECONNECT_DELAY=5
export LOG_LEVEL=$LOG_LEVEL
export HEADLESS=False  # Show Chrome window

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${RED}🛑 Shutting down services...${NC}"
    kill $(jobs -p) 2>/dev/null
    deactivate
    echo -e "${GREEN}✅ Sandbox cleaned up.${NC}"
}
trap cleanup EXIT

# 4. Start Crunchbase API
echo -e "${BLUE}🔌 Starting Crunchbase API on port $API_PORT...${NC}"
# Use > to truncate/create new log file
> api.log
python api_handler.py > api.log 2>&1 &
API_PID=$!

# Stream logs to terminal in background
tail -f api.log &
TAIL_PID=$!

# Wait for API to be ready
echo -e "${BLUE}⏳ Waiting for API to respond...${NC}"
attempts=0
max_attempts=60
while ! curl -s "http://localhost:$API_PORT/health" > /dev/null; do
    sleep 1
    attempts=$((attempts+1))
    if [ $attempts -ge $max_attempts ]; then
        echo -e "${RED}❌ API failed to start in time.${NC}"
        # Logs are already visible via tail
        kill $TAIL_PID
        exit 1
    fi
done
echo -e "${GREEN}✅ API is UP!${NC}"

# Stop tailing API logs so we don't spam indefinitely/mix with agent logs too much?
# Actually user wants to see them. Let's keep tailing. 
# But maybe we should label them? Simple tail is fine.

# 5. Start Worker Agent
echo -e "${BLUE}🤖 Starting Worker Agent...${NC}"
python worker_agent/agent.py > agent.log 2>&1 &
AGENT_PID=$!

# Keep script running
echo -e "${GREEN}🚀 Services running. (Window should appear soon)${NC}"
wait $API_PID $AGENT_PID
