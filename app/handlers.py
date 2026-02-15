"""Request handlers for webhooks and reconciliation."""

from typing import Any, Dict, Optional, Union

from google.cloud import pubsub_v1

from app.notion_client import NotionClient
from app.logging_setup import get_logger
from app.models import PubSubMessage, SyncAction, TodoistTask, TodoistWebhookEvent
from app.pubsub_worker import SyncWorker
from app.settings import settings
from app.store import FirestoreStore
from app.todoist_client import TodoistClient
from app.utils import has_capsync_label, should_auto_label_task

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

    async def _auto_label_tasks(self) -> int:
        """
        Auto-add/remove capsync label based on task eligibility.
        
        ADD label if task is:
        - Not completed
        - Not in Inbox
        - Not recurring
        - Doesn't already have capsync label
        
        REMOVE label if task is:
        - Recurring (changed from one-off)
        - In Inbox (moved from project)
        - Has capsync label
        
        Returns:
            Number of tasks that were auto-labeled/unlabeled
        """
        # Check if auto-labeling is enabled
        if not settings.auto_label_tasks:
            logger.info("Auto-labeling is disabled")
            return 0
        
        logger.info("Auto-labeling/unlabeling eligible tasks")
        
        # Fetch all active (non-completed) tasks
        all_tasks = await self.todoist.get_tasks()
        
        # Fetch all projects to identify Inbox
        all_projects = await self.todoist.get_projects()
        inbox_project_ids = {p.id for p in all_projects if p.name == "Inbox"}
        
        auto_labeled = 0
        auto_unlabeled = 0
        
        for task in all_tasks:
            # Skip completed tasks
            if task.checked:
                continue
            
            # Check if task is recurring
            is_recurring = task.due.is_recurring if task.due else False
            
            # Check if task is in Inbox
            is_inbox = task.project_id in inbox_project_ids
            
            # Check if task currently has capsync label
            has_label = has_capsync_label(task.labels)
            
            # Determine if task SHOULD be labeled
            should_label = should_auto_label_task(task.project_id, is_recurring, is_inbox)
            
            # ADD label if eligible and doesn't have it
            if should_label and not has_label:
                try:
                    await self.todoist.add_label_to_task(task.id, "capsync", task.labels)
                    auto_labeled += 1
                    logger.info(
                        "Auto-added capsync label to task",
                        extra={"task_id": task.id, "content": task.content},
                    )
                except Exception as e:
                    logger.error(
                        "Error adding label to task",
                        extra={"task_id": task.id, "error": str(e)},
                    )
            
            # REMOVE label if no longer eligible but still has it
            elif not should_label and has_label:
                try:
                    await self.todoist.remove_label_from_task(task.id, "capsync", task.labels)
                    auto_unlabeled += 1
                    logger.info(
                        "Auto-removed capsync label from task (became ineligible)",
                        extra={
                            "task_id": task.id,
                            "content": task.content,
                            "is_recurring": is_recurring,
                            "is_inbox": is_inbox
                        },
                    )
                except Exception as e:
                    logger.error(
                        "Error removing label from task",
                        extra={"task_id": task.id, "error": str(e)},
                    )
        
        logger.info(
            "Auto-labeling complete",
            extra={
                "auto_labeled": auto_labeled,
                "auto_unlabeled": auto_unlabeled,
                "total_checked": len(all_tasks)
            },
        )
        
        return auto_labeled + auto_unlabeled

    async def reconcile(self) -> Dict[str, Any]:
        """
        Perform full reconciliation of all @capsync tasks.
        
        Auto-adds capsync label to eligible tasks (not in Inbox, not recurring, not completed)
        then syncs all tasks with the label.

        Returns:
            Reconciliation summary
        """
        logger.info("Starting reconciliation")

        # Step 1: Auto-label eligible tasks
        auto_labeled_count = await self._auto_label_tasks()
        
        # Step 2: Reconcile projects (archival status)
        await self._reconcile_projects()

        # Step 3a: Pull edits from Notion back to Todoist (titles + priority + project titles)
        await self._reconcile_notion_to_todoist()

        # Step 3b: Fetch all Todoist tasks with capsync label (both active AND completed)
        # We need to include completed tasks so they can be marked as completed in Notion
        active_tasks = await self.todoist.get_active_tasks_with_label()
        
        # Also fetch completed tasks with capsync label (they need to sync to Notion too)
        try:
            completed_tasks_response = await self.todoist._get_paginated(
                "/tasks",
                params={"filter": "@capsync & is:completed"}
            )
            completed_tasks = [TodoistTask(**task) for task in completed_tasks_response]
        except Exception as e:
            logger.warning(
                "Could not fetch completed tasks, continuing with active tasks only",
                extra={"error": str(e)},
            )
            completed_tasks = []
        
        # Combine active and completed tasks
        all_fetched_tasks = active_tasks + completed_tasks
        active_task_ids = {task.id for task in all_fetched_tasks}

        logger.info(
            "Found active tasks with capsync label",
            extra={"count": len(active_tasks), "auto_labeled": auto_labeled_count},
        )

        # Fetch all stored sync states
        stored_states = await self.store.get_all_task_states()
        stored_task_ids = {state.todoist_task_id for state in stored_states}

        # Process active and completed tasks (upsert)
        upserted = 0
        for task in all_fetched_tasks:
            try:
                message = PubSubMessage(
                    action=SyncAction.UPSERT,
                    todoist_task_id=task.id,
                )
                await self.worker.process_message(message, sync_source="reconciliation")
                upserted += 1
            except Exception as e:
                logger.error(
                    "Error upserting task during reconcile",
                    extra={"task_id": task.id, "error": str(e)},
                )

        # Note: Completed tasks are already included in all_fetched_tasks above
        # (fetched via the "@capsync & is:completed" filter in lines 276-280)
        # active_task_ids already includes both active and completed tasks

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
            "auto_labeled": auto_labeled_count,
            "upserted": upserted,
            "archived": archived,
            "total_stored": len(stored_states),
        }

        logger.info("Reconciliation completed", extra=summary)

        return summary

    async def _reconcile_projects(self) -> None:
        """
        Reconcile all Todoist projects, syncing name changes and archival status.
        """
        logger.info("Starting project reconciliation")
        all_todoist_projects = await self.todoist.get_projects()
        
        for project in all_todoist_projects:
            # Try to find existing project in Notion
            existing_page = await self.notion.find_project_by_todoist_id(project.id)
            if not existing_page:
                continue

            notion_page_id = existing_page["id"]
            
            # Sync archival status
            try:
                if project.is_archived:
                    await self.notion.update_project_status(notion_page_id, "Archived")
                    logger.info("Archived Notion project", extra={"project_id": project.id})
                else:
                    # If it was previously archived, maybe set it back to Active
                    current_status = existing_page.get("properties", {}).get("Status", {}).get("select", {}).get("name")
                    if current_status == "Archived":
                        await self.notion.update_project_status(notion_page_id, "Active")
                        logger.info("Un-archived Notion project", extra={"project_id": project.id})

            except Exception as e:
                logger.warning(f"Failed to update project status for {project.id}: {e}")

    async def _reconcile_notion_to_todoist(self) -> None:
        """
        Pull selected edits from Notion into Todoist.
        
        Per sync rules:
        - Projects: Name is bidirectional (Notion wins post-creation)
        - Tasks: ALL properties are one-way (Todoist always wins)
        """
        try:
            # 1) Projects: sync Name -> Todoist project name (bidirectional)
            projects = await self.notion.client.databases.query(
                database_id=self.notion.projects_db_id,
                page_size=100,  # Fetch more projects
            )
            for page in projects.get("results", []):
                props = page.get("properties", {})
                
                # Safely get name
                name_prop = props.get("Name", {}).get("title")
                name = name_prop[0].get("text", {}).get("content") if name_prop else None

                # Safely get project ID
                proj_id_prop = props.get("Todoist Project ID", {}).get("rich_text")
                proj_id = proj_id_prop[0].get("text", {}).get("content") if proj_id_prop else None
                
                if name and proj_id:
                    try:
                        todoist_proj = await self.todoist.get_project(proj_id)
                        if todoist_proj.name != name:
                            await self.todoist.update_project_name(proj_id, name)
                            logger.info("Updated Todoist project name from Notion", extra={"project_id": proj_id, "name": name})
                    except Exception as e:
                        logger.debug(f"Could not sync project {proj_id}: {e}")

            # 2) Tasks: NO sync from Notion → Todoist (Todoist always wins)
            # All task properties are one-way: Todoist → Notion only
            # Future: Add bidirectional sync as enhancement
            
        except Exception as e:
            logger.warning("Notion->Todoist reconciliation skipped due to error", extra={"error": str(e)})

