"""FastAPI application entry point."""

import hmac
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import ORJSONResponse
from google.cloud import pubsub_v1

from app.handlers import ReconcileHandler, WebhookHandler
from app.logging_setup import get_logger, setup_logging
from app.models import TodoistWebhookEvent
from app.notion_client import NotionClient
from app.settings import settings
from app.store import FirestoreStore
from app.todoist_client import TodoistClient

# Setup logging
setup_logging()
logger = get_logger(__name__)


# Application state
class AppState:
    """Global application state."""

    todoist_client: TodoistClient
    notion_client: NotionClient
    store: FirestoreStore
    webhook_handler: WebhookHandler
    reconcile_handler: ReconcileHandler
    pubsub_publisher: pubsub_v1.PublisherClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Initializes clients on startup and cleans up on shutdown.
    """
    logger.info("Starting application")

    # Initialize clients
    app.state.todoist_client = TodoistClient()
    app.state.notion_client = NotionClient()
    
    # Initialize GCP clients (optional for local dev)
    try:
        app.state.store = FirestoreStore()
        app.state.pubsub_publisher = pubsub_v1.PublisherClient()
        logger.info("GCP clients initialized successfully")
    except Exception as e:
        logger.warning(f"GCP clients not available (running in local dev mode): {e}")
        app.state.store = None
        app.state.pubsub_publisher = None

    # Initialize handlers
    if app.state.pubsub_publisher:
        app.state.webhook_handler = WebhookHandler(app.state.pubsub_publisher)
    else:
        app.state.webhook_handler = None
        
    app.state.reconcile_handler = ReconcileHandler(
        app.state.todoist_client,
        app.state.notion_client,
        app.state.store,
    )

    logger.info("Application started successfully")

    yield

    # Cleanup
    logger.info("Shutting down application")
    await app.state.todoist_client.close()
    if app.state.store:
        await app.state.store.close()


# Create FastAPI app
app = FastAPI(
    title="Todoist-Capacities Sync",
    description="Synchronize Todoist tasks to Capacities",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


def _verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    """
    Verify Todoist webhook HMAC-SHA256 signature.

    Args:
        body: Raw request body bytes
        signature_header: Value of X-Todoist-Hmac-SHA256 header

    Returns:
        True if signature is valid
    """
    import base64
    import hashlib

    if not settings.todoist_client_secret:
        # No client secret configured - skip verification (dev mode)
        logger.debug("Webhook HMAC verification skipped (no client secret configured)")
        return True

    if not signature_header:
        logger.warning("Webhook missing X-Todoist-Hmac-SHA256 header")
        return False

    expected = base64.b64encode(
        hmac.new(
            settings.todoist_client_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    is_valid = hmac.compare_digest(expected, signature_header)
    if not is_valid:
        logger.warning("Webhook HMAC signature mismatch")

    return is_valid


async def _verify_oidc_token(token: str, request: Request) -> bool:
    """
    Verify a Google OIDC token from Cloud Scheduler.

    Validates the token signature against Google's public keys and checks
    the audience claim matches this service's URL.

    Args:
        token: The raw JWT string (without "Bearer " prefix)
        request: FastAPI request (used to determine expected audience)

    Returns:
        True if token is valid
    """
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        # The audience should be the Cloud Run service URL
        # Cloud Scheduler sets this to the target URL
        expected_audience = str(request.base_url).rstrip("/")

        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=expected_audience,
        )

        logger.debug(
            "OIDC token verified",
            extra={"email": claims.get("email"), "audience": claims.get("aud")},
        )
        return True

    except ImportError:
        logger.warning(
            "google-auth not installed, cannot verify OIDC tokens. "
            "Rejecting OIDC request. Install google-auth or use internal_cron_token."
        )
        return False
    except Exception as e:
        logger.warning("OIDC token verification failed", extra={"error": str(e)})
        return False


@app.post("/todoist/webhook")
async def todoist_webhook(request: Request) -> Dict[str, Any]:
    """
    Receive Todoist webhook events with HMAC signature verification.

    Args:
        request: FastAPI request object

    Returns:
        Response dictionary
    """
    # Read raw body for HMAC verification
    body = await request.body()

    # Verify HMAC signature
    signature = request.headers.get("X-Todoist-Hmac-SHA256", "")
    if not _verify_webhook_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Check if running in local dev mode (no Pub/Sub)
    if not request.app.state.webhook_handler:
        logger.info("Received webhook in local dev mode (Pub/Sub not available)")
        import orjson
        payload = orjson.loads(body)
        return {
            "status": "received_local_dev",
            "message": "Running in local dev mode without Pub/Sub. Deploy to GCP for full functionality.",
            "event": payload.get("event_name", "unknown"),
        }

    try:
        # Parse webhook payload from raw body
        import orjson
        payload = orjson.loads(body)
        event = TodoistWebhookEvent(**payload)

        # Handle event
        result = await request.app.state.webhook_handler.handle_event(event)

        return result

    except Exception as e:
        logger.error("Error processing webhook", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing webhook",
        )


@app.post("/pubsub/process")
async def process_pubsub(request: Request) -> Dict[str, Any]:
    """
    Process Pub/Sub push messages.
    
    This endpoint receives messages from Pub/Sub push subscription
    and processes the sync jobs.
    
    Args:
        request: FastAPI request object containing Pub/Sub message
        
    Returns:
        Processing status
    """
    # Check if running in production with GCP clients
    if not request.app.state.store:
        return {
            "status": "local_dev_mode",
            "message": "Running in local dev mode without Firestore.",
        }
    
    try:
        import base64
        import json
        from app.pubsub_worker import SyncWorker
        from app.models import PubSubMessage
        
        # Parse Pub/Sub message
        body = await request.json()
        if "message" not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Pub/Sub message format",
            )
        
        # Decode message data
        message_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
        message_json = json.loads(message_data)
        
        logger.info(
            "Received Pub/Sub message",
            extra={"message": message_json},
        )
        
        # Parse into PubSubMessage model
        pubsub_message = PubSubMessage(**message_json)
        
        # Create worker and process
        worker = SyncWorker(
            todoist_client=request.app.state.todoist_client,
            notion_client=request.app.state.notion_client,
            store=request.app.state.store,
        )
        
        await worker.process_message(pubsub_message)
        
        return {
            "status": "success",
            "task_id": pubsub_message.todoist_task_id,
            "action": pubsub_message.action,
        }
        
    except HTTPException:
        raise  # Re-raise 400 for malformed messages (no retry needed)
    except Exception as e:
        logger.error("Error processing Pub/Sub message", exc_info=True)
        # Return 500 so Pub/Sub push subscription retries the message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process sync message",
        )


@app.get("/test/reconcile")
async def test_reconcile(request: Request) -> Dict[str, Any]:
    """
    Test reconcile endpoint that doesn't require authorization (for manual testing).
    
    Returns:
        Reconciliation summary or error details
    """
    try:
        # Check if running in local dev mode (no Firestore)
        if not request.app.state.store:
            return {
                "status": "local_dev_mode",
                "message": "Running in local dev mode without Firestore. Deploy to GCP for reconciliation.",
            }
        
        # Run reconciliation
        summary = await request.app.state.reconcile_handler.reconcile()
        return summary
        
    except Exception as e:
        logger.error("Error during test reconciliation", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }


@app.post("/reconcile")
async def reconcile(
    request: Request,
    authorization: str = Header(None),
) -> Dict[str, Any]:
    """
    Trigger manual reconciliation of all @capsync tasks.

    Requires authorization token in header.

    Args:
        request: FastAPI request object
        authorization: Authorization header

    Returns:
        Reconciliation summary
    """
    # Check if running in local dev mode (no Firestore)
    if not request.app.state.store:
        return {
            "status": "local_dev_mode",
            "message": "Running in local dev mode without Firestore. Deploy to GCP for reconciliation.",
        }
    
    # Verify authorization token
    # Accept either:
    # 1. Bearer token with internal cron token
    # 2. OIDC token from Cloud Scheduler (verified against Google's public keys)
    is_valid = False

    if authorization:
        if authorization.startswith("Bearer eyJ"):
            # OIDC token from Cloud Scheduler — verify signature and claims
            is_valid = await _verify_oidc_token(authorization[7:], request)
            if is_valid:
                logger.info("Reconciliation triggered via verified Cloud Scheduler OIDC token")
        else:
            # Check for Bearer token with internal cron token
            expected_token = f"Bearer {settings.internal_cron_token}"
            if hmac.compare_digest(authorization, expected_token):
                is_valid = True
                logger.info("Reconciliation triggered via internal cron token")

    if not is_valid:
        logger.warning(
            "Unauthorized reconcile attempt",
            extra={"auth_header": authorization[:20] if authorization else None},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    try:
        # Run reconciliation
        summary = await request.app.state.reconcile_handler.reconcile()
        return summary

    except Exception as e:
        logger.error("Error during reconciliation", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during reconciliation",
        )


@app.get("/")
async def root(request: Request) -> Dict[str, Any]:
    """Root endpoint."""
    gcp_available = request.app.state.store is not None and request.app.state.pubsub_publisher is not None
    return {
        "service": "Todoist-Notion Sync",
        "version": "1.0.0",
        "status": "running",
        "mode": "production" if gcp_available else "local_dev",
        "gcp_clients": {
            "firestore": request.app.state.store is not None,
            "pubsub": request.app.state.pubsub_publisher is not None,
        },
    }


@app.get("/test/todoist")
async def test_todoist(request: Request, show_tasks: bool = False, capsync_only: bool = False) -> Dict[str, Any]:
    """Test Todoist API connection."""
    try:
        projects = await request.app.state.todoist_client.get_projects()
        result = {
            "status": "success",
            "message": "Todoist API connected successfully",
            "project_count": len(projects),
            "projects": [{"id": p.id, "name": p.name} for p in projects[:5]],  # First 5
        }
        
        # Optionally show tasks
        if show_tasks or capsync_only:
            if capsync_only:
                # Get only tasks with @capsync label
                tasks = await request.app.state.todoist_client.get_active_tasks_with_label("@capsync")
                result["message"] = "Found tasks with @capsync label"
                result["capsync_task_count"] = len(tasks)
            else:
                # Get all tasks
                tasks = await request.app.state.todoist_client.get_tasks()
                result["task_count"] = len(tasks)
            
            result["tasks"] = [
                {
                    "id": t.id,
                    "content": t.content,
                    "labels": t.labels,
                    "project_id": t.project_id,
                }
                for t in tasks[:20]  # Show up to 20 tasks
            ]
            
            if capsync_only and len(tasks) == 0:
                result["note"] = "No tasks with @capsync label found. Add the label to a task in Todoist!"
            elif not capsync_only:
                result["note"] = "Use ?capsync_only=true to see only tasks with @capsync label"
        
        return result
    except Exception as e:
        logger.error("Error testing Todoist API", exc_info=True)
        return {
            "status": "error",
            "message": f"Todoist API error: {str(e)}",
        }


@app.get("/test/notion")
async def test_notion(request: Request) -> Dict[str, Any]:
    """Test Notion API connection and database access."""
    try:
        # Try to query both databases to verify access
        tasks_result = await request.app.state.notion_client.client.databases.query(
            database_id=settings.notion_tasks_database_id,
            page_size=1,
        )
        projects_result = await request.app.state.notion_client.client.databases.query(
            database_id=settings.notion_projects_database_id,
            page_size=1,
        )
        
        return {
            "status": "success",
            "message": "Notion API connected successfully",
            "databases": {
                "tasks": {
                    "id": settings.notion_tasks_database_id,
                    "accessible": True,
                    "pages_found": len(tasks_result.get("results", [])),
                },
                "projects": {
                    "id": settings.notion_projects_database_id,
                    "accessible": True,
                    "pages_found": len(projects_result.get("results", [])),
                },
            },
        }
    except Exception as e:
        logger.error("Error testing Notion API", exc_info=True)
        return {
            "status": "error",
            "message": f"Notion API error: {str(e)}",
            "error_type": type(e).__name__,
        }


@app.get("/test/sync-task/{task_id}")
async def test_sync_task(task_id: str, request: Request, dry_run: bool = True) -> Dict[str, Any]:
    """
    Test syncing a single task to Notion (demonstrates the full workflow).
    
    This demonstrates:
    1. Fetching task from Todoist
    2. Checking if it has @capsync label
    3. Auto-creating project in Notion if needed
    4. Creating ToDo page in Notion
    
    Args:
        task_id: Todoist task ID to sync
        dry_run: If True, only simulate. If False, actually create in Notion.
    """
    # Validate task_id format (v1 API uses alphanumeric IDs)
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task ID cannot be empty.",
        )

    try:
        from app.mapper import map_project_to_notion, map_task_to_todo
        from app.utils import has_capsync_label
        
        # 1. Fetch task from Todoist
        logger.info(f"Fetching task {task_id} from Todoist")
        task = await request.app.state.todoist_client.get_task(task_id)
        
        # 2. Check for @capsync label
        if not has_capsync_label(task.labels):
            return {
                "status": "skipped",
                "message": f"Task '{task.content}' does not have @capsync label",
                "task_id": task_id,
                "labels": task.labels,
                "note": "Add the @capsync label to this task in Todoist to sync it",
            }
        
        # 3. Fetch related data
        project = await request.app.state.todoist_client.get_project(task.project_id)
        comments = await request.app.state.todoist_client.get_comments(task_id)
        
        # Get section name if exists
        section_name = None
        if task.section_id:
            section = await request.app.state.todoist_client.get_section(task.section_id)
            section_name = section.name
        
        # 4. Map to Notion models
        notion_project = map_project_to_notion(project)
        todo = map_task_to_todo(task, project, comments, section_name)
        
        # 5. Either simulate or actually create
        if dry_run:
            # Simulation mode - just show what would happen
            return {
                "status": "success",
                "message": "Task sync simulation complete (dry run)",
                "todoist_task": {
                    "id": task.id,
                    "content": task.content,
                    "project": project.name,
                    "labels": task.labels,
                },
                "would_create_in_notion": {
                    "project_page": {
                        "name": notion_project.name,
                        "todoist_project_id": notion_project.todoist_project_id,
                        "url": notion_project.url,
                        "color": notion_project.color,
                    },
                    "todo_page": {
                        "title": todo.title,
                        "body_preview": todo.body[:100] + "..." if len(todo.body) > 100 else todo.body,
                        "project_name": todo.todoist_project_name,
                        "labels": todo.todoist_labels,
                        "priority": f"P{todo.priority}",
                        "due_date": todo.due_date,
                        "comments_count": len(comments),
                    },
                },
                "note": "Add ?dry_run=false to actually create these pages in Notion",
            }
        else:
            # Actually create in Notion
            logger.info(f"Actually creating Notion pages for task {task_id}")
            
            try:
                # 1. Check if project page already exists
                existing_project = await request.app.state.notion_client.find_project_by_todoist_id(
                    project.id
                )
                
                if existing_project:
                    logger.info(f"Project page already exists: {existing_project['id']}")
                    project_page_id = existing_project["id"]
                    project_result = {"status": "already_exists", "page_id": project_page_id}
                else:
                    # Create new project page
                    logger.info(f"Creating new project page for: {project.name}")
                    project_page = await request.app.state.notion_client.create_project_page(notion_project)
                    project_page_id = project_page["id"]
                    project_result = {"status": "created", "page_id": project_page_id}
                
                # 2. Check if todo page already exists
                existing_todo = await request.app.state.notion_client.find_todo_by_todoist_id(task.id)
                
                if existing_todo:
                    logger.info(f"Todo page already exists: {existing_todo['id']}, updating it")
                    todo_page = await request.app.state.notion_client.update_todo_page(
                        existing_todo["id"], todo
                    )
                    todo_result = {"status": "updated", "page_id": todo_page["id"]}
                else:
                    # Create new todo page
                    logger.info(f"Creating new todo page: {todo.title}")
                    todo_page = await request.app.state.notion_client.create_todo_page(
                        todo, project_page_id
                    )
                    todo_result = {"status": "created", "page_id": todo_page["id"]}
                
                return {
                    "status": "success",
                    "message": "Successfully synced to Notion!",
                    "todoist_task": {
                        "id": task.id,
                        "content": task.content,
                        "project": project.name,
                    },
                    "notion_results": {
                        "project": project_result,
                        "todo": todo_result,
                    },
                    "notion_links": {
                        "project_page": f"https://notion.so/{project_page_id.replace('-', '')}",
                        "todo_page": f"https://notion.so/{todo_result['page_id'].replace('-', '')}",
                    },
                }
            except Exception as create_error:
                logger.error(f"Error creating in Notion: {create_error}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Failed to create in Notion: {str(create_error)}",
                    "error_type": type(create_error).__name__,
                    "note": "Check the logs for detailed error. Verify your Notion database IDs and permissions.",
                }
        
    except Exception as e:
        logger.error(f"Error testing sync for task {task_id}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
        }


@app.post("/migrate/v1-ids")
async def migrate_v1_ids(request: Request, dry_run: bool = True) -> Dict[str, Any]:
    """
    One-time migration: Update Notion pages and Firestore with new v1 Todoist IDs.

    Args:
        dry_run: If True, only report what would change. If False, execute migration.
    """
    if not request.app.state.store:
        return {"status": "error", "message": "Firestore not available"}

    try:
        from app.migration import run_v1_id_migration

        return await run_v1_id_migration(
            todoist=request.app.state.todoist_client,
            notion=request.app.state.notion_client,
            store=request.app.state.store,
            dry_run=dry_run,
        )
    except Exception as e:
        logger.error("Migration: FAILED", exc_info=True)
        return {"status": "error", "error": str(e), "error_type": type(e).__name__}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

