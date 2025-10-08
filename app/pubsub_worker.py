"""Pub/Sub worker for processing sync jobs."""

from datetime import datetime
from typing import Optional

from app.capacities_client import CapacitiesClient
from app.logging_setup import get_logger
from app.mapper import create_archived_todo, map_project_to_capacities, map_task_to_todo
from app.models import PubSubMessage, SyncAction, SyncStatus, TaskSyncState
from app.store import FirestoreStore
from app.todoist_client import TodoistClient
from app.utils import compute_payload_hash, has_capsync_label

logger = get_logger(__name__)


class SyncWorker:
    """Process sync jobs from Pub/Sub messages."""

    def __init__(
        self,
        todoist_client: TodoistClient,
        capacities_client: CapacitiesClient,
        store: FirestoreStore,
    ) -> None:
        """
        Initialize sync worker.

        Args:
            todoist_client: Todoist API client
            capacities_client: Capacities API client
            store: Firestore store for state management
        """
        self.todoist = todoist_client
        self.capacities = capacities_client
        self.store = store

    async def process_message(self, message: PubSubMessage) -> None:
        """
        Process a single Pub/Sub sync message.

        Args:
            message: PubSubMessage with sync instructions
        """
        logger.info(
            "Processing sync message",
            extra={
                "action": message.action,
                "task_id": message.todoist_task_id,
            },
        )

        try:
            if message.action == SyncAction.UPSERT:
                await self._handle_upsert(message)
            elif message.action == SyncAction.ARCHIVE:
                await self._handle_archive(message)
            else:
                logger.warning("Unknown sync action", extra={"action": message.action})

        except Exception as e:
            logger.error(
                "Error processing sync message",
                extra={
                    "task_id": message.todoist_task_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            await self.store.mark_task_error(message.todoist_task_id, str(e))

    async def _handle_upsert(self, message: PubSubMessage) -> None:
        """
        Handle UPSERT action: create or update task in Capacities.

        Args:
            message: PubSubMessage with task data
        """
        task_id = message.todoist_task_id

        # Fetch full task data from Todoist (or use snapshot if provided)
        if message.snapshot:
            logger.info("Using task snapshot from message")
            # TODO: Parse snapshot into TodoistTask model
            task = await self.todoist.get_task(task_id)
        else:
            task = await self.todoist.get_task(task_id)

        # Gate: Check if task has @capsync label
        if not has_capsync_label(task.labels):
            logger.info(
                "Task does not have @capsync label, skipping",
                extra={"task_id": task_id},
            )
            # If it previously existed, archive it
            existing_state = await self.store.get_task_state(task_id)
            if existing_state:
                await self._handle_archive(message)
            return

        # Fetch related data
        project = await self.todoist.get_project(task.project_id)
        comments = await self.todoist.get_comments(task_id)

        # Get section name if task is in a section
        section_name: Optional[str] = None
        if task.section_id:
            section = await self.todoist.get_section(task.section_id)
            section_name = section.name

        # Map to Capacities models
        todo = map_task_to_todo(task, project, comments, section_name)
        capacities_project = map_project_to_capacities(project)

        # Compute payload hash for idempotency
        payload_hash = compute_payload_hash(todo.model_dump())

        # Check existing state
        existing_state = await self.store.get_task_state(task_id)

        # Skip if unchanged (idempotency check)
        if existing_state and existing_state.payload_hash == payload_hash:
            logger.info(
                "Task unchanged, skipping sync",
                extra={"task_id": task_id, "hash": payload_hash},
            )
            return

        # Ensure project exists in Capacities
        project_capacities_id = await self._ensure_project_exists(capacities_project)

        # Set project relation
        todo.project_relation_id = project_capacities_id

        # Upsert task in Capacities
        capacities_object_id = existing_state.capacities_object_id if existing_state else None
        result = await self.capacities.upsert_todo(todo, capacities_object_id)

        # Extract Capacities object ID from result
        if not capacities_object_id:
            capacities_object_id = result.get("id") or result.get("objectId")

        # Update sync state
        new_state = TaskSyncState(
            todoist_task_id=task_id,
            capacities_object_id=capacities_object_id,
            payload_hash=payload_hash,
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
        )
        await self.store.save_task_state(new_state)

        logger.info(
            "Successfully synced task to Capacities",
            extra={
                "task_id": task_id,
                "capacities_id": capacities_object_id,
            },
        )

    async def _handle_archive(self, message: PubSubMessage) -> None:
        """
        Handle ARCHIVE action: mark task as archived in Capacities.

        Args:
            message: PubSubMessage with task ID
        """
        task_id = message.todoist_task_id

        # Get existing state
        existing_state = await self.store.get_task_state(task_id)
        if not existing_state or not existing_state.capacities_object_id:
            logger.info(
                "Task not found in sync state, nothing to archive",
                extra={"task_id": task_id},
            )
            return

        # Fetch task from Todoist to get current data
        try:
            task = await self.todoist.get_task(task_id)
            project = await self.todoist.get_project(task.project_id)
        except Exception as e:
            logger.warning(
                "Could not fetch task for archiving, may be deleted",
                extra={"task_id": task_id, "error": str(e)},
            )
            # Mark as archived in our state
            await self.store.mark_task_archived(task_id, "Task deleted in Todoist")
            return

        # Create archived version
        archived_todo = create_archived_todo(task, project)

        # Update in Capacities
        await self.capacities.upsert_todo(archived_todo, existing_state.capacities_object_id)

        # Update sync state
        await self.store.mark_task_archived(task_id)

        logger.info(
            "Successfully archived task in Capacities",
            extra={"task_id": task_id},
        )

    async def _ensure_project_exists(self, project: "CapacitiesProject") -> Optional[str]:
        """
        Ensure project exists in Capacities, create if needed.

        Args:
            project: CapacitiesProject model

        Returns:
            Capacities project object ID
        """
        project_id = project.todoist_project_id

        # Check if we already have it synced
        existing_state = await self.store.get_project_state(project_id)
        if existing_state and existing_state.capacities_object_id:
            return existing_state.capacities_object_id

        # Try to find it in Capacities
        # TODO: Search for project by todoist_project_id property

        # Create new project
        result = await self.capacities.upsert_project(project)
        capacities_object_id = result.get("id") or result.get("objectId")

        # Save state
        from app.models import ProjectSyncState

        state = ProjectSyncState(
            todoist_project_id=project_id,
            capacities_object_id=capacities_object_id,
            payload_hash=compute_payload_hash(project.model_dump()),
            last_synced_at=datetime.now(),
        )
        await self.store.save_project_state(state)

        logger.info(
            "Created project in Capacities",
            extra={
                "project_id": project_id,
                "capacities_id": capacities_object_id,
            },
        )

        return capacities_object_id

