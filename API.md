# 📡 API Documentation

**Service**: Todoist → Notion Sync  
**Version**: 1.0.0  
**Base URL**: `http://localhost:8000` (local) or your Cloud Run URL (production)

## 🔍 Overview

The service exposes several REST endpoints for health checks, testing, and webhook processing. All endpoints return JSON responses.

## 📋 Endpoints

### Health & Status

#### `GET /`

Service status and configuration information.

**Response**:
```json
{
  "service": "Todoist-Notion Sync",
  "version": "1.0.0",
  "status": "running",
  "mode": "local_dev",  // or "production"
  "gcp_clients": {
    "firestore": true,
    "pubsub": true
  }
}
```

**Status Codes**:
- `200 OK`: Service is running

---

#### `GET /health`

Simple health check endpoint.

**Response**:
```json
{
  "status": "healthy"
}
```

**Status Codes**:
- `200 OK`: Service is healthy

---

### Testing Endpoints (Local Development)

#### `GET /test/todoist`

Test Todoist API connection and retrieve tasks.

**Query Parameters**:
- `show_tasks` (boolean, optional): Include task list in response
- `capsync_only` (boolean, optional): Show only tasks with `capsync` label

**Examples**:
```bash
# Basic test
curl "http://localhost:8000/test/todoist"

# Show all tasks
curl "http://localhost:8000/test/todoist?show_tasks=true"

# Show only tasks with capsync label
curl "http://localhost:8000/test/todoist?capsync_only=true"
```

**Success Response** (200 OK):
```json
{
  "status": "success",
  "message": "Todoist API connected successfully",
  "project_count": 74,
  "projects": [
    {
      "id": "2005983004",
      "name": "Inbox"
    }
  ],
  "tasks": [
    {
      "id": "9625006790",
      "content": "Test sync to Notion",
      "labels": ["capsync"],
      "project_id": "2005983004"
    }
  ],
  "capsync_task_count": 4
}
```

**Error Response** (500):
```json
{
  "status": "error",
  "message": "Todoist API error: <error details>"
}
```

---

#### `GET /test/notion`

Test Notion API connection and database access.

**Example**:
```bash
curl "http://localhost:8000/test/notion"
```

**Success Response** (200 OK):
```json
{
  "status": "success",
  "message": "Notion API connected successfully",
  "databases": {
    "tasks": {
      "id": "28789c4a21dd801bac9afec0722348a0",
      "accessible": true,
      "pages_found": 5
    },
    "projects": {
      "id": "28789c4a21dd80db9edcfe4ffb342bfb",
      "accessible": true,
      "pages_found": 3
    }
  }
}
```

**Error Response** (500):
```json
{
  "status": "error",
  "message": "Notion API error: <error details>",
  "error_type": "APIResponseError"
}
```

---

#### `GET /test/sync-task/{task_id}`

Test syncing a specific Todoist task to Notion.

**Path Parameters**:
- `task_id` (string, required): Todoist task ID (numeric string)

**Query Parameters**:
- `dry_run` (boolean, default: `true`): If true, only simulate the sync. If false, actually create/update in Notion.

**Examples**:
```bash
# Dry run (simulation only)
curl "http://localhost:8000/test/sync-task/9625006790?dry_run=true"

# Actually sync to Notion
curl "http://localhost:8000/test/sync-task/9625006790?dry_run=false"
```

**Success Response - Dry Run** (200 OK):
```json
{
  "status": "success",
  "message": "Task sync simulation complete (dry run)",
  "todoist_task": {
    "id": "9625006790",
    "content": "Test sync to Notion",
    "project": "Inbox",
    "labels": ["capsync"]
  },
  "would_create_in_notion": {
    "project_page": {
      "name": "Inbox",
      "todoist_project_id": "2005983004",
      "url": "https://todoist.com/app/project/2005983004",
      "color": "grey"
    },
    "todo_page": {
      "title": "Test sync to Notion",
      "body_preview": "",
      "project_name": "Inbox",
      "labels": ["capsync"],
      "priority": "P4",
      "due_date": null,
      "comments_count": 0
    }
  },
  "note": "Add ?dry_run=false to actually create these pages in Notion"
}
```

