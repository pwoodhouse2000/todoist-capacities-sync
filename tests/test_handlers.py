"""Tests for webhook and reconciliation handlers."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import (
    PubSubMessage,
    SyncAction,
    SyncStatus,
    TaskSyncState,
    TodoistWebhookEvent,
)


# ============================================================================
# WebhookHandler tests
# ============================================================================


@pytest.fixture
def mock_publisher():
    """Mock Pub/Sub publisher."""
    publisher = MagicMock()
    publisher.topic_path.return_value = "projects/test/topics/todoist-sync-jobs"
    future = MagicMock()
    future.result.return_value = "msg-id-123"
    publisher.publish.return_value = future
    return publisher


@pytest.fixture
def webhook_handler(mock_publisher):
    """Create a WebhookHandler with mocked publisher."""
    with patch("app.handlers.settings") as mock_settings:
        mock_settings.gcp_project_id = "test-project"
        mock_settings.pubsub_topic = "todoist-sync-jobs"
        from app.handlers import WebhookHandler

        return WebhookHandler(mock_publisher)


class TestDetermineAction:
    def test_item_added_returns_upsert(self, webhook_handler):
        result = webhook_handler._determine_action("item:added", {"id": "1"})
        assert result == SyncAction.UPSERT

    def test_item_updated_returns_upsert(self, webhook_handler):
        result = webhook_handler._determine_action("item:updated", {"id": "1"})
        assert result == SyncAction.UPSERT

    def test_item_completed_returns_upsert(self, webhook_handler):
        result = webhook_handler._determine_action("item:completed", {"id": "1"})
        assert result == SyncAction.UPSERT

    def test_item_uncompleted_returns_upsert(self, webhook_handler):
        result = webhook_handler._determine_action("item:uncompleted", {"id": "1"})
        assert result == SyncAction.UPSERT

    def test_note_added_returns_upsert(self, webhook_handler):
        result = webhook_handler._determine_action("note:added", {"id": "1"})
        assert result == SyncAction.UPSERT

    def test_note_updated_returns_upsert(self, webhook_handler):
        result = webhook_handler._determine_action("note:updated", {"id": "1"})
        assert result == SyncAction.UPSERT

    def test_item_deleted_returns_archive(self, webhook_handler):
        result = webhook_handler._determine_action("item:deleted", {"id": "1"})
        assert result == SyncAction.ARCHIVE

    def test_unknown_event_returns_none(self, webhook_handler):
        result = webhook_handler._determine_action("project:added", {"id": "1"})
        assert result is None


class TestHandleEvent:
    async def test_queues_upsert_for_item_added(self, webhook_handler, mock_publisher):
        event = TodoistWebhookEvent(
            event_name="item:added",
            event_data={"id": "task-99", "content": "Test"},
            user_id="user-1",
        )

        result = await webhook_handler.handle_event(event)

        assert result["status"] == "queued"
        assert result["task_id"] == "task-99"
        assert result["action"] == "UPSERT"
        mock_publisher.publish.assert_called_once()

    async def test_queues_archive_for_item_deleted(self, webhook_handler, mock_publisher):
        event = TodoistWebhookEvent(
            event_name="item:deleted",
            event_data={"id": "task-99"},
            user_id="user-1",
        )

        result = await webhook_handler.handle_event(event)

        assert result["status"] == "queued"
        assert result["action"] == "ARCHIVE"

    async def test_ignores_event_without_task_id(self, webhook_handler, mock_publisher):
        event = TodoistWebhookEvent(
            event_name="item:added",
            event_data={"content": "No ID here"},
            user_id="user-1",
        )

        result = await webhook_handler.handle_event(event)

        assert result["status"] == "ignored"
        assert result["reason"] == "no_task_id"
        mock_publisher.publish.assert_not_called()

    async def test_ignores_irrelevant_event(self, webhook_handler, mock_publisher):
        event = TodoistWebhookEvent(
            event_name="project:updated",
            event_data={"id": "proj-1"},
            user_id="user-1",
        )

        result = await webhook_handler.handle_event(event)

        assert result["status"] == "ignored"
        assert result["reason"] == "irrelevant_event"
        mock_publisher.publish.assert_not_called()


# ============================================================================
# ReconcileHandler tests
# ============================================================================


@pytest.fixture
def mock_todoist():
    """Mock TodoistClient."""
    client = AsyncMock()
    client.clear_caches = MagicMock()
    client.get_tasks = AsyncMock(return_value=[])
    client.get_projects = AsyncMock(return_value=[])
    client.get_active_tasks_with_label = AsyncMock(return_value=[])
    client._get_paginated = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_notion():
    """Mock NotionClient."""
    client = AsyncMock()
    client.find_project_by_todoist_id = AsyncMock(return_value=None)
    client.get_tasks_edited_since = AsyncMock(return_value=[])
    client.get_tasks_without_todoist_id = AsyncMock(return_value=[])
    client.get_all_project_pages = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_store():
    """Mock FirestoreStore."""
    store = AsyncMock()
    store.get_all_task_states = AsyncMock(return_value=[])
    store.get_all_project_states = AsyncMock(return_value=[])
    store.get_last_reconcile_time = AsyncMock(return_value=None)
    store.set_last_reconcile_time = AsyncMock()
    return store


@pytest.fixture
def reconcile_handler(mock_todoist, mock_notion, mock_store):
    """Create a ReconcileHandler with mocked dependencies."""
    with patch("app.handlers.settings") as mock_settings:
        mock_settings.auto_label_tasks = False
        mock_settings.enable_notion_to_todoist = False
        mock_settings.enable_notion_task_creation = False
        from app.handlers import ReconcileHandler

        handler = ReconcileHandler(mock_todoist, mock_notion, mock_store)
        handler.worker = AsyncMock()
        return handler


class TestReconcile:
    async def test_reconcile_with_no_tasks(
        self, reconcile_handler, mock_todoist, mock_store
    ):
        result = await reconcile_handler.reconcile()

        assert result["status"] == "completed"
        assert result["upserted"] == 0
        assert result["archived"] == 0
        mock_todoist.clear_caches.assert_called_once()

    async def test_reconcile_upserts_active_tasks(
        self, reconcile_handler, mock_todoist, mock_store
    ):
        from app.models import TodoistTask, TodoistDue

        task = TodoistTask(
            id="t-1",
            content="Do stuff",
            project_id="p-1",
            labels=["capsync"],
            priority=1,
            added_at="2025-10-01T00:00:00Z",
        )
        mock_todoist.get_active_tasks_with_label.return_value = [task]

        result = await reconcile_handler.reconcile()

        assert result["upserted"] == 1
        reconcile_handler.worker.process_message.assert_called_once()

    async def test_reconcile_archives_removed_tasks(
        self, reconcile_handler, mock_todoist, mock_store
    ):
        # Task in store but not in active tasks
        stored = TaskSyncState(
            todoist_task_id="old-task",
            payload_hash="h1",
            last_synced_at=datetime(2025, 10, 1, tzinfo=timezone.utc),
        )
        mock_store.get_all_task_states.return_value = [stored]
        mock_todoist.get_active_tasks_with_label.return_value = []

        result = await reconcile_handler.reconcile()

        assert result["archived"] == 1


class TestAutoLabelTasks:
    async def test_auto_label_disabled(self, reconcile_handler):
        count = await reconcile_handler._auto_label_tasks()
        assert count == 0

    async def test_auto_label_adds_label_to_eligible_task(
        self, reconcile_handler, mock_todoist
    ):
        from app.models import TodoistProject, TodoistTask

        with patch("app.handlers.settings") as mock_settings:
            mock_settings.auto_label_tasks = True

            task = TodoistTask(
                id="t-1",
                content="Eligible task",
                project_id="proj-1",
                labels=[],
                priority=1,
                added_at="2025-10-01T00:00:00Z",
                checked=False,
            )
            project = TodoistProject(
                id="proj-1",
                name="Real Project",
                color="blue",
                is_shared=False,
            )

            mock_todoist.get_tasks.return_value = [task]
            mock_todoist.get_projects.return_value = [project]
            mock_todoist.add_label_to_task.return_value = task

            count = await reconcile_handler._auto_label_tasks()
            assert count == 1
            mock_todoist.add_label_to_task.assert_called_once_with(
                "t-1", "capsync", []
            )

    async def test_auto_label_skips_inbox_tasks(
        self, reconcile_handler, mock_todoist
    ):
        from app.models import TodoistProject, TodoistTask

        with patch("app.handlers.settings") as mock_settings:
            mock_settings.auto_label_tasks = True

            task = TodoistTask(
                id="t-1",
                content="Inbox task",
                project_id="inbox-1",
                labels=[],
                priority=1,
                added_at="2025-10-01T00:00:00Z",
                checked=False,
            )
            inbox = TodoistProject(
                id="inbox-1",
                name="Inbox",
                color="grey",
                is_shared=False,
            )

            mock_todoist.get_tasks.return_value = [task]
            mock_todoist.get_projects.return_value = [inbox]

            count = await reconcile_handler._auto_label_tasks()
            assert count == 0
            mock_todoist.add_label_to_task.assert_not_called()

    async def test_auto_label_removes_label_from_recurring_task(
        self, reconcile_handler, mock_todoist
    ):
        from app.models import TodoistDue, TodoistProject, TodoistTask

        with patch("app.handlers.settings") as mock_settings:
            mock_settings.auto_label_tasks = True

            task = TodoistTask(
                id="t-1",
                content="Recurring task",
                project_id="proj-1",
                labels=["capsync"],
                priority=1,
                due=TodoistDue(
                    date="2025-10-15",
                    string="every day",
                    is_recurring=True,
                ),
                added_at="2025-10-01T00:00:00Z",
                checked=False,
            )
            project = TodoistProject(
                id="proj-1",
                name="Real Project",
                color="blue",
                is_shared=False,
            )

            mock_todoist.get_tasks.return_value = [task]
            mock_todoist.get_projects.return_value = [project]
            mock_todoist.remove_label_from_task.return_value = task

            count = await reconcile_handler._auto_label_tasks()
            assert count == 1
            mock_todoist.remove_label_from_task.assert_called_once_with(
                "t-1", "capsync", ["capsync"]
            )
