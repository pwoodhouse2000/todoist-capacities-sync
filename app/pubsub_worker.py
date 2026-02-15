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
from app.utils import compute_payload_hash, extract_para_area, extract_para_areas, extract_person_labels, has_capsync_label
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
            try:
                task = TodoistTask(**message.snapshot)
            except Exception as e:
                logger.warning(
                    "Could not parse task snapshot, falling back to API fetch",
                    extra={"task_id": task_id, "error": str(e)},
                )
                task = await self.todoist.get_task(task_id)
        else:
            task = await self.todoist.get_task(task_id)

        # Gate: Check if task has @capsync label
        # Exception: If task was previously synced and is now completed, update it even without label
        # (completed tasks might lose labels in Todoist API responses)
        existing_state = await self.store.get_task_state(task_id)
        
        if not has_capsync_label(task.labels):
            # If task is completed and was previously synced, update it to mark as complete
            if task.checked and existing_state:
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

        # NEW TASK: Inherit Area label from parent project if not already present
        # This runs for new tasks (no existing_state) to auto-assign Area labels
        if not existing_state and sync_source == "webhook":
            from app.utils import get_area_label_from_parent_project
            
            # Check if task already has an Area label
            current_area = extract_para_area(task.labels)
            
            if not current_area:
                # Try to inherit from parent project
                try:
                    parent_project = await self.todoist.get_parent_project(task.project_id)
                    if parent_project:
                        inherited_area = get_area_label_from_parent_project(parent_project.name)
                        if inherited_area:
                            # Add the inherited area label to the task
                            new_labels = list(task.labels or []) + [inherited_area]
                            await self.todoist.add_label_to_task(task_id, inherited_area, task.labels or [])
                            task.labels = new_labels  # Update task object for downstream processing
                            logger.info(
                                "Inherited Area label from parent project",
                                extra={
                                    "task_id": task_id,
                                    "parent_project": parent_project.name,
                                    "area_label": inherited_area,
                                },
                            )
                        else:
                            logger.debug(
                                "Parent project name did not match any Area",
                                extra={
                                    "task_id": task_id,
                                    "parent_project": parent_project.name,
                                },
                            )
                    else:
                        logger.debug(
                            "Task has no parent project",
                            extra={"task_id": task_id},
                        )
                except Exception as e:
                    logger.debug(
                        "Could not inherit Area label from parent project",
                        extra={"task_id": task_id, "error": str(e)},
                    )

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

        # Skip if unchanged (idempotency check)
        # NOTE: We use the existing_state fetched at line 103, not a fresh fetch
        # This is important because task.labels may have been modified (line 141)
        # by the Area inheritance logic, so we must use the same state for consistency
        if existing_state and existing_state.payload_hash == payload_hash:
            logger.info(
                "Task unchanged, skipping sync",
                extra={"task_id": task_id, "hash": payload_hash},
            )
            return

        # Ensure project exists in Notion (and capture page id for potential project moves)
        # Returns None for Inbox or other filtered projects
        project_notion_id = await self._ensure_project_exists(notion_project, task.labels)
        
        # If project is filtered (e.g., Inbox), we don't sync this task
        # Per sync rules: tasks must be in a project (not Inbox) to sync
        if not project_notion_id:
            logger.info(
                "Task belongs to filtered project (e.g., Inbox), skipping sync",
                extra={"task_id": task_id, "project_name": project.name}
            )
            return
        
        # Extract PARA areas from task labels (supports multiple areas)
        # (Todoist projects don't have labels, so we use task labels)
        area_names = extract_para_areas(task.labels)
        area_page_ids = []
        if area_names:
            for area_name in area_names:
                area_id = await self.notion.ensure_area_exists(area_name)
                if area_id:  # Only add if area exists in Notion
                    area_page_ids.append(area_id)
            
            if area_page_ids:
                logger.info(
                    "Task assigned to AREA(s)",
                    extra={"task_id": task_id, "areas": area_names, "count": len(area_page_ids)},
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

        # Upsert task in Notion with race condition protection
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
        
        # Double-check state again after Notion query (race condition protection)
        # Another process might have created it between our first check and now
        if not notion_page_id:
            existing_state_recheck = await self.store.get_task_state(task_id)
            if existing_state_recheck and existing_state_recheck.capacities_object_id:
                notion_page_id = existing_state_recheck.capacities_object_id
                logger.info(
                    "Found state created by concurrent process",
                    extra={"task_id": task_id, "page_id": notion_page_id},
                )
        
        if notion_page_id:
            # Update existing page (also update Project relation if task moved projects)
            result = await self.notion.update_todo_page(
                notion_page_id,
                todo,
                area_page_ids,  # Now supports multiple areas
                people_page_ids,
                project_page_id=project_notion_id,
            )
        else:
            # Create new page
            result = await self.notion.create_todo_page(todo, project_notion_id, area_page_ids, people_page_ids)
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
        
        # Add Notion backlinks to Todoist task description if enabled
        # Includes both task page link and project page link
        if settings.add_notion_backlink:
            await self._add_notion_backlink(task, notion_page_id, project_notion_id)

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
        
        Per sync rules:
        - Never sync Inbox project
        - Set project AREAS at creation only (from aggregated task areas)
        - Don't update AREAS post-creation (Notion-controlled)

        Args:
            project: NotionProject model
            task_labels: Labels from the task (for area detection since projects don't have labels)

        Returns:
            Notion project page ID, or None if project should not be synced (e.g., Inbox)
        """
        project_id = project.todoist_project_id
        
        # Filter out Inbox project (should never sync)
        if project.name == "Inbox":
            logger.info(
                "Skipping Inbox project sync",
                extra={"project_id": project_id, "project_name": project.name}
            )
            return None

        # Check if we already have it synced
        existing_state = await self.store.get_project_state(project_id)
        if existing_state and existing_state.capacities_object_id:
            return existing_state.capacities_object_id

        # Try to find it in Notion
        existing_page = await self.notion.find_project_by_todoist_id(project_id)
        if existing_page:
            notion_page_id = existing_page["id"]
            # Project already exists - update metadata (name, color, URL) but NOT areas
            # Per sync rules: AREAS are set once at creation, then Notion-controlled
            try:
                await self.notion.update_project_page(
                    notion_page_id, 
                    project, 
                    area_page_ids=None  # Don't update areas post-creation
                )
                logger.info(
                    "Updated existing project (metadata only, no AREAS update)",
                    extra={"project_id": project_id, "notion_page_id": notion_page_id}
                )
            except Exception as e:
                # Non-fatal; continue with existing page
                logger.warning(
                    "Failed to update project metadata",
                    extra={"project_id": project_id, "error": str(e)}
                )
        else:
            # NEW PROJECT: Aggregate AREAS from ALL tasks in project
            area_page_ids = await self._get_project_areas(project_id)
            
            if area_page_ids:
                logger.info(
                    "Project assigned to AREA(s) from task aggregation",
                    extra={"project_id": project_id, "area_count": len(area_page_ids)},
                )
            
            # Create new project page with aggregated area relations
            result = await self.notion.create_project_page(project, area_page_ids)
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
    
    async def _get_project_areas(self, project_id: str) -> List[str]:
        """
        Get unique AREAS for a project by aggregating from all its tasks.
        
        Per sync rules: Project AREAS inherited from ALL areas present in project's tasks.
        
        Args:
            project_id: Todoist project ID
            
        Returns:
            List of Notion AREA page IDs
        """
        try:
            # Fetch all tasks in this project with capsync label
            all_tasks = await self.todoist.get_active_tasks_with_label("capsync")
            project_tasks = [t for t in all_tasks if t.project_id == project_id]
            
            logger.info(
                "Aggregating areas from project tasks",
                extra={"project_id": project_id, "task_count": len(project_tasks)}
            )
            
            # Collect unique area names from all tasks
            unique_area_names = set()
            for task in project_tasks:
                area_names = extract_para_areas(task.labels)
                unique_area_names.update(area_names)
            
            # Look up Notion page IDs for these areas
            area_page_ids = []
            for area_name in unique_area_names:
                area_id = await self.notion.ensure_area_exists(area_name)
                if area_id:  # Only add if area exists in Notion
                    area_page_ids.append(area_id)
            
            logger.info(
                "Project area aggregation complete",
                extra={
                    "project_id": project_id,
                    "unique_areas": list(unique_area_names),
                    "found_ids": len(area_page_ids)
                }
            )
            
            return area_page_ids
            
        except Exception as e:
            logger.warning(
                "Failed to aggregate project areas, continuing without",
                extra={"project_id": project_id, "error": str(e)}
            )
            return []

    async def _add_notion_backlink(
        self, 
        task: TodoistTask, 
        notion_task_page_id: str,
        notion_project_page_id: Optional[str]
    ) -> None:
        """
        Add Notion page links to Todoist task description.
        
        Per sync rules: Add TWO links:
        1. Link to task page in Notion
        2. Link to project page in Notion
        
        Args:
            task: TodoistTask object
            notion_task_page_id: Notion task page ID
            notion_project_page_id: Notion project page ID (None if project filtered like Inbox)
        """
        # Construct Notion URLs (remove hyphens from page IDs)
        task_url = f"https://notion.so/{notion_task_page_id.replace('-', '')}"
        
        # Check if links already exist in description
        if "notion.so" in task.description:
            logger.info(
                "Notion links already in task description",
                extra={"task_id": task.id},
            )
            return
        
        # Build backlink section with both task and project links
        separator = "\n\n---\n" if task.description else ""
        new_description = f"{task.description}{separator}"
        new_description += f"📝 View Task in Notion: {task_url}\n"
        
        if notion_project_page_id:
            project_url = f"https://notion.so/{notion_project_page_id.replace('-', '')}"
            new_description += f"📁 View Project in Notion: {project_url}"
        
        try:
            await self.todoist.update_task_description(task.id, new_description)
            logger.info(
                "Added Notion backlinks to Todoist task",
                extra={
                    "task_id": task.id,
                    "task_url": task_url,
                    "has_project_link": notion_project_page_id is not None
                },
            )
        except Exception as e:
            # Don't fail the sync if backlink fails
            logger.warning(
                "Failed to add Notion backlinks to Todoist task",
                extra={"task_id": task.id, "error": str(e)},
            )
