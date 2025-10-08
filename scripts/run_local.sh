#!/bin/bash
# Run the application locally for development

set -e

echo "🚀 Starting Todoist-Capacities Sync locally..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Run with Poetry
poetry run python -m app.main

