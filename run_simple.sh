#!/bin/bash
# Simple run script using venv instead of Poetry

set -e

echo "🚀 Starting Todoist-Capacities Sync..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run these commands first:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install fastapi 'uvicorn[standard]' httpx pydantic pydantic-settings python-dotenv orjson tenacity google-cloud-firestore google-cloud-secret-manager google-cloud-pubsub"
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi

# Activate venv and run
source venv/bin/activate
echo "✅ Starting server on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

