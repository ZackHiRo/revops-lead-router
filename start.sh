#!/bin/bash

# Revenue Ops Lead Router & Enricher Startup Script

echo "🚀 Starting Revenue Ops Lead Router & Enricher..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp env.example .env
    echo "📝 Please edit .env file with your API keys before continuing."
    echo "   Press Enter when ready, or Ctrl+C to cancel..."
    read
fi

# Start Redis if Docker is available
if command -v docker &> /dev/null; then
    echo "🐳 Starting Redis with Docker..."
    docker-compose -f infra/docker-compose.yml up -d redis
    
    # Wait for Redis to be ready
    echo "⏳ Waiting for Redis to be ready..."
    sleep 5
else
    echo "⚠️  Docker not found. Please ensure Redis is running on localhost:6379"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the application
echo "🌟 Starting FastAPI application..."
echo "📱 API will be available at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"
echo "🔍 Health check at: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

python app.py
