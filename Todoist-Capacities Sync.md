Here’s a single Markdown document you can keep in your repo or notes—complete, detailed, and restart-proof.

---

# **Todoist → Capacities Sync (Full Specification)**

Version: **v1.0 (October 2025\)**  
 Author: *Pete Woodhouse \+ ChatGPT (GPT-5)*  
 Purpose: synchronize Todoist tasks into Capacities for richer knowledge linking and archival.

---

## **1\. Overview**

### **Goal**

Automatically mirror selected Todoist tasks into Capacities as `@ToDo` objects.  
 Todoist remains the entry point; Capacities receives a one-way feed for context and archival.

### **Scope**

* Direction: **Todoist → Capacities**

* Gateway: Todoist label `@capsync`

* Hosting: Google Cloud Run (FastAPI service)

* Trigger: Todoist webhooks \+ hourly reconcile

* Storage: Firestore (state) \+ Secret Manager (secrets) \+ Pub/Sub (events)

---

## **2\. Data Model**

### **2.1 Capacities `@ToDo` Fields**

| Field | Type | Source / Notes |
| ----- | ----- | ----- |
| `title` | string | Todoist `content` |
| `body` | rich text | description \+ comments markdown |
| `todoist_task_id` | string (unique) | primary key |
| `todoist_url` | url | link to Todoist task |
| `todoist_project_id` | string | project ID |
| `todoist_project_name` | string | project name |
| `project` | relation → Project | Capacities relation |
| `todoist_labels` | list of strings | all labels (preserve `@`) |
| `priority` | int (1–4) | raw value |
| `due_date` / `due_time` / `due_timezone` | date / time / string | from Todoist `due` |
| `completed` / `completed_at` | bool / datetime | completion state |
| `parent_id` | string | Todoist parent |
| `section_id` / `section_name` | string | from Todoist section |
| `comments_markdown` | rich text | full history (snapshot) |
| `created_at` / `updated_at` | datetime | as provided |
| `last_synced_at` | datetime | service-side |
| `sync_status` | enum (ok | archived | error) | local state |
| `error_note` | text | last failure message |

### **2.2 Capacities `Project` Fields**

| Field | Type | Notes |
| ----- | ----- | ----- |
| `todoist_project_id` | string (unique) | lookup key |
| `name` | string | project name |
| `url` | url | Todoist project link |
| `is_shared` | bool | shared flag |
| `color` | string | Todoist color code |
| `last_synced_at` | datetime | service timestamp |

---

## **3\. Sync Rules**

### **Create / Tag Add**

* When a Todoist task is created or labeled `@capsync`, create/update Capacities `@ToDo`.

* Ensure Project object exists and relate.

### **Update**

* Reflect changes to title, description, due, labels, project, section, priority, comments.

### **Complete**

* When completed in Todoist → `completed=true`, `completed_at` set, remain visible.

### **Un-tag / Delete**

* If `@capsync` removed or task deleted → archive Capacities object (`sync_status=archived`, `completed=true`).

### **Comments**

* Rebuild `comments_markdown` each sync as full transcript (`author · timestamp · content`).

### **De-duplication**

* Store Todoist `task_id` in Capacities.

* Idempotent writes by payload hash.

---

## **4\. Event Flow**

1. **Todoist Webhook → Cloud Run**

   * Events: `item:added | updated | completed | deleted | note:*`

   * Body parsed; enqueue Pub/Sub job (UPSERT or ARCHIVE).

2. **Pub/Sub → Worker**

   * Fetch full task via Todoist API.

   * Gate on `@capsync`.

   * Upsert Project then Task in Capacities.

   * Persist `payload_hash` \+ Capacities ID in Firestore.

3. **Cloud Scheduler → Reconcile Hourly**

   * List Todoist tasks with label `@capsync`.

   * Upsert each; archive any missing.

---

## **5\. Cloud Architecture**

| Component | Purpose |
| ----- | ----- |
| **Cloud Run (FastAPI)** | webhook receiver \+ reconcile endpoint |
| **Pub/Sub** | decouple webhook from processing |
| **Firestore** | store task/project mapping \+ hashes |
| **Secret Manager** | store API keys and cron token |
| **Cloud Scheduler** | trigger hourly reconcile |
| **Cloud Logging** | structured JSON logs |

**Service Permissions**

* roles/secretmanager.secretAccessor

* roles/datastore.user

* roles/pubsub.publisher / subscriber

---

## **6\. Environment Variables**

