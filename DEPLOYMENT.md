# 🚀 Deployment Guide - Google Cloud Platform

**Target Platform**: Google Cloud Run  
**Difficulty**: Intermediate  
**Time Required**: 30-45 minutes  
**Cost**: ~$5-10/month for typical usage

## 📋 Prerequisites

### Required

- ✅ Google Cloud Platform account with billing enabled
- ✅ `gcloud` CLI installed ([Install guide](https://cloud.google.com/sdk/docs/install))
- ✅ Working local setup (tested with `./test_apis.sh`)
- ✅ Notion integration configured
- ✅ Todoist API token

### Recommended

- Basic understanding of GCP services
- Familiarity with Docker
- Understanding of environment variables

## 🏗️ Architecture Overview

```
Internet
   │
   ├──> Cloud Run (FastAPI Service)
   │      ├──> Pub/Sub Topic (todoist-sync-jobs)
   │      ├──> Firestore (sync state)
   │      └──> Secret Manager (API tokens)
   │
   ├──> Cloud Scheduler (hourly reconciliation)
   │
   └──> Todoist Webhooks
```

### GCP Services Used

| Service | Purpose | Estimated Cost |
|---------|---------|----------------|
| **Cloud Run** | Hosts FastAPI application | ~$2-5/month |
| **Pub/Sub** | Message queue for sync jobs | ~$0.50/month |
| **Firestore** | Stores sync state | ~$1-2/month |
| **Secret Manager** | Secures API tokens | ~$0.10/month |
| **Cloud Scheduler** | Triggers reconciliation | ~$0.10/month |
| **Cloud Logging** | Application logs | ~$1/month |

**Total**: ~$13-20/month for typical usage (100-500 tasks synced daily)

**Cost Optimizations Applied:**
- Reconciliation schedule: Every 2 hours, 5am-9pm Pacific (9x/day vs 24x/day)
- Savings: ~60% reduction in Cloud Run costs vs hourly scheduling
- No overnight syncs when not actively working

## 🔧 Step-by-Step Deployment

### Step 1: Set Up GCP Project

```bash
# 1. Create a new GCP project
PROJECT_ID="todoist-notion-sync"
gcloud projects create $PROJECT_ID --name="Todoist Notion Sync"

# 2. Set as active project
gcloud config set project $PROJECT_ID

# 3. Link billing account (replace with your billing account ID)
# Find your billing account: gcloud billing accounts list
BILLING_ACCOUNT_ID="YOUR-BILLING-ACCOUNT-ID"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID

# 4. Enable required APIs
gcloud services enable \
    run.googleapis.com \
    pubsub.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com
```

### Step 2: Create Firestore Database

```bash
# Create Firestore in Native mode
gcloud firestore databases create \
    --location=us-central1 \
    --type=firestore-native

# Verify creation
gcloud firestore databases describe --database="(default)"
```

### Step 3: Store Secrets

```bash
# 1. Create secrets
echo -n "YOUR_TODOIST_TOKEN" | gcloud secrets create TODOIST_OAUTH_TOKEN --data-file=-
echo -n "YOUR_NOTION_API_KEY" | gcloud secrets create NOTION_API_KEY --data-file=-
echo -n "YOUR_TASKS_DB_ID" | gcloud secrets create NOTION_TASKS_DATABASE_ID --data-file=-
echo -n "YOUR_PROJECTS_DB_ID" | gcloud secrets create NOTION_PROJECTS_DATABASE_ID --data-file=-

# 2. Generate and store secure cron token
CRON_TOKEN=$(openssl rand -base64 32)
echo -n "$CRON_TOKEN" | gcloud secrets create INTERNAL_CRON_TOKEN --data-file=-
echo "⚠️  Save this token securely: $CRON_TOKEN"

# 3. Verify secrets created
gcloud secrets list
```

### Step 4: Create Pub/Sub Topic and Subscription

```bash
# 1. Create topic
gcloud pubsub topics create todoist-sync-jobs

# 2. Create subscription
gcloud pubsub subscriptions create todoist-sync-worker \
    --topic=todoist-sync-jobs \
    --ack-deadline=60 \
    --message-retention-duration=7d

# 3. Verify
gcloud pubsub topics list
gcloud pubsub subscriptions list
```

### Step 5: Build and Deploy Container

```bash
# 1. Set up Artifact Registry
gcloud artifacts repositories create todoist-notion \
    --repository-format=docker \
    --location=us-central1

# 2. Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev

# 3. Build container
PROJECT_ID=$(gcloud config get-value project)
IMAGE_URL="us-central1-docker.pkg.dev/$PROJECT_ID/todoist-notion/sync-service:latest"

docker build -t $IMAGE_URL .

# 4. Push to Artifact Registry
docker push $IMAGE_URL

# 5. Deploy to Cloud Run
gcloud run deploy todoist-notion-sync \
    --image=$IMAGE_URL \
    --platform=managed \
    --region=us-central1 \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300 \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=10 \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
    --set-secrets="TODOIST_OAUTH_TOKEN=TODOIST_OAUTH_TOKEN:latest,\
NOTION_API_KEY=NOTION_API_KEY:latest,\
NOTION_TASKS_DATABASE_ID=NOTION_TASKS_DATABASE_ID:latest,\
NOTION_PROJECTS_DATABASE_ID=NOTION_PROJECTS_DATABASE_ID:latest,\
INTERNAL_CRON_TOKEN=INTERNAL_CRON_TOKEN:latest"

# 6. Get service URL
SERVICE_URL=$(gcloud run services describe todoist-notion-sync \
    --region=us-central1 \
    --format='value(status.url)')
echo "✅ Service deployed at: $SERVICE_URL"
```

### Step 6: Set Up Cloud Scheduler

```bash
# 1. Create scheduler job for reconciliation (every 2 hours, 5am-9pm Pacific)
gcloud scheduler jobs create http todoist-reconcile \
    --location=us-central1 \
    --schedule="0 5-22/2 * * *" \
    --uri="$SERVICE_URL/reconcile" \
    --http-method=POST \
    --headers="Authorization=Bearer $CRON_TOKEN" \
    --attempt-deadline=300s

# 2. Test the job
gcloud scheduler jobs run todoist-reconcile --location=us-central1

# 3. Verify
gcloud scheduler jobs list --location=us-central1
```

### Step 7: Configure Todoist Webhook

```bash
# Your webhook URL
echo "Todoist Webhook URL: $SERVICE_URL/todoist/webhook"
```

1. Go to [Todoist App Management](https://developer.todoist.com/appconsole.html)
2. Select your app or create a new one
3. Under "Webhooks":
   - **Callback URL**: `$SERVICE_URL/todoist/webhook`
   - **Events**: Select `item:*` and `note:*`
4. Save changes

### Step 8: Verify Deployment

```bash
# 1. Check service health
curl $SERVICE_URL/health

# 2. View logs
gcloud run services logs read todoist-notion-sync \
    --region=us-central1 \
    --limit=50

# 3. Test sync (create a test task with capsync label in Todoist)
# Watch logs for webhook events
gcloud run services logs tail todoist-notion-sync \
    --region=us-central1
```

## 🔍 Monitoring

### View Logs

```bash
# Real-time logs
gcloud run services logs tail todoist-notion-sync --region=us-central1

# Recent logs with filter
gcloud logging read \
    "resource.type=cloud_run_revision AND resource.labels.service_name=todoist-notion-sync" \
    --limit=100 \
    --format=json

# Search for errors
gcloud logging read \
    "resource.type=cloud_run_revision AND severity>=ERROR" \
    --limit=50
```

### Check Metrics

```bash
# View in Cloud Console
echo "Metrics: https://console.cloud.google.com/run/detail/us-central1/todoist-notion-sync/metrics?project=$PROJECT_ID"

# Key metrics to monitor:
# - Request count
# - Request latency
# - Error rate
# - Instance count
# - CPU/Memory utilization
```

### Set Up Alerts

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
    --notification-channels=YOUR_CHANNEL_ID \
    --display-name="High Error Rate" \
    --condition-display-name="Error rate > 5%" \
    --condition-threshold-value=0.05 \
    --condition-threshold-duration=300s
```

## 🔒 Security Best Practices

### 1. Service Account Permissions

```bash
# Create dedicated service account
gcloud iam service-accounts create todoist-sync-sa \
    --display-name="Todoist Sync Service Account"

# Grant minimal permissions
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="todoist-sync-sa@$PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/pubsub.publisher"

# Update Cloud Run to use service account
gcloud run services update todoist-notion-sync \
    --service-account=$SA_EMAIL \
    --region=us-central1
```

### 2. Restrict Access

```bash
# Remove public access (if using internal only)
gcloud run services remove-iam-policy-binding todoist-notion-sync \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --region=us-central1

# Add specific allowed users
gcloud run services add-iam-policy-binding todoist-notion-sync \
    --member="user:your-email@example.com" \
    --role="roles/run.invoker" \
    --region=us-central1
```

### 3. Rotate Secrets

```bash
# Add new version of secret
echo -n "NEW_TOKEN" | gcloud secrets versions add TODOIST_OAUTH_TOKEN --data-file=-

# Cloud Run will use latest version automatically
# Verify
gcloud secrets versions list TODOIST_OAUTH_TOKEN
```

## 💰 Cost Optimization

### 1. Adjust Cloud Run Settings

```bash
# Reduce min instances to 0 (cold starts OK)
# Reduce memory if usage is low
gcloud run services update todoist-notion-sync \
    --min-instances=0 \
    --memory=256Mi \
    --region=us-central1
```

### 2. Set Budget Alerts

```bash
# Create budget alert
gcloud billing budgets create \
    --billing-account=$BILLING_ACCOUNT_ID \
    --display-name="Todoist Sync Budget" \
    --budget-amount=10USD \
    --threshold-rule=percent=50 \
    --threshold-rule=percent=90 \
    --threshold-rule=percent=100
```

### 3. Monitor Costs

- Visit [GCP Billing](https://console.cloud.google.com/billing)
- Review cost breakdown by service
- Set up cost anomaly alerts

## 🔄 Updates and Maintenance

### Deploy New Version

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild and push
docker build -t $IMAGE_URL .
docker push $IMAGE_URL

# 3. Deploy update
gcloud run services update todoist-notion-sync \
    --image=$IMAGE_URL \
    --region=us-central1

# 4. Verify
curl $SERVICE_URL/health
```

### Rollback

```bash
# List revisions
gcloud run revisions list --service=todoist-notion-sync --region=us-central1

# Rollback to previous revision
gcloud run services update-traffic todoist-notion-sync \
    --to-revisions=REVISION_NAME=100 \
    --region=us-central1
```

## 🧪 Testing Production

```bash
# 1. Test health endpoint
curl $SERVICE_URL/health

# 2. Test reconciliation (requires token)
curl -X POST $SERVICE_URL/reconcile \
    -H "Authorization: Bearer $CRON_TOKEN"

# 3. Create test task in Todoist with capsync label
# Watch logs for webhook processing
gcloud run services logs tail todoist-notion-sync --region=us-central1
```

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
gcloud run services logs read todoist-notion-sync --region=us-central1 --limit=50

# Common issues:
# - Missing secrets
# - Invalid environment variables
# - Container build errors
```

### Webhooks Not Working

```bash
# 1. Verify webhook URL in Todoist
# 2. Check Cloud Run allows unauthenticated access
gcloud run services get-iam-policy todoist-notion-sync --region=us-central1

# 3. Check logs for incoming requests
gcloud run services logs tail todoist-notion-sync --region=us-central1 | grep webhook
```

### High Costs

```bash
# Check request counts
gcloud monitoring time-series list \
    --filter='metric.type="run.googleapis.com/request_count"'

# Reduce resources if underutilized
gcloud run services update todoist-notion-sync \
    --memory=256Mi \
    --max-instances=5 \
    --region=us-central1
```

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Pub/Sub Best Practices](https://cloud.google.com/pubsub/docs/best-practices)
- [Firestore Pricing](https://cloud.google.com/firestore/pricing)
- [Secret Manager Guide](https://cloud.google.com/secret-manager/docs)

## ✅ Deployment Checklist

- ✅ GCP project created and billing enabled
- ✅ All required APIs enabled
- ✅ Firestore database created
- ✅ Secrets stored in Secret Manager
- ✅ Pub/Sub topic and subscription created
- ✅ Container built and pushed
- ✅ Cloud Run service deployed
- ✅ Cloud Scheduler job configured
- ✅ Todoist webhook configured
- ✅ Service health verified
- ✅ Test task synced successfully
- ✅ Monitoring and alerts set up
- ✅ Budget alerts configured

**Your production deployment is complete!** 🎉

Tasks will now sync automatically when:
- Webhooks fire from Todoist (real-time)
- Hourly reconciliation runs (catch-up)
