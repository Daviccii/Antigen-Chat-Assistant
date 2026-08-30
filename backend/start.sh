#!/bin/bash
set -e

echo "Starting Antigen Backend..."

# Run database migrations
echo "Running database migrations..."
cd /app/backend
alembic upgrade head

# Build frontend for production
echo "Building frontend..."
cd /app/frontend
npm run build
echo "Copying frontend build to backend static directory..."
mkdir -p /app/backend/static
cp -r dist/* /app/backend/static/
cd /app/backend

# Start the application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
