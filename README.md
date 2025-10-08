# Todoist → Capacities Sync

A production-grade synchronization service that automatically mirrors Todoist tasks labeled with `@capsync` into Capacities as `@ToDo` objects.

## Overview

This service provides **one-way synchronization** from Todoist to Capacities, enabling richer knowledge linking and archival in your Capacities workspace while maintaining Todoist as the primary task entry point.

### Key Features

- 🔄 **Real-time sync** via Todoist webhooks
- ⏰ **Hourly reconciliation** to catch missed events
- 🎯 **Label-based gating** using `@capsync`
- 🔗 **Automatic project relations** in Capacities
- 💬 **Comment synchronization** as markdown
- 🔒 **Secure** secret management via GCP Secret Manager
- 📊 **Observable** with structured logging
- ⚡ **Idempotent** writes via content hashing

## Architecture

```
Todoist Webhook → Cloud Run (FastAPI) → Pub/Sub → Worker
                                              ↓
                                         Firestore
                                              ↓
                                    Capacities API
```

### GCP Services

- **Cloud Run**: FastAPI webhook receiver + reconcile endpoint
- **Pub/Sub**: Event queue for decoupled processing
- **Firestore**: State management (task mappings, hashes)
- **Secret Manager**: API tokens and credentials
- **Cloud Scheduler**: Hourly reconciliation trigger
- **Cloud Logging**: Structured logs

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management
- Google Cloud Platform account with billing enabled
- Todoist account with API token
- Capacities account with API access

## Quick Start

### 1. Install Dependencies

```bash
poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
- `GCP_PROJECT_ID`: Your GCP project ID
- `TODOIST_OAUTH_TOKEN`: Get from Todoist Settings → Integrations
- `CAPACITIES_API_KEY`: Get from Capacities Settings → API
- `CAPACITIES_SPACE_ID`: Get from Capacities Settings → Space settings

### 3. Run Locally

```bash
./scripts/run_local.sh
```

The service will start on `http://localhost:8000`

### 4. Test Webhook

```bash
curl -X POST http://localhost:8000/todoist/webhook \
  -H "Content-Type: application/json" \
  -d @scripts/sample_webhook.json
```

## Deployment

### GCP Setup

1. **Create GCP Project**
```bash
gcloud projects create todoist-capacities-sync
gcloud config set project todoist-capacities-sync
```

2. **Enable APIs**
```bash
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
```

3. **Create Secrets**
```bash
echo -n "YOUR_TODOIST_TOKEN" | gcloud secrets create TODOIST_OAUTH_TOKEN --data-file=-
echo -n "YOUR_CAPACITIES_KEY" | gcloud secrets create CAPACITIES_API_KEY --data-file=-
echo -n "$(openssl rand -base64 32)" | gcloud secrets create INTERNAL_CRON_TOKEN --data-file=-
```

### Terraform Deployment

```bash
cd infra/terraform
terraform init
terraform plan -var="project_id=todoist-capacities-sync"
terraform apply -var="project_id=todoist-capacities-sync"
```

### Configure Todoist Webhook

After deployment, add webhook in Todoist:
1. Go to Todoist Settings → Integrations → Webhooks
2. Add webhook URL: `https://YOUR-CLOUD-RUN-URL/todoist/webhook`
3. Select events: `item:*`, `note:*`

## Project Structure

```
/app
  main.py                 # FastAPI application entry point
  handlers.py            # Webhook and reconcile handlers
  mapper.py              # Todoist → Capacities data transformation
  models.py              # Pydantic data models
  todoist_client.py      # Todoist API client
  capacities_client.py   # Capacities API client
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
  sample_webhook.json    # Example webhook payload
```

## Data Model

### Capacities @ToDo Fields

| Field | Source |
|-------|--------|
| `title` | Todoist `content` |
| `body` | Description + comments (markdown) |
| `todoist_task_id` | Unique identifier |
| `todoist_url` | Deep link to task |
| `todoist_project_id` | Project ID |
| `project` | Relation to Project object |
| `todoist_labels` | All labels (preserve `@`) |
| `priority` | Priority level (1-4) |
| `due_date` / `due_time` | Due date/time |
| `completed` / `completed_at` | Completion state |

## Sync Behavior

### Create / Update
- Task labeled with `@capsync` → create/update in Capacities
- Ensure Project object exists and create relation
- Update all fields on every sync

### Complete
- Task completed in Todoist → set `completed=true` in Capacities
- Task remains visible (not archived)

### Delete / Untag
- Task deleted or `@capsync` removed → archive in Capacities
- Set `sync_status=archived`, `completed=true`

### Comments
- Full comment history synced as markdown
- Format: `**Author** · Timestamp\n\nContent`

## Development

### Run Tests
```bash
poetry run pytest
```

### Linting
```bash
poetry run ruff check .
poetry run mypy app
```

### Format Code
```bash
poetry run ruff format .
```

## Monitoring

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=todoist-capacities-sync" --limit 50
```

### Check Pub/Sub Queue
```bash
gcloud pubsub subscriptions describe todoist-sync-worker
```

## Troubleshooting

### Webhook not triggering
- Check Todoist webhook configuration
- Verify Cloud Run URL is publicly accessible
- Check Cloud Run logs for errors

### Tasks not syncing
- Ensure task has `@capsync` label
- Check Pub/Sub subscription for backlog
- Review Firestore for task state
- Check Capacities API rate limits

### Reconciliation issues
- Verify Cloud Scheduler job is enabled
- Check `INTERNAL_CRON_TOKEN` matches in Secret Manager
- Review reconcile endpoint logs

## API Endpoints

### `POST /todoist/webhook`
Receives Todoist webhook events

### `POST /reconcile`
Manually trigger full reconciliation (requires auth token)

### `GET /health`
Health check endpoint

## License

MIT

## Support

For issues and questions, please create an issue in the GitHub repository.

