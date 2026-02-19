# CLAUDE.md

## Project Overview

Todoist-to-Notion sync service. Event-driven Python/FastAPI application that syncs Todoist tasks labeled `capsync` into Notion database pages. Runs on Google Cloud Platform (Cloud Run, Pub/Sub, Firestore, Secret Manager).

Key behavior: Todoist webhooks trigger Pub/Sub messages, which are processed by a sync worker that creates/updates Notion pages. A scheduled reconciliation job runs every 2 hours (5am–10pm Pacific) to catch missed events.

## Architecture

```
Todoist Webhook → POST /todoist/webhook → Pub/Sub Topic → POST /pubsub/process → SyncWorker
Cloud Scheduler → POST /reconcile → ReconcileHandler → (full sync of all capsync tasks)
State storage: Firestore (idempotent writes via content hashing)
```

### Module Responsibilities

| Module | Purpose |
|---|---|
| `app/main.py` | FastAPI app, all HTTP endpoints, lifespan management |
| `app/models.py` | Pydantic models for Todoist, Notion, sync state, Pub/Sub |
| `app/todoist_client.py` | Todoist REST API v1 client (httpx, async) |
| `app/notion_client.py` | Notion API client (SDK + direct HTTP for complex queries) |
| `app/mapper.py` | Todoist task/project → Notion page mapping |
| `app/reverse_mapper.py` | Notion → Todoist extraction, change detection, echo suppression |
| `app/handlers.py` | `WebhookHandler` (event → Pub/Sub) and `ReconcileHandler` (full sync) |
| `app/pubsub_worker.py` | `SyncWorker` processes UPSERT/ARCHIVE actions |
| `app/store.py` | Firestore async client for sync state persistence |
| `app/settings.py` | Pydantic `BaseSettings` configuration from env vars / `.env` |
| `app/utils.py` | Hashing, timestamps, label checks, URL builders, comment formatting |
| `app/logging_setup.py` | Structured JSON logging for GCP Cloud Logging |

## Tech Stack

- **Language**: Python 3.9+
- **Framework**: FastAPI with uvicorn
- **Package manager**: Poetry (dependencies in `pyproject.toml`)
- **Container**: Docker multi-stage build (Python 3.9-slim)
- **Cloud**: GCP — Cloud Run, Pub/Sub, Firestore, Secret Manager, Cloud Scheduler
- **Infrastructure**: Terraform (`infra/terraform/`)
- **HTTP client**: httpx (async)
- **Data validation**: Pydantic v2
- **Retry logic**: tenacity
- **JSON**: orjson (deterministic serialization for hashing)

## Common Commands

```bash
# Install dependencies
poetry install

# Run locally
poetry run uvicorn app.main:app --reload --port 8000
# Or use the convenience script:
./scripts/run_local.sh

# Run all tests
poetry run pytest

# Run tests by marker
poetry run pytest -m unit
poetry run pytest -m integration
poetry run pytest -m e2e

# Run a specific test file
poetry run pytest tests/test_mapper.py

# Lint
poetry run ruff check .

# Format
poetry run ruff format .

# Type check
poetry run mypy app

# Build Docker image
docker build -t todoist-sync .

# Deploy (builds, pushes, runs Terraform)
./scripts/deploy.sh
```

## Testing

- **Framework**: pytest with pytest-asyncio (async mode: `auto`)
- **Config**: `pytest.ini` — verbose output, branch coverage on `app/`, HTML report to `htmlcov/`
- **Markers**: `unit`, `integration`, `e2e`, `slow`, `requires_network`
- **Fixtures**: `tests/conftest.py` — sample Todoist tasks/projects/comments, sample Notion pages, mock API responses
- **Coverage**: Branch coverage enabled, target 80%+, HTML report at `htmlcov/index.html`

Test files:
- `tests/test_models.py` — Pydantic model validation
- `tests/test_mapper.py` — Task/project mapping logic
- `tests/test_todoist_client.py` — Todoist API client (mocked)
- `tests/test_notion_client.py` — Notion API client (mocked)
- `tests/test_utils.py` — Utility functions
- `tests/test_bidirectional_sync.py` — Bidirectional sync integration
- `tests/test_end_to_end.py` — Full workflow E2E

## Linting and Formatting

- **ruff**: line length 100, target Python 3.9, rules: `E, F, I, N, W, UP` (configured in `pyproject.toml`)
- **mypy**: strict mode — `disallow_untyped_defs`, `warn_return_any` (configured in `pyproject.toml`)

## Environment Variables

Required (set in `.env` for local dev, Secret Manager for production):

