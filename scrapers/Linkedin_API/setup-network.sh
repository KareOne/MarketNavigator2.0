#!/bin/bash
# Microservices Network Setup Script
# Run this once before starting any microservices

set -e

echo "🚀 Setting up microservices infrastructure..."

# Create the shared network if it doesn't exist
if ! docker network inspect microservices-network >/dev/null 2>&1; then
    echo "📡 Creating microservices-network..."
    docker network create microservices-network
    echo "✅ Network created successfully"
else
    echo "✅ Network microservices-network already exists"
fi

echo ""
echo "🎉 Microservices infrastructure ready!"
echo ""
echo "Next steps:"
echo "  1. Start this service: docker-compose up -d"
echo "  2. Check health: curl http://localhost:5001/health"
echo "  3. View logs: docker-compose logs -f app"
echo ""