**Success Response - Actual Sync** (200 OK):
```json
{
  "status": "success",
  "message": "Successfully synced to Notion!",
  "todoist_task": {
    "id": "9625006790",
    "content": "Test sync to Notion",
    "project": "Inbox"
  },
  "notion_results": {
    "project": {
      "status": "already_exists",  // or "created"
      "page_id": "28889c4a-21dd-814c-babb-c123fb36bd47"
    },
    "todo": {
      "status": "created",  // or "updated"
      "page_id": "28889c4a-21dd-8179-bbef-cc12e5c1e145"
    }
  },
  "notion_links": {
    "project_page": "https://notion.so/28889c4a21dd814cbabbc123fb36bd47",
    "todo_page": "https://notion.so/28889c4a21dd8179bbefcc12e5c1e145"
  }
}
```

**Error Response - No Label** (200 OK):
```json
{
  "status": "skipped",
  "message": "Task 'Buy new sailing gloves' does not have @capsync label",
  "task_id": "9288763765",
  "labels": ["FUN 📁"],
  "note": "Add the @capsync label to this task in Todoist to sync it"
}
```

**Error Response - Sync Failure** (200 OK):
```json
{
  "status": "error",
  "message": "Failed to create in Notion: <error details>",
  "error_type": "APIResponseError",
  "note": "Check the logs for detailed error. Verify your Notion database IDs and permissions."
}
```

---

### Production Endpoints

#### `POST /todoist/webhook`

Receives webhook events from Todoist.

**Headers**:
- `Content-Type: application/json`

**Request Body**:
```json
{
  "event_name": "item:added",  // or item:updated, item:completed, item:deleted, note:added
  "event_data": {
    "id": "9625006790",
    "content": "New task",
    "labels": ["capsync"],
    "project_id": "2005983004"
  },
  "user_id": "2415995",
  "version": "9"
}
```

**Success Response** (200 OK):
```json
{
  "status": "received",
  "message": "Event queued for processing",
  "event": "item:added",
  "task_id": "9625006790"
}
```

**Local Dev Response** (200 OK):
```json
{
  "status": "received_local_dev",
  "message": "Running in local dev mode without Pub/Sub. Deploy to GCP for full functionality.",
  "event": "item:added"
}
```

