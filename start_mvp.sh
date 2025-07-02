#!/bin/bash

# Insurance Manager MVP Startup Script
# This script starts all the necessary services for the MVP

echo "🚀 Starting Insurance Manager MVP..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup first."
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if PostgreSQL is running
echo "🗄️ Checking PostgreSQL..."
if ! pgrep -x "postgres" > /dev/null; then
    echo "🔄 Starting PostgreSQL..."
    sudo -u postgres pg_ctlcluster 17 main start
fi

# Check if Redis is running
echo "🔄 Checking Redis..."
if ! pgrep -x "redis-server" > /dev/null; then
    echo "🔄 Starting Redis..."
    sudo redis-server --daemonize yes
fi

# Wait a moment for services to start
sleep 2

# Run database migrations
echo "🗃️ Running database migrations..."
alembic upgrade head

# Start the FastAPI server
echo "🌐 Starting FastAPI server..."
echo "📚 API Documentation will be available at: http://127.0.0.1:8001/api/docs"
echo "🔍 Health Check available at: http://127.0.0.1:8001/api/v1/health"
echo ""
echo "🎮 Insurance Manager MVP is starting..."
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload