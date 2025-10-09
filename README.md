# Todoist → Notion Sync

A production-grade synchronization service that automatically mirrors Todoist tasks labeled with `@capsync` into Notion database pages.

## Overview

This service provides **one-way synchronization** from Todoist to Notion, enabling richer knowledge linking and organization in your Notion workspace while maintaining Todoist as the primary task entry point.

### Key Features

- 🔄 **Real-time sync** via Todoist webhooks
- ⏰ **Hourly reconciliation** to catch missed events
- 🎯 **Label-based gating** using `@capsync`
- 🔗 **Automatic project relations** in Notion
- 💬 **Comment synchronization** as page content
- 🔒 **Secure** secret management via GCP Secret Manager
- 📊 **Observable** with structured logging
- ⚡ **Idempotent** writes via content hashing
- ✅ **Smart updates** - only creates/updates when needed

## Architecture

```
Todoist Webhook → Cloud Run (FastAPI) → Pub/Sub → Worker
                                              ↓
                                         Firestore
                                              ↓
                                        Notion API
```

### GCP Services

- **Cloud Run**: FastAPI webhook receiver + reconcile endpoint
- **Pub/Sub**: Event queue for decoupled processing
- **Firestore**: State management (task mappings, hashes)
- **Secret Manager**: API tokens and credentials
- **Cloud Scheduler**: Hourly reconciliation trigger
- **Cloud Logging**: Structured logs

## Prerequisites

- Python 3.9+
- Google Cloud Platform account with billing enabled (for production)
- Todoist account with API token
- Notion workspace with integration access

## Quick Start

See **[NOTION_SETUP.md](NOTION_SETUP.md)** for complete step-by-step setup instructions!

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Or with Poetry:
```bash
poetry install
```

### 2. Set up Notion

Follow the detailed guide in [NOTION_SETUP.md](NOTION_SETUP.md) to:
1. Create a Notion integration
2. Create two databases (Projects and Tasks)
3. Get your database IDs
4. Configure the `.env` file

### 3. Run Locally

```bash
./run_simple.sh
```

The service will start on `http://localhost:8000`

### 4. Test the Setup

```bash
./test_apis.sh
```

This will verify:
- ✅ Service is running
- ✅ Todoist API connection
- ✅ Notion API connection and database access

### 5. Sync a Test Task

```bash
# Get a task ID from Todoist
curl "http://localhost:8000/test/todoist?show_tasks=true"

# Test sync (dry run)
curl "http://localhost:8000/test/sync-task/YOUR_TASK_ID?dry_run=true"

# Actually sync to Notion
curl "http://localhost:8000/test/sync-task/YOUR_TASK_ID?dry_run=false"
```

## Project Structure

```
/app
  main.py                 # FastAPI application entry point
  handlers.py            # Webhook and reconcile handlers
  mapper.py              # Todoist → Notion data transformation
  models.py              # Pydantic data models
  todoist_client.py      # Todoist API client
  notion_client.py       # Notion API client (NEW!)
  store.py               # Firestore operations
  logging_setup.py       # Structured logging configuration
  settings.py            # Environment configuration
  pubsub_worker.py       # Pub/Sub message processing
  utils.py               # Utility functions

/tests
  test_mapper.py         # Unit tests for data mapping

/infra/terraform
  main.tf                # Main Terraform configuration
  cloud_run.tf           # Cloud Run service
  pubsub.tf              # Pub/Sub topic and subscription
  scheduler.tf           # Cloud Scheduler job
  firestore.tf           # Firestore database
  secrets.tf             # Secret Manager configuration

/scripts
  run_local.sh           # Local development server
  seed_secrets.sh        # Seed GCP secrets

NOTION_SETUP.md          # Complete Notion setup guide
```

## Data Model

### Notion Task Page Properties

| Property | Source |
|----------|--------|
| `Name` (Title) | Todoist `content` |
| `Todoist Task ID` | Unique identifier |
| `Todoist URL` | Deep link to task |
| `Priority` | Priority level (P1-P4) |
| `Labels` | All labels (multi-select) |
| `Due Date` | Due date |
| `Completed` | Completion checkbox |
| `Project` (Relation) | Link to Project page |
| **Page Body** | Description + comments |

### Notion Project Page Properties

| Property | Source |
|----------|--------|
| `Name` (Title) | Todoist project name |
| `Todoist Project ID` | Unique identifier |
| `Todoist URL` | Deep link to project |
| `Color` | Project color |
| `Is Shared` | Sharing status |

## Sync Behavior

### Create / Update
- Task labeled with `@capsync` → create/update page in Notion
- Ensure Project page exists and create relation
- Update all properties on every sync

### Complete
- Task completed in Todoist → set `Completed=true` in Notion
- Task remains visible (not archived by default)

### Delete / Untag
- Task deleted or `@capsync` removed → archive in Notion
- Page is archived and marked as completed

### Comments
- Full comment history synced to page body
- Formatted as markdown sections

## API Endpoints

### `GET /`
Service status and health

### `GET /health`
Health check endpoint

### `GET /test/todoist`
Test Todoist API connection
- Add `?show_tasks=true` to see recent tasks

### `GET /test/notion`
Test Notion API connection and database access

### `GET /test/sync-task/{task_id}`
Test syncing a specific task
- `?dry_run=true` (default) - simulate only
- `?dry_run=false` - actually create in Notion

### `POST /todoist/webhook`
Receives Todoist webhook events (production)

### `POST /reconcile`
Manually trigger full reconciliation (requires auth token)

## Deployment to GCP

### 1. Create GCP Project
```bash
gcloud projects create todoist-notion-sync
gcloud config set project todoist-notion-sync
```

### 2. Enable APIs
```bash
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
```

### 3. Create Secrets
```bash
echo -n "YOUR_TODOIST_TOKEN" | gcloud secrets create TODOIST_OAUTH_TOKEN --data-file=-
echo -n "YOUR_NOTION_KEY" | gcloud secrets create NOTION_API_KEY --data-file=-
echo -n "YOUR_TASKS_DB_ID" | gcloud secrets create NOTION_TASKS_DATABASE_ID --data-file=-
echo -n "YOUR_PROJECTS_DB_ID" | gcloud secrets create NOTION_PROJECTS_DATABASE_ID --data-file=-
echo -n "$(openssl rand -base64 32)" | gcloud secrets create INTERNAL_CRON_TOKEN --data-file=-
```

### 4. Deploy with Terraform
```bash
cd infra/terraform
terraform init
terraform plan -var="project_id=todoist-notion-sync"
terraform apply -var="project_id=todoist-notion-sync"
```

### 5. Configure Todoist Webhook
After deployment:
1. Go to Todoist Settings → Integrations → Webhooks
2. Add webhook URL: `https://YOUR-CLOUD-RUN-URL/todoist/webhook`
3. Select events: `item:*`, `note:*`

## Development

### Run Tests
```bash
pytest
```

### Linting
```bash
ruff check .
mypy app
```

### Format Code
```bash
ruff format .
```

## Monitoring

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=todoist-notion-sync" --limit 50
```

### Check Pub/Sub Queue
```bash
gcloud pubsub subscriptions describe todoist-sync-worker
```

## Troubleshooting

### Notion API errors
- Verify integration secret in `.env`
- Check database IDs are correct (32 chars with hyphens)
- Ensure databases are shared with your integration
- Verify all required properties exist in databases

### Tasks not appearing
- Ensure task has `@capsync` label in Todoist
- Check service logs for errors
- Verify Notion databases are accessible

### Connection issues
- Check network connectivity
- Verify API keys are valid
- Review rate limits

For detailed troubleshooting, see [NOTION_SETUP.md](NOTION_SETUP.md).

## Why Notion?

Notion was chosen over Capacities because:
- ✅ **Mature API** with full object creation support
- ✅ **Rich property types** (relations, selects, dates)
- ✅ **Excellent documentation** and official SDK
- ✅ **Production-ready** and stable
- ✅ **Powerful views** (tables, kanban, calendar, etc.)

## License

MIT

## Support

For issues and questions, please create an issue in the GitHub repository.
