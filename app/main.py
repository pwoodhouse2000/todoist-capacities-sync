"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import ORJSONResponse
from google.cloud import pubsub_v1

from app.capacities_client import CapacitiesClient
from app.handlers import ReconcileHandler, WebhookHandler
from app.logging_setup import get_logger, setup_logging
from app.models import TodoistWebhookEvent
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
    capacities_client: CapacitiesClient
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
    app.state.capacities_client = CapacitiesClient()
    
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
        app.state.capacities_client,
        app.state.store,
    )

    logger.info("Application started successfully")

    yield

    # Cleanup
    logger.info("Shutting down application")
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


@app.post("/todoist/webhook")
async def todoist_webhook(request: Request) -> Dict[str, Any]:
    """
    Receive Todoist webhook events.

    Args:
        request: FastAPI request object

    Returns:
        Response dictionary
    """
    # Check if running in local dev mode (no Pub/Sub)
    if not request.app.state.webhook_handler:
        logger.info("Received webhook in local dev mode (Pub/Sub not available)")
        payload = await request.json()
        return {
            "status": "received_local_dev",
            "message": "Running in local dev mode without Pub/Sub. Deploy to GCP for full functionality.",
            "event": payload.get("event_name", "unknown"),
        }
    
    try:
        # Parse webhook payload
        payload = await request.json()
        event = TodoistWebhookEvent(**payload)

        # Handle event
        result = await request.app.state.webhook_handler.handle_event(event)

        return result

    except Exception as e:
        logger.error("Error processing webhook", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}",
        )


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
    expected_token = f"Bearer {settings.internal_cron_token}"
    if authorization != expected_token:
        logger.warning("Unauthorized reconcile attempt")
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
            detail=f"Error during reconciliation: {str(e)}",
        )


@app.get("/")
async def root(request: Request) -> Dict[str, Any]:
    """Root endpoint."""
    gcp_available = request.app.state.store is not None and request.app.state.pubsub_publisher is not None
    return {
        "service": "Todoist-Capacities Sync",
        "version": "1.0.0",
        "status": "running",
        "mode": "production" if gcp_available else "local_dev",
        "gcp_clients": {
            "firestore": request.app.state.store is not None,
            "pubsub": request.app.state.pubsub_publisher is not None,
        },
    }


@app.get("/test/todoist")
async def test_todoist(request: Request, show_tasks: bool = False) -> Dict[str, Any]:
    """Test Todoist API connection."""
    try:
        projects = await request.app.state.todoist_client.get_projects()
        result = {
            "status": "success",
            "message": "Todoist API connected successfully",
            "project_count": len(projects),
            "projects": [{"id": p.id, "name": p.name} for p in projects[:5]],  # First 5
        }
        
        # Optionally show recent tasks
        if show_tasks:
            tasks = await request.app.state.todoist_client.get_tasks()
            result["task_count"] = len(tasks)
            result["recent_tasks"] = [
                {
                    "id": t.id,
                    "content": t.content,
                    "labels": t.labels,
                    "project_id": t.project_id,
                }
                for t in tasks[:10]  # First 10 tasks
            ]
            result["note"] = "Use ?show_tasks=true to see tasks"
        
        return result
    except Exception as e:
        logger.error("Error testing Todoist API", exc_info=True)
        return {
            "status": "error",
            "message": f"Todoist API error: {str(e)}",
        }


@app.get("/test/capacities")
async def test_capacities(request: Request) -> Dict[str, Any]:
    """Test Capacities API connection."""
    try:
        space_info = await request.app.state.capacities_client.get_space_info()
        return {
            "status": "success",
            "message": "Capacities API connected successfully",
            "space_id": settings.capacities_space_id,
            "structures": list(space_info.keys()) if isinstance(space_info, dict) else "unknown",
        }
    except Exception as e:
        logger.error("Error testing Capacities API", exc_info=True)
        return {
            "status": "error",
            "message": f"Capacities API error: {str(e)}",
        }


@app.get("/test/sync-task/{task_id}")
async def test_sync_task(task_id: str, request: Request) -> Dict[str, Any]:
    """
    Test syncing a single task (simulates the full workflow).
    
    This demonstrates:
    1. Fetching task from Todoist
    2. Checking if it has @capsync label
    3. Auto-creating project in Capacities if needed
    4. Creating ToDo in Capacities
    
    Args:
        task_id: Todoist task ID to sync
    """
    try:
        from app.mapper import map_project_to_capacities, map_task_to_todo
        from app.utils import has_capsync_label
        
        # 1. Fetch task from Todoist
        logger.info(f"Fetching task {task_id} from Todoist")
        task = await request.app.state.todoist_client.get_task(task_id)
        
        # 2. Check for @capsync label
        if not has_capsync_label(task.labels):
            return {
                "status": "skipped",
                "message": f"Task '{task.content}' does not have @capsync label",
                "labels": task.labels,
            }
        
        # 3. Fetch related data
        project = await request.app.state.todoist_client.get_project(task.project_id)
        comments = await request.app.state.todoist_client.get_comments(task_id)
        
        # Get section name if exists
        section_name = None
        if task.section_id:
            section = await request.app.state.todoist_client.get_section(task.section_id)
            section_name = section.name
        
        # 4. Map to Capacities models
        capacities_project = map_project_to_capacities(project)
        todo = map_task_to_todo(task, project, comments, section_name)
        
        # 5. Show what would be created
        return {
            "status": "success",
            "message": "Task sync simulation complete",
            "todoist_task": {
                "id": task.id,
                "content": task.content,
                "project": project.name,
                "labels": task.labels,
            },
            "would_create_in_capacities": {
                "project": {
                    "name": capacities_project.name,
                    "todoist_project_id": capacities_project.todoist_project_id,
                    "url": capacities_project.url,
                },
                "todo": {
                    "title": todo.title,
                    "body": todo.body[:100] + "..." if len(todo.body) > 100 else todo.body,
                    "project_name": todo.todoist_project_name,
                    "labels": todo.todoist_labels,
                    "priority": todo.priority,
                    "comments_count": len(comments),
                },
            },
            "note": "In production with Firestore, this would actually create these objects in Capacities",
        }
        
    except Exception as e:
        logger.error(f"Error testing sync for task {task_id}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

