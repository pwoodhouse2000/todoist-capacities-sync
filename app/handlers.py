"""Request handlers for webhooks and reconciliation."""

from typing import Any, Dict, Optional, Union

from google.cloud import pubsub_v1

from app.notion_client import NotionClient
from app.logging_setup import get_logger
from app.models import PubSubMessage, SyncAction, TodoistWebhookEvent
from app.pubsub_worker import SyncWorker
from app.settings import settings
from app.store import FirestoreStore
from app.todoist_client import TodoistClient
from app.utils import has_capsync_label

logger = get_logger(__name__)


class WebhookHandler:
    """Handle incoming Todoist webhook events."""

    def __init__(self, pubsub_publisher: pubsub_v1.PublisherClient) -> None:
        """
        Initialize webhook handler.

        Args:
            pubsub_publisher: Pub/Sub publisher client
        """
        self.publisher = pubsub_publisher
        self.topic_path = self.publisher.topic_path(settings.gcp_project_id, settings.pubsub_topic)

    async def handle_event(self, event: TodoistWebhookEvent) -> Dict[str, str]:
        """
        Handle a Todoist webhook event.

        Args:
            event: Parsed webhook event

        Returns:
            Response dictionary
        """
        logger.info(
            "Received Todoist webhook",
            extra={
                "event_name": event.event_name,
                "user_id": event.user_id,
            },
        )

        # Extract task ID from event data
        task_id = event.event_data.get("id")
        if not task_id:
            logger.warning("No task ID in webhook event", extra={"event_data": event.event_data})
            return {"status": "ignored", "reason": "no_task_id"}

        # Determine action based on event type
        action = self._determine_action(event.event_name, event.event_data)

        if action is None:
            logger.info(
                "Ignoring webhook event",
                extra={"event_name": event.event_name},
            )
            return {"status": "ignored", "reason": "irrelevant_event"}

        # Create Pub/Sub message
        message = PubSubMessage(
            action=action,
            todoist_task_id=task_id,
            snapshot=event.event_data,  # Include snapshot to avoid immediate re-fetch
        )

        # Publish to Pub/Sub
        self._publish_message(message)

        logger.info(
            "Published sync job to Pub/Sub",
            extra={"task_id": task_id, "action": action},
        )

        return {"status": "queued", "task_id": task_id, "action": action.value}

    def _determine_action(self, event_name: str, event_data: Dict[str, Any]) -> Optional[SyncAction]:
        """
        Determine sync action based on webhook event.

        Args:
            event_name: Webhook event name
            event_data: Event data payload

        Returns:
            SyncAction or None if event should be ignored
        """
        # Events that trigger UPSERT
        if event_name in [
            "item:added",
            "item:updated",
            "item:completed",
            "item:uncompleted",
            "note:added",
            "note:updated",
        ]:
            return SyncAction.UPSERT

        # Events that trigger ARCHIVE
        if event_name in ["item:deleted"]:
            return SyncAction.ARCHIVE

        # Ignore other events
        return None

    def _publish_message(self, message: PubSubMessage) -> None:
        """
        Publish message to Pub/Sub.

        Args:
            message: PubSubMessage to publish
        """
        import orjson

        data = orjson.dumps(message.model_dump())
        future = self.publisher.publish(self.topic_path, data)

        # We could await the future, but for webhook responses we want to be fast
        # The future will complete asynchronously
        logger.debug("Published message to Pub/Sub", extra={"message_id": future.result()})


class ReconcileHandler:
    """Handle reconciliation jobs."""

    def __init__(
        self,
        todoist_client: TodoistClient,
        notion_client: NotionClient,
        store: FirestoreStore,
    ) -> None:
        """
        Initialize reconcile handler.

        Args:
            todoist_client: Todoist API client
            notion_client: Notion API client
            store: Firestore store
        """
        self.todoist = todoist_client
        self.notion = notion_client
        self.store = store
        self.worker = SyncWorker(todoist_client, notion_client, store)

    async def reconcile(self) -> Dict[str, Any]:
        """
        Perform full reconciliation of all @capsync tasks.

        Returns:
            Reconciliation summary
        """
        logger.info("Starting reconciliation")

        # Fetch all Todoist tasks with @capsync label
        active_tasks = await self.todoist.get_active_tasks_with_label("@capsync")
        active_task_ids = {task.id for task in active_tasks}

        logger.info(
            "Found active tasks with @capsync",
            extra={"count": len(active_tasks)},
        )

        # Fetch all stored sync states
        stored_states = await self.store.get_all_task_states()
        stored_task_ids = {state.todoist_task_id for state in stored_states}

        # Process active tasks (upsert)
        upserted = 0
        for task in active_tasks:
            try:
                message = PubSubMessage(
                    action=SyncAction.UPSERT,
                    todoist_task_id=task.id,
                )
                await self.worker.process_message(message)
                upserted += 1
            except Exception as e:
                logger.error(
                    "Error upserting task during reconcile",
                    extra={"task_id": task.id, "error": str(e)},
                )

        # Find tasks that need archiving (in store but not in active tasks)
        tasks_to_archive = stored_task_ids - active_task_ids
        archived = 0

        for task_id in tasks_to_archive:
            try:
                message = PubSubMessage(
                    action=SyncAction.ARCHIVE,
                    todoist_task_id=task_id,
                )
                await self.worker.process_message(message)
                archived += 1
            except Exception as e:
                logger.error(
                    "Error archiving task during reconcile",
                    extra={"task_id": task_id, "error": str(e)},
                )

        summary = {
            "status": "completed",
            "active_tasks": len(active_tasks),
            "upserted": upserted,
            "archived": archived,
            "total_stored": len(stored_states),
        }

        logger.info("Reconciliation completed", extra=summary)

        return summary

