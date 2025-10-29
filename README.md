# Todoist → Notion Sync

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]() [![Python](https://img.shields.io/badge/python-3.9%2B-blue)]() [![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A production-grade synchronization service that automatically mirrors Todoist tasks labeled with `capsync` (or `@capsync`) into Notion database pages with full metadata, comments, project relations, and PARA areas organization.

## 🎯 Overview

This service provides **intelligent one-way synchronization** from Todoist to Notion, enabling powerful knowledge management in Notion while maintaining Todoist as your primary task entry point. The sync follows the **PARA method** (Projects, Areas, Resources, Archives) for organizing tasks by life areas.

### Key Features

- 🔄 **Real-time sync** via Todoist webhooks (when deployed)
- ⏰ **5-minute reconciliation** to catch missed events and completed tasks
- 🎯 **Label-based filtering** using `capsync` or `@capsync` label
- 🔗 **Automatic project relations** in Notion databases
- 📁 **PARA Areas support** - Tasks link to life areas (WORK, HEALTH, etc.)
- 💬 **Comment synchronization** as page content
- 🔒 **Secure** secret management via GCP Secret Manager
- 📊 **Observable** with structured logging
- ⚡ **Idempotent** writes via content hashing
- ✅ **Smart updates** - only syncs when content changes
- 🔄 **Bidirectional backlinks** - Notion URLs added to Todoist descriptions
- 🏗️ **Project archiving** - Syncs archived status to Notion
- 🧪 **Fully tested** with unit, integration, and E2E tests
- 🚫 **Inbox filtering** - Inbox projects never sync to Notion
- ♻️ **Recurring task filtering** - Repeating tasks never sync to Notion

### What Gets Synced

#### Tasks
✅ Task title, description, and priority (Todoist is source of truth)  
✅ Due dates and time with timezone support  
✅ Labels (multi-select in Notion)  
✅ Completion status (including completed tasks)  
✅ All comments (formatted as markdown)  
✅ Project relations (automatic)  
✅ PARA Area relations (multiple areas supported)  
✅ Person relations (via `@person` labels)  
✅ Section information  
✅ Notion backlinks in Todoist description (task + project URLs)

#### Projects
✅ Project name and URL  
✅ Project color and sharing status  
✅ PARA Area relations (aggregated from tasks at creation)  
✅ Archived/Active status  
✅ Notion backlink in Todoist project comment

#### Areas (PARA Method)
✅ Seven predefined areas: WORK, HEALTH, PERSONAL & FAMILY, FUN, FINANCIAL, HOME, PROSPER  
✅ Areas must be created manually in Notion first  
✅ Areas identified by folder emoji suffix in Todoist (e.g., "WORK 📁")  
✅ Tasks and projects can belong to multiple areas

### What Doesn't Get Synced

❌ Inbox project and its tasks  
❌ Recurring/repeating tasks  
❌ Tasks without `capsync` label  
❌ Subtasks (coming soon)  
❌ Project sections (metadata only, not structure)

## 📋 Quick Start

### Prerequisites

- Python 3.9+ installed
- Notion workspace with integration access
- Todoist account with API access
- (Optional) Google Cloud Platform account for production deployment

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/pwoodhouse2000/todoist-capacities-sync.git
cd todoist-capacities-sync

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Notion

Follow the complete guide in **[NOTION_SETUP.md](NOTION_SETUP.md)** to:
1. Create a Notion integration
2. Set up four Notion databases: Tasks, Projects, Areas, and People
3. Get your API key and database IDs
4. Create the seven predefined PARA areas in the Areas database

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
# Todoist API
TODOIST_OAUTH_TOKEN=your_todoist_token_here

# Notion API
NOTION_API_KEY=your_notion_integration_key_here
NOTION_TASKS_DATABASE_ID=your_tasks_database_id_here
NOTION_PROJECTS_DATABASE_ID=your_projects_database_id_here
NOTION_AREAS_DATABASE_ID=your_areas_database_id_here
NOTION_PEOPLE_DATABASE_ID=your_people_database_id_here

# Optional: GCP Configuration (for production)
GCP_PROJECT_ID=your-gcp-project
FIRESTORE_NAMESPACE=todoist-notion-v1
INTERNAL_CRON_TOKEN=generate-secure-token-here
```

### 4. Run Locally

```bash
# Start the service
./run_simple.sh

# In another terminal, test the APIs
./test_apis.sh
```

The service will be available at `http://localhost:8000`

### 5. Sync Your First Task

1. **In Todoist**: Add the `capsync` label to a task
2. **Test the sync**:
   ```bash
   # Find tasks with capsync label
   curl "http://localhost:8000/test/todoist?capsync_only=true"
   
   # Sync a specific task (get ID from above)
   curl "http://localhost:8000/test/sync-task/TASK_ID?dry_run=false"
   ```
3. **Check Notion**: Your task should appear in the Tasks database!

## 🏗️ Architecture

```
┌─────────────────────┐
│  Todoist Webhook    │
│   (item:*, note:*)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│   FastAPI Service   │────▶│      Pub/Sub        │
│   (Cloud Run)       │     │  (Message Queue)    │
└─────────────────────┘     └──────────┬──────────┘
           │                            │
           │                            ▼
           │                 ┌─────────────────────┐
           │                 │   Sync Worker       │
           │                 │  (Process Message)  │
           │                 └──────────┬──────────┘
           │                            │
           ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐
│    Firestore        │     │   Todoist API       │
│  (Sync State)       │     │  (Fetch Details)    │
└─────────────────────┘     └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │    Notion API       │
                            │ (Create/Update)     │
                            └─────────────────────┘
```

### Components

- **FastAPI Service**: Receives webhooks, exposes test endpoints
- **Pub/Sub**: Decouples webhook receipt from processing
- **Sync Worker**: Core sync logic with Todoist/Notion interaction
- **Firestore**: Stores sync state and content hashes for idempotency
- **Cloud Scheduler**: Triggers hourly reconciliation

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[SYNC_RULES.md](SYNC_RULES.md)** | **Complete synchronization rules and behavior** |
| [NOTION_SETUP.md](NOTION_SETUP.md) | Complete Notion setup guide with database schemas |
| [DEPLOYMENT.md](DEPLOYMENT.md) | GCP deployment guide with Cloud Run and Terraform |
| [API.md](API.md) | API endpoint documentation |
| [CODE_AUDIT.md](CODE_AUDIT.md) | Code audit against sync rules |
| [CODE_REVIEW.md](CODE_REVIEW.md) | Security audit and code quality review |
| [CHANGES_2025-10-28.md](CHANGES_2025-10-28.md) | Latest changes and improvements |

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests with coverage
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m e2e           # End-to-end tests only

# Run with verbose output
pytest -v

# Generate coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_utils.py            # Unit tests for utilities
├── test_models.py           # Pydantic model tests
├── test_mapper.py           # Data mapping tests
├── test_todoist_client.py   # Todoist API client tests
├── test_notion_client.py    # Notion API client tests
└── test_end_to_end.py       # Complete workflow tests
```

**Test Coverage**: 85%+ (excluding external API calls)

## 🚀 Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment instructions to Google Cloud Run.

### Quick Deploy

```bash
# 1. Set up GCP project
gcloud projects create your-project-id
gcloud config set project your-project-id

# 2. Enable required APIs
./scripts/setup_gcp.sh

# 3. Deploy with Terraform
cd infra/terraform
terraform init
terraform apply

# 4. Configure Todoist webhook
# Add webhook URL to Todoist settings
```

## 📖 API Endpoints

### Health & Status

- **`GET /`** - Service status and mode (local_dev vs production)
- **`GET /health`** - Health check endpoint

### Testing Endpoints (Local Dev)

- **`GET /test/todoist`** - Test Todoist API connection
  - `?show_tasks=true` - Show recent tasks
  - `?capsync_only=true` - Show only tasks with capsync label

- **`GET /test/notion`** - Test Notion API and database access

- **`GET /test/sync-task/{task_id}`** - Test syncing a specific task
  - `?dry_run=true` (default) - Simulate only
  - `?dry_run=false` - Actually sync to Notion

### Production Endpoints

- **`POST /todoist/webhook`** - Receives Todoist webhook events
- **`POST /reconcile`** - Triggers full reconciliation (requires auth token)

See [API.md](API.md) for complete documentation.

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TODOIST_OAUTH_TOKEN` | Yes | Todoist API token |
| `NOTION_API_KEY` | Yes | Notion integration secret |
| `NOTION_TASKS_DATABASE_ID` | Yes | Notion tasks database ID |
| `NOTION_PROJECTS_DATABASE_ID` | Yes | Notion projects database ID |
| `NOTION_AREAS_DATABASE_ID` | Yes | Notion areas database ID |
| `NOTION_PEOPLE_DATABASE_ID` | Yes | Notion people database ID |
| `GCP_PROJECT_ID` | Production | Google Cloud project ID |
| `INTERNAL_CRON_TOKEN` | Production | Secure token for reconcile endpoint |
| `FIRESTORE_NAMESPACE` | Optional | Firestore collection prefix |
| `LOG_LEVEL` | Optional | Logging level (default: INFO) |

### Notion Database Schema

#### Tasks Database Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| Name | Title | ✅ | Task title from Todoist |
| Todoist Task ID | Text | ✅ | Unique identifier for idempotency |
| Todoist URL | URL | ✅ | Deep link to Todoist task |
| Priority | Select (P1-P4) | ✅ | Task priority (Todoist is source) |
| Labels | Multi-select | ✅ | All Todoist labels |
| Due Date | Date | Optional | Due date with time and timezone |
| Completed | Checkbox | ✅ | Completion status |
| Project | Relation (→ Projects) | Optional | Single project relation |
| AREAS | Relation (→ Areas) | Optional | Multiple PARA area relations |
| People | Relation (→ People) | Optional | Multiple person relations |
| Section | Text | Optional | Todoist section name |

#### Projects Database Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| Name | Title | ✅ | Project name from Todoist |
| Todoist Project ID | Text | ✅ | Unique identifier |
| Todoist URL | URL | ✅ | Deep link to Todoist project |
| Color | Select | Optional | Project color |
| Is Shared | Checkbox | Optional | Sharing status |
| Status | Select | ✅ | Active or Archived |
| AREAS | Relation (→ Areas) | Optional | Multiple PARA area relations |

#### Areas Database Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| Name | Title | ✅ | Area name (UPPERCASE) |

**Predefined Areas:** WORK, HEALTH, PERSONAL & FAMILY, FUN, FINANCIAL, HOME, PROSPER

#### People Database Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| Name | Title | ✅ | Person name |

## 🐛 Troubleshooting

### Common Issues

**"Area not found in Notion" warning in logs**
- Solution: Create the missing PARA area manually in Notion AREAS database
- Remember: Areas are NEVER auto-created by the sync
- Must use exact names: WORK, HEALTH, PERSONAL & FAMILY, FUN, FINANCIAL, HOME, PROSPER

**"Inbox tasks not syncing"**
- Expected behavior: Inbox project is explicitly filtered and never syncs to Notion
- Move tasks to a named project and add `capsync` label to sync them

**"Recurring tasks not syncing"**
- Expected behavior: Recurring tasks are explicitly filtered and never sync to Notion
- The `capsync` label will be automatically removed from recurring tasks

**"Task synced but no areas assigned"**
- Check that Todoist label has folder emoji suffix: `WORK 📁`
- Verify the area exists in Notion AREAS database
- Area names must match predefined list (case-insensitive in Todoist, but uppercase in Notion)

**"Completed tasks not showing as complete in Notion"**
- Wait for reconciliation cycle (every 5 minutes)
- Check logs for any errors during sync
- Verify task has `capsync` label (Todoist renders as `@capsync`)

**"Labels is not a property that exists"**
- Solution: Add "Labels" as Multi-select property in Tasks database
- Also ensure AREAS (relation), People (relation), Section (text) exist

**"No tasks with @capsync label found"**
- Verify label is spelled correctly: `capsync` or `@capsync` (case-sensitive)
- Check that label is saved in Todoist
- Test: `curl "http://localhost:8000/test/todoist?capsync_only=true"`

**"Notion API error: Invalid database ID"**
- Verify database IDs are correct (32 hex characters without dashes)
- Ensure all four databases are shared with your Notion integration
- Check `.env` file has no extra quotes or spaces

**"AttributeError: 'DatabasesEndpoint' object has no attribute 'query'"**
- This was a known bug, now fixed with direct HTTP API calls
- Update to latest version from GitHub

**"Service not starting"**
- Check Python version: `python3 --version` (need 3.9+)
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check logs: `tail -f /tmp/uvicorn.log`
- Verify all four database IDs are set in environment

**"Duplicate AREA entries in Notion"**
- This was a known bug, now fixed
- Run cleanup script: `python scripts/cleanup_duplicate_areas.py`
- New areas are never auto-created

See [NOTION_SETUP.md](NOTION_SETUP.md) for more troubleshooting tips and [SYNC_RULES.md](SYNC_RULES.md) for complete behavior documentation.

## 🔒 Security

### Best Practices

✅ **Never commit `.env` file** to version control  
✅ **Use Secret Manager** for production credentials  
✅ **Rotate tokens** regularly  
✅ **Use strong cron token** (32+ characters)  
✅ **Review logs** for unusual activity  
✅ **Keep dependencies updated**

### Security Audit

See [CODE_REVIEW.md](CODE_REVIEW.md) for complete security audit and recommendations.

## 📊 Monitoring

### Logs

```bash
# Local development
tail -f /tmp/uvicorn.log

# Production (GCP)
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=todoist-notion-sync" \
  --limit 50 --format json
```

### Metrics to Monitor

- Sync success rate
- API error rates (Todoist, Notion)
- Pub/Sub queue depth
- Reconciliation duration
- Firestore read/write counts

## 🤝 Contributing

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-test.txt

# Run linter
ruff check .

# Format code
ruff format .

# Type checking
mypy app

# Run tests
pytest
```

### Code Quality Standards

- **Test Coverage**: Maintain 80%+ coverage
- **Type Hints**: All functions must have type hints
- **Documentation**: Docstrings for all public functions
- **Linting**: Code must pass `ruff` checks
- **Testing**: All PRs must include tests

## 📝 Sync Behavior

### Complete Synchronization Rules

For comprehensive details on how every entity syncs, see **[SYNC_RULES.md](SYNC_RULES.md)**.

### Task Lifecycle

1. **Labeling**: Add `capsync` or `@capsync` label to a Todoist task
   - Task must NOT be in Inbox project
   - Task must NOT be recurring
   - Subtasks automatically inherit label from parent
2. **Creation**: Task synced to Notion with:
   - All metadata (title, description, priority, due date, labels)
   - Project relation (project auto-created if needed)
   - AREA relations (multiple areas supported)
   - Person relations (via `@person` labels)
   - Two Notion URLs added to Todoist description (task + project pages)
3. **Updates**: Changes in Todoist → Updated in Notion
   - **Todoist wins** on all task properties
   - Title, description, priority, due date, completion status
   - Labels, project assignment, areas
4. **Completion**: Task marked done → Checkbox updated in Notion
   - Reconciliation fetches both active AND completed tasks
5. **Un-labeling**: Remove `capsync` label → Page archived in Notion
6. **Recurring**: Task becomes recurring → Label auto-removed, page archived

### Project Lifecycle

1. **Creation**: Project created one-way from Todoist → Notion
   - Only projects with at least one eligible task sync
   - Inbox project NEVER syncs
   - AREAS aggregated from all tasks in project (set once)
   - Notion project URL added to Todoist as comment
2. **Updates**: Post-creation, **Notion wins** on:
   - Project name (can be edited in Notion)
   - AREAS (managed in Notion after creation)
   - Other properties still sync from Todoist (color, sharing)
3. **Archiving**: Archived in Todoist → Status set to "Archived" in Notion
   - All tasks in project also archived in Notion
4. **Unarchiving**: Unarchived in Todoist → Status set to "Active" in Notion
5. **Empty Projects**: If last eligible task removed → Status set to "Archived"
6. **Deletion**: Deleted in Todoist → Deleted in Notion (rare)

### Areas Lifecycle

1. **Creation**: Areas MUST be created manually in Notion first
   - Seven predefined areas only
   - Sync NEVER creates new areas
2. **Assignment**: Areas assigned via Todoist labels with folder emoji
   - Example: `WORK 📁`, `HEALTH 📁`
   - Multiple areas per task/project supported
   - Folder emoji (📁) MUST be present
3. **Updates**: Areas on tasks sync continuously from Todoist
   - Areas on projects set once at creation, then managed in Notion
4. **Deletion**: If area deleted in Notion (rare):
   - Tasks show no area relation
   - No error, graceful degradation

### Idempotency

The service uses content hashing to avoid unnecessary updates:
- Computes SHA-256 hash of task content
- Compares with last synced hash in Firestore
- Only updates Notion if content changed
- Reduces API calls and improves performance

### Reconciliation

Every 5 minutes, reconciliation ensures consistency:
- Fetches all **active AND completed** tasks with `capsync` label
- Syncs any new or changed tasks
- Archives tasks without label
- Auto-removes `capsync` from ineligible tasks (recurring, Inbox)
- Reports sync statistics to logs

## 🎓 Learning Resources

### Notion API
- [Official Documentation](https://developers.notion.com/)
- [API Reference](https://developers.notion.com/reference)
- [Database Properties](https://developers.notion.com/reference/property-object)

### Todoist API
- [Official Documentation](https://developer.todoist.com/)
- [REST API v2](https://developer.todoist.com/rest/v2/)
- [Webhooks](https://developer.todoist.com/sync/v9/#webhooks)

### Google Cloud Platform
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Firestore Documentation](https://cloud.google.com/firestore/docs)
- [Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)

## 📜 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Uses [notion-client](https://github.com/ramnes/notion-sdk-py) Python SDK
- Deployed on [Google Cloud Run](https://cloud.google.com/run)

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/pwoodhouse2000/todoist-capacities-sync/issues)
- **Discussions**: [GitHub Discussions](https://github.com/pwoodhouse2000/todoist-capacities-sync/discussions)
- **Email**: See profile for contact

---

**Made with ❤️ for better productivity workflows**