**Notes**:
- Webhook must be configured in Todoist settings
- Events are queued to Pub/Sub for asynchronous processing
- No authentication required (Todoist webhooks don't support signatures)

---

#### `POST /reconcile`

Manually trigger full reconciliation of all tasks with `capsync` label.

**Headers**:
- `Authorization: Bearer <INTERNAL_CRON_TOKEN>` (required)

**Example**:
```bash
curl -X POST "https://your-service.run.app/reconcile" \
  -H "Authorization: Bearer your-secure-token"
```

**Success Response** (200 OK):
```json
{
  "status": "success",
  "message": "Reconciliation completed",
  "summary": {
    "active_tasks_found": 15,
    "tasks_upserted": 3,
    "tasks_archived": 1,
    "errors": 0
  },
  "duration_seconds": 12.5
}
```

**Error Response - Unauthorized** (401):
```json
{
  "detail": "Invalid authorization token"
}
```

**Local Dev Response** (200 OK):
```json
{
  "status": "local_dev_mode",
  "message": "Running in local dev mode without Firestore. Deploy to GCP for reconciliation."
}
```

**Notes**:
- Requires secure token for authentication
- Typically triggered by Cloud Scheduler hourly
- Can be manually triggered for testing or recovery

---

## 🔐 Authentication

### Test Endpoints
- **No authentication required** (local development only)
- Should not be exposed in production

### Webhook Endpoint
- **No authentication** (Todoist doesn't support webhook signatures)
- Relies on URL obscurity and rate limiting
- Consider adding custom validation in production

### Reconcile Endpoint
- **Bearer token authentication** required
- Token stored in Secret Manager
- Token should be 32+ characters and cryptographically random

---

## 📊 Response Format

### Success Response Structure

All successful responses follow this pattern:
```json
{
  "status": "success",
  "message": "<human-readable message>",
  "<data_key>": {
    // Response data
  }
}
```

### Error Response Structure

Error responses include details for debugging:
```json
{
  "status": "error",
  "message": "<error description>",
  "error_type": "<exception class name>",
  "note": "<troubleshooting hint>"
}
```

---

## 🔄 Webhook Event Types

### Supported Events

| Event Name | Triggers Sync | Action |
|------------|--------------|--------|
| `item:added` | Yes | Create/update task in Notion |
| `item:updated` | Yes | Update task in Notion |
| `item:completed` | Yes | Mark task as completed in Notion |
| `item:deleted` | Yes | Archive task in Notion |
| `item:uncompleted` | Yes | Mark task as incomplete in Notion |
| `note:added` | Yes | Update comments in Notion |
| `note:updated` | Yes | Update comments in Notion |

### Event Processing Flow

```
Todoist → Webhook → FastAPI → Pub/Sub → Worker
                                            │
                                            ├─> Fetch full task data
                                            ├─> Check for capsync label
                                            ├─> Map to Notion format
                                            ├─> Create/update in Notion
                                            └─> Update Firestore state
```

---

## 🧪 Testing

### Local Testing

```bash
# 1. Start service
./run_simple.sh

# 2. Test all endpoints
./test_apis.sh

# 3. Test specific task sync
TASK_ID=$(curl -s "http://localhost:8000/test/todoist?capsync_only=true" | \
  jq -r '.tasks[0].id')
curl "http://localhost:8000/test/sync-task/$TASK_ID?dry_run=false"
```

### Production Testing

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe todoist-notion-sync \
  --region=us-central1 \
  --format='value(status.url)')

# Test health
curl "$SERVICE_URL/health"

# Trigger reconciliation
curl -X POST "$SERVICE_URL/reconcile" \
  -H "Authorization: Bearer $CRON_TOKEN"

# Watch logs
gcloud run services logs tail todoist-notion-sync --region=us-central1
```

---

## ⚡ Rate Limiting

### Current Limits

- **Todoist API**: 450 requests per 15 minutes
- **Notion API**: 3 requests per second per integration
- **Cloud Run**: 1000 concurrent requests (default)

### Mitigation Strategies

1. **Retry Logic**: Exponential backoff with tenacity
2. **Queuing**: Pub/Sub decouples webhook receipt from processing
3. **Idempotency**: Content hashing prevents unnecessary API calls
4. **Batching**: Reconciliation processes tasks efficiently

---

## 🐛 Error Codes

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request processed successfully |
| 400 | Bad Request | Invalid request format |
| 401 | Unauthorized | Missing or invalid auth token |
| 404 | Not Found | Task or resource doesn't exist |
| 500 | Server Error | Internal service error |

### Application Error Types

| Error Type | Description | Resolution |
|------------|-------------|------------|
| `APIResponseError` | Notion API error | Check database permissions and property names |
| `HTTPStatusError` | Todoist API error | Verify task exists and token is valid |
| `ValidationError` | Invalid data format | Check data models and API responses |
| `RetryError` | Max retries exceeded | Check network and API status |

---

## 📚 Examples

### Complete Workflow Example

```bash
#!/bin/bash

# 1. Check service health
curl http://localhost:8000/health

# 2. Verify API connections
curl http://localhost:8000/test/todoist
curl http://localhost:8000/test/notion

# 3. Find tasks with capsync label
curl "http://localhost:8000/test/todoist?capsync_only=true" > tasks.json
cat tasks.json | jq '.tasks[].id'

# 4. Test sync (dry run first)
TASK_ID="9625006790"
curl "http://localhost:8000/test/sync-task/$TASK_ID?dry_run=true" | jq

# 5. Actually sync
curl "http://localhost:8000/test/sync-task/$TASK_ID?dry_run=false" | jq

# 6. Verify in Notion
# Check the returned notion_links URLs
```

### Webhook Simulation

```bash
# Simulate Todoist webhook
curl -X POST http://localhost:8000/todoist/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "item:added",
    "event_data": {
      "id": "9625006790",
      "content": "New task",
      "labels": ["capsync"],
      "project_id": "2005983004"
    },
    "user_id": "2415995",
    "version": "9"
  }'
```

---

## 📖 Related Documentation

- [NOTION_SETUP.md](NOTION_SETUP.md) - Notion configuration guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - GCP deployment instructions
- [CODE_REVIEW.md](CODE_REVIEW.md) - Security and code quality
- [README.md](README.md) - Project overview

---

## 🆘 Support

**Issues**: [GitHub Issues](https://github.com/pwoodhouse2000/todoist-capacities-sync/issues)  
**Email**: See profile for contact information

---

**Last Updated**: October 2025