GCP\_PROJECT\_ID=your-project  
FIRESTORE\_NAMESPACE=todoist-capacities-v1  
DEFAULT\_TIMEZONE=America/Los\_Angeles  
PUBSUB\_TOPIC=todoist-sync-jobs  
PUBSUB\_SUBSCRIPTION=todoist-sync-worker  
LOG\_LEVEL=INFO

---

## **7\. Secrets (Secret Manager)**

| Secret ID | Purpose |
| ----- | ----- |
| `TODOIST_OAUTH_TOKEN` | Todoist API access |
| `CAPACITIES_API_KEY` | Capacities REST key |
| `INTERNAL_CRON_TOKEN` | protects `/reconcile` endpoint |

---

## **8\. Acceptance Tests**

1. Create Todoist task with `@capsync` → Capacities `@ToDo` appears \<5 s.

2. Edit title/due or move project → Capacities updates accordingly.

3. Add comments → markdown section updates.

4. Complete task → `completed=true`.

5. Remove `@capsync` → archived \+ completed.

6. Miss webhook → reconcile repairs drift.

---

## **9\. Security and Compliance**

* All secrets in Secret Manager.

* Webhook signature verification optional for v1.

* Logs contain no PII beyond Todoist IDs and titles.

* Replays idempotent via hash.

---

## **10\. Cursor Prompt (Scaffold Command)**

Copy this directly into Cursor when starting fresh:

Create a new Python 3.11 project named "todoist-capacities-sync" using Poetry.  
Add dependencies: fastapi, uvicorn\[standard\], google-cloud-firestore, google-cloud-secret-manager,  
google-cloud-pubsub, httpx, pydantic, python-dotenv, orjson, tenacity.  
Add dev deps: pytest, pytest-asyncio, ruff, mypy, types-requests.

Scaffold this repo structure:

/app  
  main.py  
  handlers.py  
  mapper.py  
  models.py  
  todoist\_client.py  
  capacities\_client.py  
  store.py  
  logging\_setup.py  
  settings.py  
  pubsub\_worker.py  
  utils.py  
/tests  
  test\_mapper.py  
infra/terraform/  
  main.tf  
  variables.tf  
  outputs.tf  
  cloud\_run.tf  
  pubsub.tf  
  scheduler.tf  
  firestore.tf  
  secrets.tf  
scripts/  
  run\_local.sh  
  seed\_secrets.sh  
  sample\_webhook.json  
pyproject.toml  
.env.example  
README.md

Constraints:  
\- Use FastAPI with ORJSONResponse.  
\- Use httpx.AsyncClient for outbound calls.  
\- Implement idempotency via content-hash in Firestore.  
\- Map fields exactly per spec (see @ToDo and Project schemas).  
\- Pub/Sub message shape: { "action": "UPSERT|ARCHIVE", "todoist\_task\_id": "...", "snapshot" ?: {...} }.  
\- Production-grade type hints and structure; ready for Cloud Run deploy.

---

## **11\. Deployment Checklist**

| Step | Command / Action |
| ----- | ----- |
| Install Poetry | `curl -sSL https://install.python-poetry.org | python3 -` |
| Install deps | `poetry install` |
| Run locally | `./scripts/run_local.sh` |
| Enable GCP APIs | Cloud Run, Pub/Sub, Firestore, Secret Manager, Scheduler |
| Create secrets | `gcloud secrets create ...` then `secrets versions add` |
| Build image | `gcloud builds submit --tag us-central1-docker.pkg.dev/<PROJECT>/default/todoist-capacities-sync:v1 .` |
| Deploy Terraform | `cd infra/terraform && terraform apply -var="project_id=<PROJECT>" -var="image=..."` |
| Add Todoist webhook | point to `https://<cloud-run-url>/todoist/webhook` |
| Trigger test task | create Todoist `@capsync` task → check Capacities object appears |
| Review logs | Logs Explorer → Cloud Run service |

---

## **12\. Future Work (v1.1+)**

* **Two-way sync** (edit title/due back to Todoist)

* **Subtask nesting** via `parent_id`

* **Attachment mirror**

* **Comment diff sync instead of snapshot**

* **Fine-grained error metrics**

* **Configurable archive policy**

---

### **Summary**

This spec defines a single-direction, event-driven synchronization pipeline between Todoist and Capacities, deployable entirely on Google Cloud. It uses modern, typed Python (FastAPI \+ async HTTPX), isolates secrets securely, and ensures idempotent writes through payload hashing.

Re-running the Cursor prompt above will rebuild the same scaffold from scratch; drop in the code files from earlier sections, commit incrementally, and follow the deployment checklist.

