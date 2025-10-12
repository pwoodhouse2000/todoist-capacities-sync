"""Pub/Sub worker for processing sync jobs."""

from datetime import datetime
from typing import Optional

from app.notion_client import NotionClient
from app.logging_setup import get_logger
from app.mapper import create_archived_todo, map_project_to_notion, map_task_to_todo
from app.models import PubSubMessage, SyncAction, SyncStatus, TaskSyncState, TodoistTask
from app.settings import settings
from app.store import FirestoreStore
from app.todoist_client import TodoistClient
from app.utils import compute_payload_hash, extract_para_area, extract_person_labels, has_capsync_label
from typing import List

logger = get_logger(__name__)


class SyncWorker:
    """Process sync jobs from Pub/Sub messages."""

    def __init__(
        self,
        todoist_client: TodoistClient,
        notion_client: NotionClient,
        store: FirestoreStore,
    ) -> None:
        """
        Initialize sync worker.

        Args:
            todoist_client: Todoist API client
            notion_client: Notion API client
            store: Firestore store for state management
        """
        self.todoist = todoist_client
        self.notion = notion_client
        self.store = store

    async def process_message(self, message: PubSubMessage, sync_source: str = "webhook") -> None:
        """
        Process a single Pub/Sub sync message.

        Args:
            message: PubSubMessage with sync instructions
            sync_source: Source of sync ("webhook" or "reconciliation")
        """
        logger.info(
            "Processing sync message",
            extra={
                "action": message.action,
                "task_id": message.todoist_task_id,
                "sync_source": sync_source,
            },
        )

        try:
            if message.action == SyncAction.UPSERT:
                await self._handle_upsert(message, sync_source)
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

    async def _handle_upsert(self, message: PubSubMessage, sync_source: str = "webhook") -> None:
        """
        Handle UPSERT action: create or update task in Notion.

        Args:
            message: PubSubMessage with task data
            sync_source: Source of sync ("webhook" or "reconciliation")
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
        # Exception: If task was previously synced and is now completed, update it even without label
        # (completed tasks might lose labels in Todoist API responses)
        existing_state = await self.store.get_task_state(task_id)
        
        if not has_capsync_label(task.labels):
            # If task is completed and was previously synced, update it to mark as complete
            if task.is_completed and existing_state:
                logger.info(
                    "Completed task without label - updating to mark complete",
                    extra={"task_id": task_id},
                )
                # Continue to update the task
            else:
                logger.info(
                    "Task does not have @capsync label, skipping",
                    extra={"task_id": task_id},
                )
                # If it previously existed, archive it
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

        # Map to Notion models
        todo = map_task_to_todo(task, project, comments, section_name)
        notion_project = map_project_to_notion(project)

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

        # Ensure project exists in Notion
        project_notion_id = await self._ensure_project_exists(notion_project, task.labels)
        
        # Extract PARA area from task labels
        # (Todoist projects don't have labels, so we use task labels)
        area_name = extract_para_area(task.labels)
        area_page_id = None
        if area_name:
            area_page_id = await self.notion.ensure_area_exists(area_name)
            logger.info(
                "Task assigned to AREA",
                extra={"task_id": task_id, "area": area_name},
            )

        # Extract and match people from task labels
        person_names = extract_person_labels(task.labels)
        people_page_ids = []
        
        logger.info(
            "Extracted person labels from task",
            extra={"task_id": task_id, "person_names": person_names, "all_labels": task.labels},
        )
        
        if person_names:
            people_page_ids = await self.notion.match_people(person_names)
            logger.info(
                "Person matching complete",
                extra={"task_id": task_id, "people_count": len(people_page_ids), "person_names": person_names, "matched": len(people_page_ids) > 0},
            )

        # Upsert task in Notion
        # First check Firestore state
        notion_page_id = existing_state.capacities_object_id if existing_state else None
        
        # If no state in Firestore, check if page exists in Notion by Todoist ID
        if not notion_page_id:
            existing_page = await self.notion.find_todo_by_todoist_id(task_id)
            if existing_page:
                notion_page_id = existing_page["id"]
                logger.info(
                    "Found existing page in Notion without Firestore state",
                    extra={"task_id": task_id, "page_id": notion_page_id},
                )
        
        if notion_page_id:
            # Update existing page
            result = await self.notion.update_todo_page(notion_page_id, todo, area_page_id, people_page_ids)
        else:
            # Create new page
            result = await self.notion.create_todo_page(todo, project_notion_id, area_page_id, people_page_ids)
            notion_page_id = result.get("id")

        # Update sync state
        new_state = TaskSyncState(
            todoist_task_id=task_id,
            capacities_object_id=notion_page_id,  # Using same field name for compatibility
            payload_hash=payload_hash,
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
            sync_source=sync_source,
        )
        await self.store.save_task_state(new_state)

        logger.info(
            "Successfully synced task to Notion",
            extra={
                "task_id": task_id,
                "notion_page_id": notion_page_id,
            },
        )
        
        # Add Notion backlink to Todoist task description if enabled
        if settings.add_notion_backlink:
            await self._add_notion_backlink(task, notion_page_id)

    async def _handle_archive(self, message: PubSubMessage) -> None:
        """
        Handle ARCHIVE action: archive task page in Notion.

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

        notion_page_id = existing_state.capacities_object_id

        # Archive the Notion page
        try:
            await self.notion.archive_page(notion_page_id)
        except Exception as e:
            logger.warning(
                "Could not archive Notion page",
                extra={"task_id": task_id, "page_id": notion_page_id, "error": str(e)},
            )

        # Update sync state
        await self.store.mark_task_archived(task_id)

        logger.info(
            "Successfully archived task in Notion",
            extra={"task_id": task_id},
        )

    async def _ensure_project_exists(
        self, 
        project: "NotionProject",
        task_labels: List[str]
    ) -> Optional[str]:
        """
        Ensure project exists in Notion, create if needed.

        Args:
            project: NotionProject model
            task_labels: Labels from the task (for area detection since projects don't have labels)

        Returns:
            Notion project page ID
        """
        project_id = project.todoist_project_id

        # Check if we already have it synced
        existing_state = await self.store.get_project_state(project_id)
        if existing_state and existing_state.capacities_object_id:
            return existing_state.capacities_object_id

        # Try to find it in Notion
        existing_page = await self.notion.find_project_by_todoist_id(project_id)
        if existing_page:
            notion_page_id = existing_page["id"]
        else:
            # Extract PARA area from task labels (projects don't have labels in Todoist)
            # We'll use the task's area label to categorize the project
            from app.utils import extract_para_area
            area_name = extract_para_area(task_labels)
            area_page_id = None
            if area_name:
                area_page_id = await self.notion.ensure_area_exists(area_name)
                logger.info(
                    "Project assigned to AREA",
                    extra={"project_id": project_id, "area": area_name},
                )
            
            # Create new project page with area relation
            result = await self.notion.create_project_page(project, area_page_id)
            notion_page_id = result.get("id")

        # Save state
        from app.models import ProjectSyncState

        state = ProjectSyncState(
            todoist_project_id=project_id,
            capacities_object_id=notion_page_id,  # Using same field name for compatibility
            payload_hash=compute_payload_hash(project.model_dump()),
            last_synced_at=datetime.now(),
        )
        await self.store.save_project_state(state)

        logger.info(
            "Ensured project exists in Notion",
            extra={
                "project_id": project_id,
                "notion_page_id": notion_page_id,
            },
        )

        return notion_page_id

    async def _add_notion_backlink(self, task: TodoistTask, notion_page_id: str) -> None:
        """
        Add Notion page link to Todoist task description.

        Args:
            task: TodoistTask object
            notion_page_id: Notion page ID
        """
        # Construct Notion URL (remove hyphens from page ID)
        notion_url = f"https://notion.so/{notion_page_id.replace('-', '')}"
        
        # Check if link is already in description
        if notion_url in task.description or "notion.so" in task.description:
            logger.info(
                "Notion link already in task description",
                extra={"task_id": task.id},
            )
            return
        
        # Append Notion link to description
        separator = "\n\n" if task.description else ""
        new_description = f"{task.description}{separator}🔗 [View in Notion]({notion_url})"
        
        try:
            await self.todoist.update_task_description(task.id, new_description)
            logger.info(
                "Added Notion backlink to Todoist task",
                extra={"task_id": task.id, "notion_url": notion_url},
            )
        except Exception as e:
            # Don't fail the sync if backlink fails
            logger.warning(
                "Failed to add Notion backlink to Todoist task",
                extra={"task_id": task.id, "error": str(e)},
            )
