#!/bin/bash

# Insurance Manager Complete MVP Startup Script
# This script starts both backend and frontend services for the full MVP experience

echo "🚀 Starting Insurance Manager Complete MVP..."

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

# Check if frontend dependencies are installed
echo "📦 Checking frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    echo "🔄 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Start the FastAPI server in background
echo "🌐 Starting FastAPI backend server..."
echo "📚 API Documentation will be available at: http://localhost:8001/api/docs"
echo "🔍 Health Check available at: http://localhost:8001/api/v1/health"

uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload > /tmp/backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Start the Next.js frontend
echo "🎨 Starting Next.js frontend..."
echo "🌟 Frontend will be available at: http://localhost:3000"
cd frontend
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 5

echo ""
echo "✅ Insurance Manager MVP is now FULLY OPERATIONAL!"
echo ""
echo "🌐 Access Points:"
echo "   📱 Frontend (Students): http://localhost:3000"
echo "   🔧 API Documentation: http://localhost:8001/api/docs"
echo "   ❤️  Health Check: http://localhost:8001/api/v1/health"
echo ""
echo "🎮 Quick Start:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Click 'Sign up' to create a new account"
echo "   3. Complete CEO character creation"
echo "   4. Start your insurance company"
echo "   5. Begin making strategic decisions!"
echo ""
echo "📝 Logs:"
echo "   Backend: tail -f /tmp/backend.log"
echo "   Frontend: tail -f /tmp/frontend.log"
echo ""
echo "🛑 To stop all services: kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to view logs or use the URLs above to access the MVP"
echo ""

# Create a simple process monitor that shows both services are running
while true; do
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ Backend process died! Check /tmp/backend.log"
        break
    fi
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "❌ Frontend process died! Check /tmp/frontend.log"
        break
    fi
    
    # Check if services are responding
    if curl -s http://localhost:8001/api/v1/health > /dev/null 2>&1; then
        BACKEND_STATUS="✅"
    else
        BACKEND_STATUS="❌"
    fi
    
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        FRONTEND_STATUS="✅"
    else
        FRONTEND_STATUS="❌"
    fi
    
    echo -ne "\r🚀 MVP Status: Backend $BACKEND_STATUS | Frontend $FRONTEND_STATUS | Press Ctrl+C to exit"
    sleep 5
done