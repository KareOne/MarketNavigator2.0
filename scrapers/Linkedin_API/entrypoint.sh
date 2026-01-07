#!/usr/bin/env bash
set -e

echo "🚀 Starting LinkedIn Scraper Microservice..."

# Check if database is disabled
DISABLE_DATABASE="${DISABLE_DATABASE:-false}"
if [[ "${DISABLE_DATABASE,,}" == "true" ]]; then
  echo "⚠️  Database disabled - skipping migrations"
else
  echo "🗄️  Running database migrations..."
  # Wait for MySQL to be ready
  until python -c "from config.config import get_db_connection; get_db_connection().close()"; do
    echo "⏳ Waiting for MySQL to be ready..."
    sleep 2
  done

  # Run database initialization and migrations
  python database/init_database.py || echo "⚠️  Database init warning (may already exist)"
  python database/migrate_database.py || echo "⚠️  Migration warning (may already be up to date)"
  echo "✅ Database migrations completed"
fi

# Default to False if not set
FLASK_DEBUG="${FLASK_DEBUG:-False}"

# Compare case-insensitively
if [[ "${FLASK_DEBUG,,}" == "true" ]]; then
  echo "Starting in DEV mode: python run.py"
  exec python run.py
else
  echo "Starting in PROD mode: gunicorn (sync worker)"
  # Using default sync worker to avoid eventlet+trio incompatibility breaking httpx/telegram
  exec gunicorn -c gunicorn.conf.py config.config:app
fi
