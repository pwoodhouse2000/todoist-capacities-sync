#!/bin/bash
# Seed secrets to GCP Secret Manager

set -e

# Check if required env vars are set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ Error: GCP_PROJECT_ID not set"
    exit 1
fi

if [ -z "$TODOIST_OAUTH_TOKEN" ]; then
    echo "❌ Error: TODOIST_OAUTH_TOKEN not set"
    exit 1
fi

if [ -z "$CAPACITIES_API_KEY" ]; then
    echo "❌ Error: CAPACITIES_API_KEY not set"
    exit 1
fi

echo "🔐 Seeding secrets to GCP Secret Manager..."

# Create secrets (ignore errors if they already exist)
gcloud secrets create TODOIST_OAUTH_TOKEN --project="$GCP_PROJECT_ID" 2>/dev/null || true
gcloud secrets create CAPACITIES_API_KEY --project="$GCP_PROJECT_ID" 2>/dev/null || true
gcloud secrets create INTERNAL_CRON_TOKEN --project="$GCP_PROJECT_ID" 2>/dev/null || true

# Add secret versions
echo -n "$TODOIST_OAUTH_TOKEN" | gcloud secrets versions add TODOIST_OAUTH_TOKEN \
    --project="$GCP_PROJECT_ID" \
    --data-file=-

echo -n "$CAPACITIES_API_KEY" | gcloud secrets versions add CAPACITIES_API_KEY \
    --project="$GCP_PROJECT_ID" \
    --data-file=-

# Generate internal cron token if not set
if [ -z "$INTERNAL_CRON_TOKEN" ]; then
    INTERNAL_CRON_TOKEN=$(openssl rand -base64 32)
    echo "Generated INTERNAL_CRON_TOKEN: $INTERNAL_CRON_TOKEN"
    echo "⚠️  Save this token - you'll need it to trigger reconciliation"
fi

echo -n "$INTERNAL_CRON_TOKEN" | gcloud secrets versions add INTERNAL_CRON_TOKEN \
    --project="$GCP_PROJECT_ID" \
    --data-file=-

echo "✅ Secrets seeded successfully!"

