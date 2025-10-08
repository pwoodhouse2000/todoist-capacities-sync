"""Firestore operations for storing sync state."""

from datetime import datetime
from typing import List, Optional

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from app.logging_setup import get_logger
from app.models import ProjectSyncState, SyncStatus, TaskSyncState
from app.settings import settings

logger = get_logger(__name__)


class FirestoreStore:
    """Async Firestore client for sync state management."""

    def __init__(self, project_id: Optional[str] = None, namespace: Optional[str] = None) -> None:
        """
        Initialize Firestore client.

        Args:
            project_id: GCP project ID (defaults to settings)
            namespace: Firestore namespace/collection prefix (defaults to settings)
        """
        self.project_id = project_id or settings.gcp_project_id
        self.namespace = namespace or settings.firestore_namespace
        self.client: Optional[AsyncClient] = None

    async def _get_client(self) -> AsyncClient:
        """Get or create async Firestore client."""
        if self.client is None:
            self.client = firestore.AsyncClient(project=self.project_id)
        return self.client

    def _task_collection_ref(self) -> str:
        """Get task collection reference."""
        return f"{self.namespace}_tasks"

    def _project_collection_ref(self) -> str:
        """Get project collection reference."""
        return f"{self.namespace}_projects"

    async def get_task_state(self, todoist_task_id: str) -> Optional[TaskSyncState]:
        """
        Retrieve task sync state from Firestore.

        Args:
            todoist_task_id: Todoist task ID

        Returns:
            TaskSyncState if found, None otherwise
        """
        logger.info("Getting task state", extra={"task_id": todoist_task_id})

        client = await self._get_client()
        doc_ref = client.collection(self._task_collection_ref()).document(todoist_task_id)
        doc = await doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            return TaskSyncState(**data)

        return None

    async def save_task_state(self, state: TaskSyncState) -> None:
        """
        Save task sync state to Firestore.

        Args:
            state: TaskSyncState to save
        """
        logger.info("Saving task state", extra={"task_id": state.todoist_task_id})

        client = await self._get_client()
        doc_ref = client.collection(self._task_collection_ref()).document(state.todoist_task_id)

        # Convert to dict
        data = state.model_dump()
        data["last_synced_at"] = state.last_synced_at  # Keep datetime object

        await doc_ref.set(data)

    async def delete_task_state(self, todoist_task_id: str) -> None:
        """
        Delete task sync state from Firestore.

        Args:
            todoist_task_id: Todoist task ID
        """
        logger.info("Deleting task state", extra={"task_id": todoist_task_id})

        client = await self._get_client()
        doc_ref = client.collection(self._task_collection_ref()).document(todoist_task_id)
        await doc_ref.delete()

    async def get_project_state(self, todoist_project_id: str) -> Optional[ProjectSyncState]:
        """
        Retrieve project sync state from Firestore.

        Args:
            todoist_project_id: Todoist project ID

        Returns:
            ProjectSyncState if found, None otherwise
        """
        logger.info("Getting project state", extra={"project_id": todoist_project_id})

        client = await self._get_client()
        doc_ref = client.collection(self._project_collection_ref()).document(todoist_project_id)
        doc = await doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            return ProjectSyncState(**data)

        return None

    async def save_project_state(self, state: ProjectSyncState) -> None:
        """
        Save project sync state to Firestore.

        Args:
            state: ProjectSyncState to save
        """
        logger.info("Saving project state", extra={"project_id": state.todoist_project_id})

        client = await self._get_client()
        doc_ref = client.collection(self._project_collection_ref()).document(
            state.todoist_project_id
        )

        # Convert to dict
        data = state.model_dump()
        data["last_synced_at"] = state.last_synced_at

        await doc_ref.set(data)

    async def get_all_task_states(self) -> List[TaskSyncState]:
        """
        Retrieve all task sync states.

        Returns:
            List of TaskSyncState objects
        """
        logger.info("Getting all task states")

        client = await self._get_client()
        collection_ref = client.collection(self._task_collection_ref())
        docs = collection_ref.stream()

        states = []
        async for doc in docs:
            data = doc.to_dict()
            states.append(TaskSyncState(**data))

        return states

    async def mark_task_archived(
        self,
        todoist_task_id: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Mark a task as archived in sync state.

        Args:
            todoist_task_id: Todoist task ID
            error_message: Optional error message
        """
        logger.info("Marking task as archived", extra={"task_id": todoist_task_id})

        state = await self.get_task_state(todoist_task_id)
        if state:
            state.sync_status = SyncStatus.ARCHIVED
            state.last_synced_at = datetime.now()
            if error_message:
                state.error_message = error_message
            await self.save_task_state(state)

    async def mark_task_error(self, todoist_task_id: str, error_message: str) -> None:
        """
        Mark a task sync as errored.

        Args:
            todoist_task_id: Todoist task ID
            error_message: Error message
        """
        logger.error(
            "Marking task as error",
            extra={"task_id": todoist_task_id, "error": error_message},
        )

        state = await self.get_task_state(todoist_task_id)
        if state:
            state.sync_status = SyncStatus.ERROR
            state.error_message = error_message
            state.last_synced_at = datetime.now()
            await self.save_task_state(state)

    async def close(self) -> None:
        """Close Firestore client connection."""
        if self.client:
            # AsyncClient doesn't have explicit close, but we clear the reference
            self.client = None

