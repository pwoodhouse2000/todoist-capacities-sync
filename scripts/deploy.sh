#!/bin/bash
# Deploy script for Todoist-Capacities Sync

set -e

echo "🚀 Deploying Todoist-Capacities Sync to GCP"

# Check required environment variables
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ Error: GCP_PROJECT_ID not set"
    exit 1
fi

# Configuration
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="todoist-capacities-sync"
IMAGE_NAME="${GCP_PROJECT_ID}/${SERVICE_NAME}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${REGION}-docker.pkg.dev/${IMAGE_NAME}:${IMAGE_TAG}"

echo "📦 Project: $GCP_PROJECT_ID"
echo "🌍 Region: $REGION"
echo "🐳 Image: $FULL_IMAGE"

# Step 1: Build and push container image
echo ""
echo "Step 1: Building and pushing container image..."
gcloud builds submit --tag "$FULL_IMAGE" --project="$GCP_PROJECT_ID" .

# Step 2: Seed secrets (if not already done)
echo ""
echo "Step 2: Checking secrets..."
if ! gcloud secrets describe TODOIST_OAUTH_TOKEN --project="$GCP_PROJECT_ID" &>/dev/null; then
    echo "⚠️  Secrets not found. Run scripts/seed_secrets.sh first!"
    exit 1
fi
echo "✅ Secrets exist"

# Step 3: Initialize Firestore (if not already done)
echo ""
echo "Step 3: Checking Firestore..."
if ! gcloud firestore databases describe --project="$GCP_PROJECT_ID" &>/dev/null; then
    echo "⚠️  Firestore not initialized. Creating database..."
    gcloud firestore databases create --region="$REGION" --project="$GCP_PROJECT_ID"
fi
echo "✅ Firestore ready"

# Step 4: Deploy with Terraform
echo ""
echo "Step 4: Deploying infrastructure with Terraform..."
cd infra/terraform

if [ ! -f terraform.tfvars ]; then
    echo "❌ Error: terraform.tfvars not found"
    echo "Copy terraform.tfvars.example and fill in your values:"
    echo "  cp terraform.tfvars.example terraform.tfvars"
    exit 1
fi

terraform init
terraform plan -var="image=$FULL_IMAGE"
terraform apply -var="image=$FULL_IMAGE" -auto-approve

# Get Cloud Run URL
CLOUD_RUN_URL=$(terraform output -raw cloud_run_url)

cd ../..

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Add Todoist webhook:"
echo "   URL: ${CLOUD_RUN_URL}/todoist/webhook"
echo "   Events: item:*, note:*"
echo ""
echo "2. Test the webhook:"
echo "   curl -X POST ${CLOUD_RUN_URL}/todoist/webhook \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d @scripts/sample_webhook.json"
echo ""
echo "3. View logs:"
echo "   gcloud logging read \"resource.type=cloud_run_revision\" --project=$GCP_PROJECT_ID --limit=50"
echo ""
echo "4. Trigger manual reconciliation:"
echo "   curl -X POST ${CLOUD_RUN_URL}/reconcile \\"
echo "     -H 'Authorization: Bearer YOUR_INTERNAL_CRON_TOKEN'"

