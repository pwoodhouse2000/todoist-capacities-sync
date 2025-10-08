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
    app.state.store = FirestoreStore()
    app.state.pubsub_publisher = pubsub_v1.PublisherClient()

    # Initialize handlers
    app.state.webhook_handler = WebhookHandler(app.state.pubsub_publisher)
    app.state.reconcile_handler = ReconcileHandler(
        app.state.todoist_client,
        app.state.capacities_client,
        app.state.store,
    )

    logger.info("Application started successfully")

    yield

    # Cleanup
    logger.info("Shutting down application")
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
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Todoist-Capacities Sync",
        "version": "1.0.0",
        "status": "running",
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

