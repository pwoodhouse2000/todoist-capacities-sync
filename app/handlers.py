"""Request handlers for webhooks and reconciliation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from google.cloud import pubsub_v1

from app.notion_client import NotionClient
from app.logging_setup import get_logger
from app.models import PubSubMessage, SyncAction, SyncStatus, TaskSyncState, TodoistTask, TodoistWebhookEvent
from app.pubsub_worker import SyncWorker
from app.reverse_mapper import (
    compute_notion_properties_hash,
    extract_notion_task_properties,
    notion_props_differ,
)
from app.settings import settings
from app.store import FirestoreStore
from app.todoist_client import TodoistClient
from app.utils import build_todoist_task_url, compute_payload_hash, has_capsync_label, should_auto_label_task

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
        then syncs all tasks with the label. Also syncs Notion→Todoist changes.

        Returns:
            Reconciliation summary
        """
        logger.info("Starting reconciliation")

        # Clear caches from any previous run
        self.todoist.clear_caches()

        # Step 1: Auto-label eligible tasks (also warms project cache via get_projects)
        auto_labeled_count = await self._auto_label_tasks()

        # Step 2: Reconcile projects (archival status + name sync)
        await self._reconcile_projects()

        # Step 3: Todoist→Notion sync FIRST (authoritative direction)
        # IMPORTANT: This must run BEFORE Notion→Todoist to ensure Todoist changes
        # land in Notion first. This updates the notion_payload_hash in Firestore,
        # so the subsequent Notion→Todoist step correctly recognizes these as echoes
        # and doesn't push stale Notion values back to Todoist.
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
            "Found tasks with capsync label",
            extra={
                "active": len(active_tasks),
                "completed": len(completed_tasks),
                "total": len(all_fetched_tasks),
                "auto_labeled": auto_labeled_count,
            },
        )

        # Fetch all stored sync states
        stored_states = await self.store.get_all_task_states()
        stored_task_ids = {state.todoist_task_id for state in stored_states}

        # OPTIMIZATION: Pass task snapshots to avoid re-fetching each task individually.
        # Each task already has full data from the bulk fetch above.
        # This saves ~262 GET /tasks/{id} calls (1 per task).
        upserted = 0
        for task in all_fetched_tasks:
            try:
                message = PubSubMessage(
                    action=SyncAction.UPSERT,
                    todoist_task_id=task.id,
                    snapshot=task.model_dump(),
                )
                await self.worker.process_message(message, sync_source="reconciliation")
                upserted += 1
            except Exception as e:
                logger.error(
                    "Error upserting task during reconcile",
                    extra={"task_id": task.id, "error": str(e)},
                )

        # Step 4: Notion→Todoist sync AFTER Todoist→Notion
        # Now that all Todoist changes have been written to Notion (with updated hashes),
        # this step will only push genuinely user-initiated Notion edits to Todoist.
        # Echo suppression will correctly skip any pages that were just updated by Step 3.
        notion_to_todoist_count = 0
        if settings.enable_notion_to_todoist:
            notion_to_todoist_count = await self._sync_notion_to_todoist()

        # Step 5: Create Todoist tasks from new Notion pages
        notion_created_count = 0
        if settings.enable_notion_task_creation:
            notion_created_count = await self._create_todoist_tasks_from_notion()

        # Step 6: Archive tasks that are no longer in Todoist
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
            "notion_to_todoist_synced": notion_to_todoist_count,
            "notion_created_in_todoist": notion_created_count,
            "upserted": upserted,
            "archived": archived,
            "total_stored": len(stored_states),
        }

        logger.info("Reconciliation completed", extra=summary)

        return summary

    async def _reconcile_projects(self) -> None:
        """
        Reconcile all Todoist projects, syncing name changes and archival status.
        Also syncs project names from Notion → Todoist (bidirectional).
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

        # Also sync project names from Notion → Todoist
        await self._reconcile_notion_project_names()

    async def _sync_notion_to_todoist(self) -> int:
        """
        Poll Notion for task changes and push diffs to Todoist.

        Uses hash-based echo suppression:
        - Computes current notion_properties_hash for each edited page
        - Compares against stored notion_payload_hash
        - If equal → our own echo from a recent Todoist→Notion push → skip
        - If different → genuine Notion edit → push changes to Todoist

        Returns:
            Number of tasks synced from Notion→Todoist
        """
        logger.info("Starting Notion→Todoist sync")

        # Get last reconciliation timestamp
        last_reconcile = await self.store.get_last_reconcile_time()
        if not last_reconcile:
            # First run: use a reasonable default (1 hour ago)
            one_hour_ago = datetime.now(timezone.utc).isoformat()
            logger.info("No last reconcile time, setting initial timestamp")
            await self.store.set_last_reconcile_time(one_hour_ago)
            return 0

        # Fetch Notion pages edited since last reconcile
        try:
            edited_pages = await self.notion.get_tasks_edited_since(last_reconcile)
        except Exception as e:
            logger.warning(
                "Failed to fetch edited Notion pages",
                extra={"error": str(e)},
            )
            return 0

        logger.info(
            "Found Notion pages edited since last reconcile",
            extra={"count": len(edited_pages), "since": last_reconcile},
        )

        # Build project state lookup for resolving Notion project IDs → Todoist project IDs
        project_states = await self.store.get_all_project_states()
        notion_to_todoist_project = {
            ps.capacities_object_id: ps.todoist_project_id
            for ps in project_states
            if ps.capacities_object_id
        }

        synced_count = 0

        for page in edited_pages:
            try:
                # Extract sync-relevant properties
                notion_props = extract_notion_task_properties(page)
                todoist_task_id = notion_props.get("todoist_task_id", "")

                # Skip pages without Todoist Task ID (handled by _create_todoist_tasks_from_notion)
                if not todoist_task_id:
                    continue

                # Compute current hash of Notion properties
                current_hash = compute_notion_properties_hash(notion_props)

                # Look up stored state
                state = await self.store.get_task_state(todoist_task_id)
                if not state:
                    logger.debug(
                        "No Firestore state for task, skipping Notion→Todoist",
                        extra={"todoist_task_id": todoist_task_id},
                    )
                    continue

                # Echo suppression: compare hashes
                if state.notion_payload_hash == current_hash:
                    logger.debug(
                        "Notion page unchanged (echo suppressed)",
                        extra={"todoist_task_id": todoist_task_id},
                    )
                    continue

                # Fetch current Todoist task to compare
                try:
                    todoist_task = await self.todoist.get_task(todoist_task_id)
                except Exception as e:
                    logger.warning(
                        "Could not fetch Todoist task for comparison",
                        extra={"todoist_task_id": todoist_task_id, "error": str(e)},
                    )
                    continue

                # Determine what changed
                todoist_due = todoist_task.due.date if todoist_task.due else None
                changes = notion_props_differ(
                    notion_props,
                    todoist_title=todoist_task.content,
                    todoist_priority=todoist_task.priority,
                    todoist_due_date=todoist_due,
                    todoist_completed=todoist_task.checked,
                )

                if not changes:
                    # Properties match Todoist — update stored hash to prevent future comparisons
                    state.notion_payload_hash = current_hash
                    await self.store.save_task_state(state)
                    continue

                logger.info(
                    "Notion→Todoist: pushing changes",
                    extra={
                        "todoist_task_id": todoist_task_id,
                        "changes": list(changes.keys()),
                    },
                )

                # Apply changes to Todoist
                # Handle completion separately from property updates
                if "completed" in changes:
                    if changes["completed"]:
                        await self.todoist.complete_task(todoist_task_id)
                        logger.info("Marked task complete in Todoist", extra={"task_id": todoist_task_id})
                    else:
                        await self.todoist.uncomplete_task(todoist_task_id)
                        logger.info("Reopened task in Todoist", extra={"task_id": todoist_task_id})

                # Apply property changes (title, priority, due_date)
                prop_changes = {k: v for k, v in changes.items() if k != "completed"}
                if prop_changes:
                    await self.todoist.update_task(
                        todoist_task_id,
                        content=prop_changes.get("title"),
                        priority=prop_changes.get("priority"),
                        due_date=prop_changes.get("due_date"),
                    )

                # After pushing to Todoist, update both hashes to prevent echo loop:
                # 1. notion_payload_hash = current Notion state (prevents re-pushing same changes)
                # 2. payload_hash = re-computed from the Todoist task (prevents the resulting
                #    Todoist→Notion push from creating an echo)
                from app.mapper import map_task_to_todo
                updated_task = await self.todoist.get_task(todoist_task_id)
                project = await self.todoist.get_project(updated_task.project_id)
                comments = await self.todoist.get_comments(todoist_task_id)
                todo = map_task_to_todo(updated_task, project, comments)
                new_payload_hash = compute_payload_hash(todo.model_dump())

                state.payload_hash = new_payload_hash
                state.notion_payload_hash = current_hash
                state.last_synced_at = datetime.now()
                state.sync_source = "notion-to-todoist"
                await self.store.save_task_state(state)

                synced_count += 1

            except Exception as e:
                page_id = page.get("id", "unknown")
                logger.error(
                    "Error syncing Notion page to Todoist",
                    extra={"page_id": page_id, "error": str(e)},
                    exc_info=True,
                )

        # Update last reconcile time
        await self.store.set_last_reconcile_time(
            datetime.now(timezone.utc).isoformat()
        )

        logger.info(
            "Notion→Todoist sync complete",
            extra={"synced": synced_count, "checked": len(edited_pages)},
        )

        return synced_count

    async def _create_todoist_tasks_from_notion(self) -> int:
        """
        Find Notion task pages without a Todoist Task ID and create tasks in Todoist.

        Returns:
            Number of tasks created in Todoist
        """
        logger.info("Checking for new Notion tasks to create in Todoist")

        try:
            pages = await self.notion.get_tasks_without_todoist_id()
        except Exception as e:
            logger.warning(
                "Failed to fetch Notion pages without Todoist ID",
                extra={"error": str(e)},
            )
            return 0

        if not pages:
            logger.info("No new Notion tasks to create in Todoist")
            return 0

        logger.info("Found Notion tasks to create in Todoist", extra={"count": len(pages)})

        # Build project lookup
        project_states = await self.store.get_all_project_states()
        notion_to_todoist_project = {
            ps.capacities_object_id: ps.todoist_project_id
            for ps in project_states
            if ps.capacities_object_id
        }

        created_count = 0

        for page in pages:
            try:
                notion_props = extract_notion_task_properties(page)
                title = notion_props.get("title", "")
                notion_page_id = notion_props.get("notion_page_id", "")

                if not title or not notion_page_id:
                    continue

                # Skip archived/deleted pages
                if page.get("archived", False):
                    continue

                # Resolve project: Notion project relation → Todoist project ID
                todoist_project_id = None
                project_notion_id = notion_props.get("project_notion_id")
                if project_notion_id:
                    todoist_project_id = notion_to_todoist_project.get(project_notion_id)

                if not todoist_project_id:
                    # Default: find first non-Inbox project or use a default
                    # For now, log and skip - user should assign a project in Notion
                    logger.warning(
                        "Notion task has no mapped project, skipping creation",
                        extra={"notion_page_id": notion_page_id, "title": title},
                    )
                    continue

                # Build task data
                priority = notion_props.get("priority", 1)
                due_date = notion_props.get("due_date")
                labels = ["capsync"]  # Always add capsync label

                # Create task in Todoist
                new_task = await self.todoist.create_task(
                    content=title,
                    project_id=todoist_project_id,
                    priority=priority,
                    due_date=due_date,
                    labels=labels,
                )

                logger.info(
                    "Created Todoist task from Notion",
                    extra={
                        "todoist_task_id": new_task.id,
                        "notion_page_id": notion_page_id,
                        "title": title,
                    },
                )

                # Set Todoist Task ID and URL back on the Notion page
                task_url = build_todoist_task_url(new_task.id)
                await self.notion.set_todoist_task_id(notion_page_id, new_task.id, task_url)

                # Compute hashes for echo suppression
                notion_hash = compute_notion_properties_hash(notion_props)

                from app.mapper import map_task_to_todo
                project = await self.todoist.get_project(todoist_project_id)
                comments = await self.todoist.get_comments(new_task.id)
                todo = map_task_to_todo(new_task, project, comments)
                payload_hash = compute_payload_hash(todo.model_dump())

                # Create Firestore state
                new_state = TaskSyncState(
                    todoist_task_id=new_task.id,
                    capacities_object_id=notion_page_id,
                    payload_hash=payload_hash,
                    notion_payload_hash=notion_hash,
                    last_synced_at=datetime.now(),
                    sync_status=SyncStatus.OK,
                    sync_source="notion-created",
                )
                await self.store.save_task_state(new_state)

                created_count += 1

            except Exception as e:
                page_id = page.get("id", "unknown")
                logger.error(
                    "Error creating Todoist task from Notion",
                    extra={"page_id": page_id, "error": str(e)},
                    exc_info=True,
                )

        logger.info(
            "Notion task creation complete",
            extra={"created": created_count},
        )

        return created_count

    async def _reconcile_notion_project_names(self) -> None:
        """
        Pull project name edits from Notion into Todoist.

        Per sync rules:
        - Projects: Name is bidirectional (Notion wins post-creation)
        """
        try:
            # Fetch all project pages from Notion
            project_pages = await self.notion.get_all_project_pages()

            for page in project_pages:
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
                            logger.info(
                                "Updated Todoist project name from Notion",
                                extra={"project_id": proj_id, "name": name},
                            )
                    except Exception as e:
                        logger.debug(f"Could not sync project {proj_id}: {e}")

        except Exception as e:
            logger.warning(
                "Notion→Todoist project name sync skipped due to error",
                extra={"error": str(e)},
            )

