#!/bin/bash
# Crunchbase Remote Worker Setup Script
# Run this script to prepare and start the remote Crunchbase worker

set -e

echo "🚀 Crunchbase Remote Worker Setup"
echo "=================================="

# Check if worker_agent exists
if [ ! -d "worker_agent" ]; then
    echo "❌ Error: worker_agent folder not found!"
    echo ""
    echo "Please copy the worker_agent folder from the main project:"
    echo "  cp -r /path/to/marketnavigator-v2/worker_agent ./worker_agent"
    echo ""
    exit 1
fi

# Check if .env.remote exists
if [ ! -f ".env.remote" ]; then
    echo "📝 Creating .env.remote from template..."
    cp .env.remote.example .env.remote
    echo ""
    echo "⚠️  Please edit .env.remote and set your WORKER_TOKEN"
    echo "   Then run this script again."
    echo ""
    echo "   nano .env.remote"
    echo ""
    exit 1
fi

# Check if WORKER_TOKEN is set
if grep -q "your-crunchbase-worker-token" .env.remote; then
    echo "❌ Error: WORKER_TOKEN not configured!"
    echo ""
    echo "Please edit .env.remote and set your WORKER_TOKEN"
    echo "Get the token from the main server admin."
    echo ""
    exit 1
fi

echo "✅ Configuration looks good!"
echo ""

# Build and start
echo "🔨 Building and starting services..."
docker-compose -f docker-compose.remote.yml --env-file .env.remote up -d --build

echo ""
echo "✅ Services started!"
echo ""
echo "📊 Check status:"
echo "   docker-compose -f docker-compose.remote.yml logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose -f docker-compose.remote.yml down"
