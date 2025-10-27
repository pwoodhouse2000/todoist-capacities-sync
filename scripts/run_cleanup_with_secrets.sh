#!/bin/bash
# Script to run cleanup with secrets loaded from Google Cloud Secret Manager

set -e

PROJECT_ID="notion-todoist-sync-464419"

echo "🔐 Loading secrets from Google Cloud Secret Manager..."

# Load secrets
export TODOIST_OAUTH_TOKEN=$(gcloud secrets versions access latest --secret="todoist-oauth-token" --project="$PROJECT_ID")
export NOTION_API_KEY=$(gcloud secrets versions access latest --secret="notion-api-key" --project="$PROJECT_ID")
export NOTION_TASKS_DATABASE_ID=$(gcloud secrets versions access latest --secret="notion-tasks-database-id" --project="$PROJECT_ID")
export NOTION_PROJECTS_DATABASE_ID=$(gcloud secrets versions access latest --secret="notion-projects-database-id" --project="$PROJECT_ID")
export NOTION_AREAS_DATABASE_ID=$(gcloud secrets versions access latest --secret="notion-areas-database-id" --project="$PROJECT_ID" 2>/dev/null || echo "")
export NOTION_PEOPLE_DATABASE_ID=$(gcloud secrets versions access latest --secret="notion-people-database-id" --project="$PROJECT_ID" 2>/dev/null || echo "")

echo "✅ Secrets loaded"
echo ""

# Activate virtual environment
source .venv/bin/activate

# Run cleanup script with all arguments passed through
echo "🧹 Running cleanup script..."
python scripts/cleanup_duplicate_areas.py "$@"

