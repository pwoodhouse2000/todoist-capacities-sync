# Getting Started with Todoist-Capacities Sync

Welcome! This guide will help you get the sync service running, both locally and in production.

## 🎯 Quick Overview

This service automatically syncs Todoist tasks labeled with `@capsync` to your Capacities workspace as `@ToDo` objects. It uses:
- **Todoist** as the source of truth for tasks
- **Capacities** as the knowledge management destination
- **Google Cloud** for hosting and infrastructure

## 📋 What You Need

### Required Accounts
- ✅ Todoist account with API access
- ✅ Capacities account with API access  
- ✅ Google Cloud account with billing enabled

### Required Software
- [Poetry](https://python-poetry.org/) - Python dependency management
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) - Google Cloud command-line
- [Terraform](https://www.terraform.io/downloads) - Infrastructure as code
- Python 3.11+

## 🚀 Option 1: Local Development (Test First!)

### Step 1: Get Your API Tokens

#### Todoist Token
✅ **Already provided**: `c48f86e2730782b3b263e45b3f589ccad89e5b66`

Alternatively, get it from: [Todoist Settings → Integrations](https://todoist.com/prefs/integrations)

#### Capacities API Key
✅ **Already provided**: `xQLRJwaItiQkVcrztUAL8AIOoWarFiO12CP1TAIMGw3QYGtGlB`

Alternatively:
1. Open Capacities desktop app
2. Go to Settings → Capacities API
3. Generate access token

#### Capacities Space ID
⚠️ **You need to get this**:
1. Open Capacities desktop app
2. Go to Settings → Space settings
3. Copy the Space ID

### Step 2: Configure Environment

The `.env` file has been created with your tokens. Edit it to add your Space ID:

```bash
# Edit .env file
nano .env

# Update this line:
CAPACITIES_SPACE_ID=YOUR_SPACE_ID_HERE
```

### Step 3: Install Dependencies

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install
```

### Step 4: Test Locally

```bash
# Run the service
./scripts/run_local.sh

# The service will start on http://localhost:8000
```

### Step 5: Test with a Task

In another terminal:

```bash
# Send a test webhook
curl -X POST http://localhost:8000/todoist/webhook \
  -H "Content-Type: application/json" \
  -d @scripts/sample_webhook.json
```

**Or create a real test:**
1. Open Todoist
2. Create a task: "Test sync to Capacities"
3. Add label: `@capsync`
4. Check your Capacities - it should appear!

## ☁️ Option 2: Deploy to Google Cloud

### Step 1: Set Up GCP Project

```bash
# Set your project ID (choose a unique name)
export GCP_PROJECT_ID=todoist-capacities-sync-$(whoami)

# Create project
gcloud projects create $GCP_PROJECT_ID

# Set as active project
gcloud config set project $GCP_PROJECT_ID

# Link billing (you need to know your billing account ID)
gcloud beta billing accounts list
gcloud beta billing projects link $GCP_PROJECT_ID --billing-account=YOUR-BILLING-ACCOUNT-ID
```

### Step 2: Enable APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Step 3: Initialize Firestore

```bash
gcloud firestore databases create --region=us-central1
```

### Step 4: Seed Secrets

```bash
# The .env file already has your tokens
source .env

# Seed to GCP Secret Manager
./scripts/seed_secrets.sh
```

**Important**: Save the `INTERNAL_CRON_TOKEN` that gets generated!

### Step 5: Build Container Image

```bash
export REGION=us-central1

gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/default/todoist-capacities-sync:v1
```

This will take 5-10 minutes.

### Step 6: Configure Terraform

```bash
cd infra/terraform

# Copy example config
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

Update these values:
```hcl
project_id          = "your-actual-project-id"
image               = "us-central1-docker.pkg.dev/your-actual-project-id/default/todoist-capacities-sync:v1"
capacities_space_id = "your-space-id-from-capacities"
```

### Step 7: Deploy Infrastructure

```bash
# Still in infra/terraform directory
terraform init
terraform plan
terraform apply
```

Type `yes` when prompted.

**Save the outputs!** You'll need:
- `webhook_url` - for Todoist webhook configuration
- `cloud_run_url` - for testing

### Step 8: Configure Todoist Webhook

1. Go to [Todoist Integrations](https://todoist.com/prefs/integrations)
2. Click "Webhooks" tab
3. Add webhook with the URL from Terraform output
4. Select events:
   - ✅ item:added
   - ✅ item:updated
   - ✅ item:completed
   - ✅ item:uncompleted
   - ✅ item:deleted
   - ✅ note:added
   - ✅ note:updated

### Step 9: Test Production

```bash
# Health check
curl https://YOUR-CLOUD-RUN-URL/health

# Create a real task in Todoist with @capsync label
# Check Capacities - should appear within 5 seconds!

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit=20
```

## 🎯 What Happens Now?

### Automatic Syncing
- Any Todoist task with `@capsync` label automatically syncs to Capacities
- Updates to title, description, due date, priority, etc. sync in real-time
- Comments sync as markdown in the task body
- Completing a task marks it complete in Capacities
- Removing `@capsync` or deleting the task archives it in Capacities

### Hourly Reconciliation
- Cloud Scheduler runs reconciliation every hour
- Catches any missed webhook events
- Ensures Todoist and Capacities stay in sync

## 🐛 Troubleshooting

### "Module not found" errors
```bash
# Reinstall dependencies
poetry install
```

### "CAPACITIES_SPACE_ID not set"
Edit `.env` file and add your Space ID from Capacities settings.

### Tasks not appearing in Capacities
1. Check task has `@capsync` label
2. Check Cloud Run logs: `gcloud logging read "resource.type=cloud_run_revision" --limit=20`
3. Verify Capacities API key is valid
4. Check Capacities API documentation for any changes

### Webhook not working
1. Verify webhook URL in Todoist matches Cloud Run URL
2. Check Cloud Run logs for incoming requests
3. Test with sample webhook: `curl -X POST https://YOUR-URL/todoist/webhook -d @scripts/sample_webhook.json`

## 📊 Monitoring

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision" \
  --project=$GCP_PROJECT_ID \
  --limit=50
```

### Check Sync Status
Firestore stores sync state for each task:
```bash
gcloud firestore documents list \
  --collection-ids=todoist-capacities-v1_tasks \
  --project=$GCP_PROJECT_ID
```

### Trigger Manual Reconciliation
```bash
curl -X POST https://YOUR-CLOUD-RUN-URL/reconcile \
  -H "Authorization: Bearer YOUR-INTERNAL-CRON-TOKEN"
```

## 💡 Tips

1. **Start small**: Test locally first with a few tasks
2. **Use a test project**: Create a test project in both Todoist and Capacities
3. **Monitor costs**: Check GCP billing dashboard regularly
4. **Check logs**: When something doesn't work, logs are your friend
5. **Capacities API is beta**: The API may change; check docs if issues arise

## 📚 Next Steps

- Read [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment info
- Check [README.md](README.md) for architecture details
- Review the [Capacities API docs](https://docs.capacities.io/developer/api)
- Customize sync behavior in `app/mapper.py`

## 🆘 Need Help?

1. Check the logs (most issues show up there)
2. Review the Capacities API documentation
3. Create an issue on GitHub with:
   - What you tried
   - What happened
   - Relevant log excerpts
   - Your configuration (without secrets!)

---

**Happy syncing!** 🚀