```
TODOIST_OAUTH_TOKEN       # Todoist API token
NOTION_API_KEY            # Notion integration token
NOTION_TASKS_DATABASE_ID  # Notion ToDo database ID (32-char hex)
NOTION_PROJECTS_DATABASE_ID  # Notion Projects database ID
```

Optional:

```
NOTION_AREAS_DATABASE_ID     # PARA areas database (enables area mapping)
NOTION_PEOPLE_DATABASE_ID    # People database (enables person matching)
INTERNAL_CRON_TOKEN          # Auth token for /reconcile endpoint
TODOIST_CLIENT_SECRET        # HMAC webhook verification secret
GCP_PROJECT_ID               # GCP project (default: notion-todoist-sync-464419)
FIRESTORE_NAMESPACE          # Firestore namespace (default: todoist-notion-v1)
DEFAULT_TIMEZONE             # Timezone (default: America/Los_Angeles)
PUBSUB_TOPIC                 # Pub/Sub topic name (default: todoist-sync-jobs)
LOG_LEVEL                    # Logging level (default: INFO)
```

Feature flags (all boolean, defaults in `app/settings.py`):

```
ADD_NOTION_BACKLINK=true          # Add Notion URL to Todoist task description
ENABLE_PARA_AREAS=true            # PARA method area mapping
ENABLE_PEOPLE_MATCHING=true       # Auto-match people from labels
AUTO_LABEL_TASKS=true             # Auto-add capsync to eligible tasks
ENABLE_NOTION_TO_TODOIST=true     # Bidirectional sync
ENABLE_NOTION_TASK_CREATION=true  # Create Todoist tasks from Notion
```

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | None | Service info and status |
| GET | `/health` | None | Health check |
| POST | `/todoist/webhook` | HMAC signature | Receive Todoist webhook events |
| POST | `/pubsub/process` | None (GCP IAM) | Process Pub/Sub sync messages |
| POST | `/reconcile` | Bearer token / OIDC | Trigger full reconciliation |
| GET | `/test/todoist` | None | Test Todoist API connectivity |
| GET | `/test/notion` | None | Test Notion API connectivity |
| GET | `/test/reconcile` | None | Manual reconciliation (no auth, for testing) |
| GET | `/test/sync-task/{task_id}` | None | Dry-run or live sync of a single task |
| POST | `/migrate/v1-ids` | None | One-time v2→v1 Todoist ID migration |

## Key Conventions

### Code Style
- All I/O functions are `async`
- All function parameters and returns have type hints
- Classes: `PascalCase`; functions: `snake_case`; constants: `UPPER_SNAKE_CASE`; private: `_prefix`
- Pydantic models use `ConfigDict(extra="ignore")` for forward compatibility
- Structured logging with `extra={}` dict for GCP Cloud Logging fields
- Logger per module: `logger = get_logger(__name__)`
- Dependency injection via constructor parameters (no global singletons for clients)

### Sync Logic
- Only tasks with `capsync` label are synced
- Inbox projects and recurring tasks are never synced
- Idempotent writes: content hashing via `compute_payload_hash()` in `app/utils.py`
- Echo suppression: `notion_payload_hash` in sync state prevents update loops
- PARA areas: tasks/projects mapped to life areas (HOME, HEALTH, WORK, etc.)
- Backlinks: Notion page URLs written back to Todoist task descriptions

### Retry Strategy
- API calls use `tenacity` with exponential backoff
- Configurable via `MAX_RETRIES` and `RETRY_DELAY` settings
- Pub/Sub subscription has its own retry policy (10s–600s backoff)

## Project Structure

```
├── app/                    # Application source code (13 Python modules)
├── tests/                  # pytest test suite (unit, integration, e2e)
├── infra/terraform/        # GCP infrastructure as code (8 .tf files)
├── scripts/                # Setup, run, deploy, seed scripts
├── Documentation/          # 30+ markdown docs (see root directory)
├── pyproject.toml          # Poetry dependencies and tool config
├── pytest.ini              # Test runner configuration
├── Dockerfile              # Multi-stage production container
├── requirements-test.txt   # Test-only pip dependencies
└── .env                    # Local environment variables (not committed)
```

## Infrastructure (Terraform)

Located in `infra/terraform/`. Key resources:

- **Cloud Run**: Auto-scaling container service (0–10 replicas, 512Mi RAM)
- **Pub/Sub**: Topic + push subscription with retry backoff
- **Cloud Scheduler**: Cron job `0 5-22/2 * * *` (every 2 hours, 5am–10pm Pacific)
- **Firestore**: Native mode database with indexes
- **Secret Manager**: Stores API tokens accessed by service account

Deploy with: `cd infra/terraform && terraform init && terraform apply`
