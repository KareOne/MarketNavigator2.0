#!/bin/bash
# Service Management Script for LinkedIn Bot Microservice

set -e

COMPOSE_FILE="docker-compose.yml"
COMPOSE_PROD="docker-compose.prod.yml"

show_help() {
    cat << EOF
LinkedIn Bot Microservice Management Script

Usage: ./manage.sh [COMMAND]

Commands:
    start           Start services in development mode
    start-prod      Start services in production mode
    stop            Stop all services
    restart         Restart services
    rebuild         Rebuild and restart services
    logs            Follow service logs
    health          Check service health
    status          Show service status
    exec            Execute command in app container
    db-shell        Open MySQL shell
    db-init         Initialize database
    db-migrate      Run database migrations
    network-setup   Create microservices network
    cleanup         Remove all containers and volumes (⚠️  destructive)

Examples:
    ./manage.sh start
    ./manage.sh logs
    ./manage.sh exec python database/migrate_database.py
    ./manage.sh health
EOF
}

ensure_network() {
    if ! docker network inspect microservices-network >/dev/null 2>&1; then
        echo "📡 Creating microservices-network..."
        docker network create microservices-network
    fi
}

case "${1:-}" in
    start)
        ensure_network
        echo "🚀 Starting services (development mode)..."
        docker-compose up -d
        echo "✅ Services started"
        ;;
    
    start-prod)
        ensure_network
        echo "🚀 Starting services (production mode)..."
        docker-compose -f $COMPOSE_FILE -f $COMPOSE_PROD up -d
        echo "✅ Services started in production mode"
        ;;
    
    stop)
        echo "🛑 Stopping services..."
        docker-compose down
        echo "✅ Services stopped"
        ;;
    
    restart)
        echo "🔄 Restarting services..."
        docker-compose restart
        echo "✅ Services restarted"
        ;;
    
    rebuild)
        ensure_network
        echo "🔨 Rebuilding and restarting services..."
        docker-compose up -d --build
        echo "✅ Services rebuilt and restarted"
        ;;
    
    logs)
        docker-compose logs -f app
        ;;
    
    health)
        echo "🏥 Checking service health..."
        curl -s http://localhost:5001/health | python3 -m json.tool || echo "❌ Health check failed"
        ;;
    
    status)
        echo "📊 Service Status:"
        docker-compose ps
        echo ""
        echo "🌐 Networks:"
        docker network inspect microservices-network --format '{{range .Containers}}  - {{.Name}}{{"\n"}}{{end}}' 2>/dev/null || echo "  Network not found"
        ;;
    
    exec)
        shift
        docker exec -it linkedin-api "$@"
        ;;
    
    db-shell)
        docker exec -it linkedin-mysql mysql -u root -proot_pass_123 linkdeen_bot
        ;;
    
    db-init)
        echo "ℹ️  Note: Database auto-migrates on container start"
        echo "🗄️  Manually initializing database..."
        docker exec linkedin-api python database/init_database.py
        echo "✅ Database initialized"
        ;;
    
    db-migrate)
        echo "ℹ️  Note: Database auto-migrates on container start"
        echo "🔄 Manually running database migrations..."
        docker exec linkedin-api python database/migrate_database.py
        echo "✅ Migrations completed"
        ;;
    
    network-setup)
        ensure_network
        echo "✅ Microservices network ready"
        ;;
    
    cleanup)
        echo "⚠️  WARNING: This will remove all containers and volumes!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            docker-compose down -v
            echo "✅ Cleanup completed"
        else
            echo "❌ Cleanup cancelled"
        fi
        ;;
    
    help|--help|-h|"")
        show_help
        ;;
    
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
