# Todoist → Notion Sync

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]() [![Python](https://img.shields.io/badge/python-3.9%2B-blue)]() [![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A production-grade synchronization service that automatically mirrors Todoist tasks labeled with `@capsync` into Notion database pages with full metadata, comments, and project relations.

## 🎯 Overview

This service provides **one-way synchronization** from Todoist to Notion, enabling powerful knowledge management in Notion while maintaining Todoist as your primary task entry point.

### Key Features

- 🔄 **Real-time sync** via Todoist webhooks (when deployed)
- ⏰ **Hourly reconciliation** to catch missed events
- 🎯 **Label-based filtering** using `capsync` label
- 🔗 **Automatic project relations** in Notion databases
- 💬 **Comment synchronization** as page content
- 🔒 **Secure** secret management via GCP Secret Manager
- 📊 **Observable** with structured logging
- ⚡ **Idempotent** writes via content hashing
- ✅ **Smart updates** - only syncs when content changes
- 🧪 **Fully tested** with unit, integration, and E2E tests

### What Gets Synced

✅ Task title, description, and priority  
✅ Due dates and time  
✅ Labels (multi-select in Notion)  
✅ Completion status  
✅ All comments (formatted as markdown)  
✅ Project relations (automatic)  
✅ Task hierarchy information

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
2. Set up two Notion databases (Tasks and Projects)
3. Get your API key and database IDs

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
# Todoist API
TODOIST_OAUTH_TOKEN=your_todoist_token_here

# Notion API
NOTION_API_KEY=your_notion_integration_key_here
NOTION_TASKS_DATABASE_ID=your_tasks_database_id_here
NOTION_PROJECTS_DATABASE_ID=your_projects_database_id_here

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
| [NOTION_SETUP.md](NOTION_SETUP.md) | Complete Notion setup guide with screenshots |
| [CODE_REVIEW.md](CODE_REVIEW.md) | Security audit and code quality review |
| [DEPLOYMENT.md](DEPLOYMENT.md) | GCP deployment guide |
| [API.md](API.md) | API endpoint documentation |

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
| `GCP_PROJECT_ID` | Production | Google Cloud project ID |
| `INTERNAL_CRON_TOKEN` | Production | Secure token for reconcile endpoint |
| `FIRESTORE_NAMESPACE` | Optional | Firestore collection prefix |
| `LOG_LEVEL` | Optional | Logging level (default: INFO) |

### Notion Database Schema

#### Tasks Database Properties

| Property | Type | Required |
|----------|------|----------|
| Name | Title | ✅ |
| Todoist Task ID | Text | ✅ |
| Todoist URL | URL | ✅ |
| Priority | Select (P1-P4) | ✅ |
| Labels | Multi-select | ✅ |
| Due Date | Date | Optional |
| Completed | Checkbox | ✅ |
| Project | Relation (→ Projects) | Optional |

#### Projects Database Properties

| Property | Type | Required |
|----------|------|----------|
| Name | Title | ✅ |
| Todoist Project ID | Text | ✅ |
| Todoist URL | URL | ✅ |
| Color | Select | Optional |
| Is Shared | Checkbox | Optional |

## 🐛 Troubleshooting

### Common Issues

**"Labels is not a property that exists"**
- Solution: Add "Labels" as Multi-select property in Tasks database

**"No tasks with @capsync label found"**
- Verify label is spelled correctly (case-sensitive)
- Check that label is saved in Todoist
- Try: `curl "http://localhost:8000/test/todoist?capsync_only=true"`

**"Notion API error: Invalid database ID"**
- Verify database IDs are correct (32 hex characters)
- Ensure databases are shared with your integration
- Check `.env` file has no extra quotes or spaces

**"Service not starting"**
- Check Python version: `python3 --version` (need 3.9+)
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check logs: `tail -f /tmp/uvicorn.log`

See [NOTION_SETUP.md](NOTION_SETUP.md) for more troubleshooting tips.

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

### Task Lifecycle

1. **Create**: Task gets `capsync` label → Synced to Notion
2. **Update**: Task changes in Todoist → Updated in Notion
3. **Complete**: Task marked done → Checkbox updated in Notion
4. **Archive**: Label removed or task deleted → Page archived in Notion

### Idempotency

The service uses content hashing to avoid unnecessary updates:
- Computes SHA-256 hash of task content
- Compares with last synced hash in Firestore
- Only updates Notion if content changed

### Reconciliation

Hourly reconciliation ensures consistency:
- Fetches all tasks with `capsync` label
- Syncs any new or changed tasks
- Archives tasks without label
- Reports sync statistics

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
