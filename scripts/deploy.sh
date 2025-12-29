#!/bin/bash
# MarketNavigator v2 - Production Deployment Script
# Run this script on your production server to deploy the application

set -e

echo "================================================"
echo "MarketNavigator v2 - Production Deployment"
echo "================================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Step 1: Pull latest code (if using git)
echo ""
echo "[Step 1] Checking for code updates..."
if [ -d ".git" ]; then
    git pull origin main 2>/dev/null || echo "Git pull skipped (not on main or no remote)"
fi

# Step 2: Copy environment file if not exists
echo ""
echo "[Step 2] Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.production template..."
    cp .env.production .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and set:"
    echo "   - SECRET_KEY (generate a strong random key)"
    echo "   - Any API keys that need updating"
    echo ""
    read -p "Press Enter after editing .env to continue..."
fi

# Step 3: Build and start containers
echo ""
echo "[Step 3] Building and starting containers..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Step 4: Wait for services to be ready
echo ""
echo "[Step 4] Waiting for services to start..."
sleep 10

# Step 5: Run database migrations
echo ""
echo "[Step 5] Running database migrations..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python manage.py migrate --noinput

# Step 6: Collect static files
echo ""
echo "[Step 6] Collecting static files..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python manage.py collectstatic --noinput

# Step 7: Check service health
echo ""
echo "[Step 7] Checking service health..."
echo ""

# Check backend
if docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo "✅ Backend: Healthy"
else
    echo "⚠️  Backend: May still be starting..."
fi

# Check frontend
if docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T frontend wget -q --spider http://localhost:3000 2>/dev/null; then
    echo "✅ Frontend: Healthy"
else
    echo "⚠️  Frontend: May still be starting..."
fi

# Check Redis
if docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: Healthy"
else
    echo "⚠️  Redis: May still be starting..."
fi

echo ""
echo "================================================"
echo "Deployment Complete!"
echo ""
echo "Your application should be available at:"
echo "  https://market.kareonecompany.com"
echo ""
echo "If this is your first deployment, run SSL setup:"
echo "  sudo ./scripts/setup-ssl.sh"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
echo ""
echo "To stop all services:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.prod.yml down"
echo "================================================"
