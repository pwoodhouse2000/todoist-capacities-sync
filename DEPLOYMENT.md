# Deployment Guide

This guide walks you through deploying the Todoist-Capacities Sync service to Google Cloud Platform.

## Prerequisites

- Google Cloud Platform account with billing enabled
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and configured
- [Terraform](https://www.terraform.io/downloads) >= 1.0 installed
- [Poetry](https://python-poetry.org/docs/#installation) installed (for local development)
- Docker installed (for building images locally)

## Step 1: Create GCP Project

1. Create a new GCP project:
```bash
gcloud projects create YOUR-PROJECT-ID
gcloud config set project YOUR-PROJECT-ID
```

2. Link billing account:
```bash
gcloud beta billing projects link YOUR-PROJECT-ID --billing-account=YOUR-BILLING-ACCOUNT-ID
```

## Step 2: Enable Required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

## Step 3: Initialize Firestore

Firestore must be initialized before deployment:

```bash
gcloud firestore databases create --region=us-central1
```

## Step 4: Set Up Secrets

Create a `.env` file with your credentials:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Then seed the secrets to GCP Secret Manager:

```bash
export GCP_PROJECT_ID=YOUR-PROJECT-ID
export TODOIST_OAUTH_TOKEN=your-todoist-token
export CAPACITIES_API_KEY=your-capacities-key

./scripts/seed_secrets.sh
```

**Important:** Save the generated `INTERNAL_CRON_TOKEN` - you'll need it to trigger reconciliation.

## Step 5: Build and Push Container Image

```bash
export GCP_PROJECT_ID=YOUR-PROJECT-ID
export REGION=us-central1

gcloud builds submit --tag ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/default/todoist-capacities-sync:latest
```

## Step 6: Configure Terraform

1. Copy the example tfvars:
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars` with your values:
```hcl
project_id          = "your-gcp-project-id"
region              = "us-central1"
image               = "us-central1-docker.pkg.dev/your-gcp-project-id/default/todoist-capacities-sync:latest"
capacities_space_id = "your-capacities-space-id"
```

**Finding your Capacities Space ID:**
- Open Capacities desktop app
- Go to Settings → Space settings
- Copy the Space ID

## Step 7: Deploy with Terraform

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

Take note of the outputs, especially `cloud_run_url` and `webhook_url`.

## Step 8: Configure Todoist Webhook

1. Go to [Todoist App Settings](https://todoist.com/prefs/integrations)
2. Click on "Webhooks" tab
3. Add a new webhook:
   - **URL**: `https://YOUR-CLOUD-RUN-URL/todoist/webhook` (from Terraform output)
   - **Events**: Select:
     - `item:added`
     - `item:updated`
     - `item:completed`
     - `item:uncompleted`
     - `item:deleted`
     - `note:added`
     - `note:updated`
4. Save the webhook

## Step 9: Test the Deployment

### Test Health Check
```bash
curl https://YOUR-CLOUD-RUN-URL/health
```

### Test Webhook Processing
```bash
curl -X POST https://YOUR-CLOUD-RUN-URL/todoist/webhook \
  -H "Content-Type: application/json" \
  -d @scripts/sample_webhook.json
```

### Create a Real Test Task
1. In Todoist, create a new task
2. Add the `@capsync` label
3. Check Capacities - the task should appear within 5 seconds
4. Check Cloud Run logs:
```bash
gcloud logging read "resource.type=cloud_run_revision" \
  --project=YOUR-PROJECT-ID \
  --limit=50
```

### Test Reconciliation
```bash
curl -X POST https://YOUR-CLOUD-RUN-URL/reconcile \
  -H "Authorization: Bearer YOUR-INTERNAL-CRON-TOKEN"
```

## Monitoring and Logs

### View Cloud Run Logs
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=todoist-capacities-sync" \
  --project=YOUR-PROJECT-ID \
  --limit=50 \
  --format=json
```

### Check Pub/Sub Queue Status
```bash
gcloud pubsub subscriptions describe todoist-sync-worker \
  --project=YOUR-PROJECT-ID
```

### View Cloud Scheduler Jobs
```bash
gcloud scheduler jobs list --project=YOUR-PROJECT-ID
```

### Monitor Firestore Data
```bash
# View task sync states
gcloud firestore documents list \
  --collection-ids=todoist-capacities-v1_tasks \
  --project=YOUR-PROJECT-ID
```

## Updating the Service

To deploy updates:

1. Build new image:
```bash
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/default/todoist-capacities-sync:v2
```

2. Update Terraform variable:
```bash
cd infra/terraform
terraform apply -var="image=${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/default/todoist-capacities-sync:v2"
```

## Troubleshooting

### Webhooks Not Triggering

1. Check webhook configuration in Todoist
2. Verify Cloud Run URL is publicly accessible
3. Check Cloud Run logs for errors:
```bash
gcloud logging read "resource.type=cloud_run_revision" --limit=20
```

### Tasks Not Syncing

1. Ensure task has `@capsync` label
2. Check Pub/Sub subscription for backlog:
```bash
gcloud pubsub subscriptions describe todoist-sync-worker
```
3. Check Firestore for task state
4. Verify Capacities API key is valid

### Reconciliation Not Running

1. Check Cloud Scheduler job status:
```bash
gcloud scheduler jobs describe todoist-capacities-sync-reconcile
```
2. Manually trigger reconciliation to test
3. Check Cloud Run logs for reconciliation runs

### Capacities API Errors

The Capacities API is in beta and endpoints may change. If you encounter API errors:

1. Check the [Capacities API documentation](https://docs.capacities.io/developer/api)
2. Review `app/capacities_client.py` and adjust endpoints/payload structure
3. Test API calls directly using curl:
```bash
curl -X POST https://api.capacities.io/save-object \
  -H "Authorization: Bearer YOUR-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{"spaceId":"YOUR-SPACE-ID","structureId":"...","properties":{...}}'
```

## Cost Estimation

Approximate monthly costs (may vary):

- **Cloud Run**: ~$5-20/month (depending on usage)
- **Pub/Sub**: ~$1-5/month
- **Firestore**: ~$1-10/month
- **Secret Manager**: ~$0.50/month
- **Cloud Scheduler**: $0.10/month per job

**Total**: ~$10-40/month for light-medium usage

## Security Best Practices

1. **Never commit secrets** to git
2. **Rotate API tokens** periodically
3. **Monitor logs** for suspicious activity
4. **Use VPC** for additional network security (optional)
5. **Enable audit logging** for compliance

## Cleanup

To tear down all infrastructure:

```bash
cd infra/terraform
terraform destroy
```

This will remove:
- Cloud Run service
- Pub/Sub topic and subscription
- Cloud Scheduler job
- Secrets (but not their values)
- IAM bindings

**Note**: Firestore database and data are not automatically deleted. Delete manually if needed.

## Support

For issues:
1. Check the [README](README.md)
2. Review logs in GCP Console
3. Create an issue on GitHub

