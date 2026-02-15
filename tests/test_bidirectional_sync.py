"""Tests for bidirectional Notion→Todoist sync."""

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import (
    ProjectSyncState,
    SyncStatus,
    TaskSyncState,
)
from app.reverse_mapper import (
    compute_notion_properties_hash,
    extract_notion_task_properties,
    notion_props_differ,
)


# ============================================================================
# reverse_mapper tests
# ============================================================================


class TestExtractNotionTaskProperties:
    """Tests for extract_notion_task_properties."""

    def test_extract_full_properties(self):
        """Extract all properties from a complete Notion page."""
        page = {
            "id": "page-123",
            "last_edited_time": "2026-02-14T10:00:00Z",
            "properties": {
                "Name": {"title": [{"text": {"content": "Buy groceries"}}]},
                "Priority": {"select": {"name": "P2"}},
                "Due Date": {"date": {"start": "2026-03-01"}},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": [{"text": {"content": "abc123"}}]},
                "Project": {"relation": [{"id": "proj-456"}]},
            },
        }

        result = extract_notion_task_properties(page)

        assert result["title"] == "Buy groceries"
        assert result["priority"] == 2
        assert result["due_date"] == "2026-03-01"
        assert result["completed"] is False
        assert result["todoist_task_id"] == "abc123"
        assert result["notion_page_id"] == "page-123"
        assert result["last_edited_time"] == "2026-02-14T10:00:00Z"
        assert result["project_notion_id"] == "proj-456"

    def test_extract_minimal_properties(self):
        """Extract properties with minimal data."""
        page = {
            "id": "page-789",
            "properties": {
                "Name": {"title": []},
                "Priority": {"select": None},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": []},
            },
        }

        result = extract_notion_task_properties(page)

        assert result["title"] == ""
        assert result["priority"] == 1  # Default
        assert result["due_date"] is None
        assert result["completed"] is False
        assert result["todoist_task_id"] == ""
        assert result["project_notion_id"] is None

    def test_extract_priority_p1(self):
        page = {
            "id": "p",
            "properties": {
                "Name": {"title": [{"text": {"content": "T"}}]},
                "Priority": {"select": {"name": "P1"}},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": []},
            },
        }
        result = extract_notion_task_properties(page)
        assert result["priority"] == 1

    def test_extract_priority_p4(self):
        page = {
            "id": "p",
            "properties": {
                "Name": {"title": [{"text": {"content": "T"}}]},
                "Priority": {"select": {"name": "P4"}},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": []},
            },
        }
        result = extract_notion_task_properties(page)
        assert result["priority"] == 4


class TestComputeNotionPropertiesHash:
    """Tests for compute_notion_properties_hash."""

    def test_deterministic_hash(self):
        """Same input produces same hash."""
        props = {"title": "Test", "priority": 2, "due_date": "2026-03-01", "completed": False}
        hash1 = compute_notion_properties_hash(props)
        hash2 = compute_notion_properties_hash(props)
        assert hash1 == hash2

    def test_different_title_different_hash(self):
        """Changing title changes hash."""
        props1 = {"title": "Task A", "priority": 1, "due_date": None, "completed": False}
        props2 = {"title": "Task B", "priority": 1, "due_date": None, "completed": False}
        assert compute_notion_properties_hash(props1) != compute_notion_properties_hash(props2)

    def test_different_priority_different_hash(self):
        """Changing priority changes hash."""
        props1 = {"title": "Test", "priority": 1, "due_date": None, "completed": False}
        props2 = {"title": "Test", "priority": 3, "due_date": None, "completed": False}
        assert compute_notion_properties_hash(props1) != compute_notion_properties_hash(props2)

    def test_different_completed_different_hash(self):
        """Changing completed changes hash."""
        props1 = {"title": "Test", "priority": 1, "due_date": None, "completed": False}
        props2 = {"title": "Test", "priority": 1, "due_date": None, "completed": True}
        assert compute_notion_properties_hash(props1) != compute_notion_properties_hash(props2)

    def test_only_sync_fields_hashed(self):
        """Extra fields don't affect hash."""
        props1 = {"title": "Test", "priority": 1, "due_date": None, "completed": False}
        props2 = {
            "title": "Test",
            "priority": 1,
            "due_date": None,
            "completed": False,
            "todoist_task_id": "abc",
            "notion_page_id": "xyz",
        }
        assert compute_notion_properties_hash(props1) == compute_notion_properties_hash(props2)


class TestNotionPropsDiffer:
    """Tests for notion_props_differ."""

    def test_no_differences(self):
        """No changes when everything matches."""
        notion_props = {"title": "Task", "priority": 2, "due_date": "2026-03-01", "completed": False}
        changes = notion_props_differ(notion_props, "Task", 2, "2026-03-01", False)
        assert changes == {}

    def test_title_changed(self):
        notion_props = {"title": "New Title", "priority": 1, "due_date": None, "completed": False}
        changes = notion_props_differ(notion_props, "Old Title", 1, None, False)
        assert changes == {"title": "New Title"}

    def test_priority_changed(self):
        notion_props = {"title": "Task", "priority": 3, "due_date": None, "completed": False}
        changes = notion_props_differ(notion_props, "Task", 1, None, False)
        assert changes == {"priority": 3}

    def test_due_date_changed(self):
        notion_props = {"title": "Task", "priority": 1, "due_date": "2026-04-01", "completed": False}
        changes = notion_props_differ(notion_props, "Task", 1, "2026-03-01", False)
        assert changes == {"due_date": "2026-04-01"}

    def test_due_date_added(self):
        notion_props = {"title": "Task", "priority": 1, "due_date": "2026-03-01", "completed": False}
        changes = notion_props_differ(notion_props, "Task", 1, None, False)
        assert changes == {"due_date": "2026-03-01"}

    def test_due_date_removed(self):
        notion_props = {"title": "Task", "priority": 1, "due_date": None, "completed": False}
        changes = notion_props_differ(notion_props, "Task", 1, "2026-03-01", False)
        assert changes == {"due_date": None}

    def test_completed_changed(self):
        notion_props = {"title": "Task", "priority": 1, "due_date": None, "completed": True}
        changes = notion_props_differ(notion_props, "Task", 1, None, False)
        assert changes == {"completed": True}

    def test_multiple_changes(self):
        notion_props = {"title": "New", "priority": 4, "due_date": "2026-05-01", "completed": True}
        changes = notion_props_differ(notion_props, "Old", 1, None, False)
        assert changes == {
            "title": "New",
            "priority": 4,
            "due_date": "2026-05-01",
            "completed": True,
        }

    def test_both_none_due_date_no_change(self):
        """Both None for due_date is not a change."""
        notion_props = {"title": "Task", "priority": 1, "due_date": None, "completed": False}
        changes = notion_props_differ(notion_props, "Task", 1, None, False)
        assert changes == {}


# ============================================================================
# Echo suppression tests
# ============================================================================


class TestEchoSuppression:
    """Test the echo suppression mechanism in pubsub_worker."""

    def test_hash_matches_skips_sync(self):
        """When notion_payload_hash matches, it's our own echo - should be skipped."""
        # Simulate what pubsub_worker stores after Todoist→Notion push
        props = {"title": "Buy milk", "priority": 2, "due_date": "2026-03-01", "completed": False}
        stored_hash = compute_notion_properties_hash(props)

        # When Notion poller sees the "edited" page, it computes the same hash
        current_hash = compute_notion_properties_hash(props)

        # They should match → skip (echo suppressed)
        assert stored_hash == current_hash

    def test_hash_differs_triggers_sync(self):
        """When hash differs, it's a genuine Notion edit - should trigger sync."""
        # Stored hash from last Todoist→Notion push
        old_props = {"title": "Buy milk", "priority": 2, "due_date": "2026-03-01", "completed": False}
        stored_hash = compute_notion_properties_hash(old_props)

        # User edits title in Notion
        new_props = {"title": "Buy groceries", "priority": 2, "due_date": "2026-03-01", "completed": False}
        current_hash = compute_notion_properties_hash(new_props)

        # They should differ → sync
        assert stored_hash != current_hash


# ============================================================================
# Integration tests for handlers
# ============================================================================


@pytest.fixture
def mock_todoist_client():
    client = AsyncMock()
    return client


@pytest.fixture
def mock_notion_client():
    client = AsyncMock()
    client.tasks_db_id = "test-tasks-db"
    client.projects_db_id = "test-projects-db"
    return client


@pytest.fixture
def mock_store():
    store = AsyncMock()
    return store


@pytest.fixture
def reconcile_handler(mock_todoist_client, mock_notion_client, mock_store):
    from app.handlers import ReconcileHandler

    handler = ReconcileHandler(mock_todoist_client, mock_notion_client, mock_store)
    return handler


class TestSyncNotionToTodoist:
    """Tests for _sync_notion_to_todoist handler method."""

    @pytest.mark.asyncio
    async def test_first_run_no_last_reconcile(self, reconcile_handler, mock_store):
        """First run with no last reconcile time sets timestamp and returns 0."""
        mock_store.get_last_reconcile_time.return_value = None

        result = await reconcile_handler._sync_notion_to_todoist()

        assert result == 0
        mock_store.set_last_reconcile_time.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_edited_pages(self, reconcile_handler, mock_store, mock_notion_client):
        """No edited pages returns 0."""
        mock_store.get_last_reconcile_time.return_value = "2026-02-14T10:00:00Z"
        mock_notion_client.get_tasks_edited_since.return_value = []
        mock_store.get_all_project_states.return_value = []

        result = await reconcile_handler._sync_notion_to_todoist()

        assert result == 0

    @pytest.mark.asyncio
    async def test_echo_suppression_skips_own_edits(
        self, reconcile_handler, mock_store, mock_notion_client
    ):
        """Pages with matching notion_payload_hash are skipped (echo suppression)."""
        props = {"title": "Test Task", "priority": 1, "due_date": None, "completed": False}
        stored_hash = compute_notion_properties_hash(props)

        mock_store.get_last_reconcile_time.return_value = "2026-02-14T10:00:00Z"
        mock_store.get_all_project_states.return_value = []

        # Notion returns a page that was just updated by our Todoist→Notion push
        page = {
            "id": "page-123",
            "last_edited_time": "2026-02-14T10:05:00Z",
            "properties": {
                "Name": {"title": [{"text": {"content": "Test Task"}}]},
                "Priority": {"select": {"name": "P1"}},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": [{"text": {"content": "task-abc"}}]},
                "Project": {"relation": []},
            },
        }
        mock_notion_client.get_tasks_edited_since.return_value = [page]

        # Firestore has matching hash
        mock_store.get_task_state.return_value = TaskSyncState(
            todoist_task_id="task-abc",
            capacities_object_id="page-123",
            payload_hash="some-hash",
            notion_payload_hash=stored_hash,
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
        )

        result = await reconcile_handler._sync_notion_to_todoist()

        # Should not update Todoist
        assert result == 0
        reconcile_handler.todoist.update_task.assert_not_called()
        reconcile_handler.todoist.complete_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_genuine_edit_pushes_to_todoist(
        self, reconcile_handler, mock_store, mock_notion_client, mock_todoist_client
    ):
        """Genuine Notion edits are pushed to Todoist."""
        # Original props stored from last push
        old_props = {"title": "Old Title", "priority": 1, "due_date": None, "completed": False}
        stored_hash = compute_notion_properties_hash(old_props)

        mock_store.get_last_reconcile_time.return_value = "2026-02-14T10:00:00Z"
        mock_store.get_all_project_states.return_value = []

        # Notion page with edited title
        page = {
            "id": "page-123",
            "last_edited_time": "2026-02-14T10:05:00Z",
            "properties": {
                "Name": {"title": [{"text": {"content": "New Title"}}]},
                "Priority": {"select": {"name": "P1"}},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": [{"text": {"content": "task-abc"}}]},
                "Project": {"relation": []},
            },
        }
        mock_notion_client.get_tasks_edited_since.return_value = [page]

        # Stored state with old hash
        mock_store.get_task_state.return_value = TaskSyncState(
            todoist_task_id="task-abc",
            capacities_object_id="page-123",
            payload_hash="old-payload-hash",
            notion_payload_hash=stored_hash,
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
        )

        # Mock Todoist task
        from app.models import TodoistTask, TodoistProject

        mock_todoist_client.get_task.return_value = TodoistTask(
            id="task-abc",
            content="Old Title",
            project_id="proj-1",
            added_at="2026-01-01T00:00:00Z",
            checked=False,
            priority=1,
        )
        mock_todoist_client.update_task.return_value = TodoistTask(
            id="task-abc",
            content="New Title",
            project_id="proj-1",
            added_at="2026-01-01T00:00:00Z",
            checked=False,
            priority=1,
        )
        mock_todoist_client.get_project.return_value = TodoistProject(
            id="proj-1", name="Test Project", color="blue",
        )
        mock_todoist_client.get_comments.return_value = []

        result = await reconcile_handler._sync_notion_to_todoist()

        assert result == 1
        mock_todoist_client.update_task.assert_called_once_with(
            "task-abc",
            content="New Title",
            priority=None,
            due_date=None,
        )

    @pytest.mark.asyncio
    async def test_completion_pushed_to_todoist(
        self, reconcile_handler, mock_store, mock_notion_client, mock_todoist_client
    ):
        """Marking task complete in Notion completes it in Todoist."""
        old_props = {"title": "Task", "priority": 1, "due_date": None, "completed": False}
        stored_hash = compute_notion_properties_hash(old_props)

        mock_store.get_last_reconcile_time.return_value = "2026-02-14T10:00:00Z"
        mock_store.get_all_project_states.return_value = []

        page = {
            "id": "page-123",
            "last_edited_time": "2026-02-14T10:05:00Z",
            "properties": {
                "Name": {"title": [{"text": {"content": "Task"}}]},
                "Priority": {"select": {"name": "P1"}},
                "Due Date": {"date": None},
                "Completed": {"checkbox": True},
                "Todoist Task ID": {"rich_text": [{"text": {"content": "task-abc"}}]},
                "Project": {"relation": []},
            },
        }
        mock_notion_client.get_tasks_edited_since.return_value = [page]

        mock_store.get_task_state.return_value = TaskSyncState(
            todoist_task_id="task-abc",
            capacities_object_id="page-123",
            payload_hash="old-hash",
            notion_payload_hash=stored_hash,
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
        )

        from app.models import TodoistTask, TodoistProject

        mock_todoist_client.get_task.return_value = TodoistTask(
            id="task-abc",
            content="Task",
            project_id="proj-1",
            added_at="2026-01-01T00:00:00Z",
            checked=False,
            priority=1,
        )
        mock_todoist_client.get_project.return_value = TodoistProject(
            id="proj-1", name="Test Project", color="blue",
        )
        mock_todoist_client.get_comments.return_value = []

        result = await reconcile_handler._sync_notion_to_todoist()

        assert result == 1
        mock_todoist_client.complete_task.assert_called_once_with("task-abc")

    @pytest.mark.asyncio
    async def test_skip_pages_without_todoist_id(
        self, reconcile_handler, mock_store, mock_notion_client
    ):
        """Pages without Todoist Task ID are skipped (handled by task creation)."""
        mock_store.get_last_reconcile_time.return_value = "2026-02-14T10:00:00Z"
        mock_store.get_all_project_states.return_value = []

        page = {
            "id": "page-new",
            "last_edited_time": "2026-02-14T10:05:00Z",
            "properties": {
                "Name": {"title": [{"text": {"content": "New from Notion"}}]},
                "Priority": {"select": None},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": []},
            },
        }
        mock_notion_client.get_tasks_edited_since.return_value = [page]

        result = await reconcile_handler._sync_notion_to_todoist()

        assert result == 0
        mock_store.get_task_state.assert_not_called()


class TestCreateTodoistTasksFromNotion:
    """Tests for _create_todoist_tasks_from_notion handler method."""

    @pytest.mark.asyncio
    async def test_no_pages_without_id(self, reconcile_handler, mock_notion_client, mock_store):
        """No pages without Todoist ID returns 0."""
        mock_notion_client.get_tasks_without_todoist_id.return_value = []
        mock_store.get_all_project_states.return_value = []

        result = await reconcile_handler._create_todoist_tasks_from_notion()

        assert result == 0

    @pytest.mark.asyncio
    async def test_create_task_from_notion(
        self, reconcile_handler, mock_notion_client, mock_todoist_client, mock_store
    ):
        """New Notion task creates a Todoist task."""
        page = {
            "id": "page-new",
            "archived": False,
            "last_edited_time": "2026-02-14T10:00:00Z",
            "properties": {
                "Name": {"title": [{"text": {"content": "Design review"}}]},
                "Priority": {"select": {"name": "P2"}},
                "Due Date": {"date": {"start": "2026-03-15"}},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": [{"id": "notion-proj-123"}]},
            },
        }
        mock_notion_client.get_tasks_without_todoist_id.return_value = [page]

        # Project mapping
        mock_store.get_all_project_states.return_value = [
            ProjectSyncState(
                todoist_project_id="todoist-proj-1",
                capacities_object_id="notion-proj-123",
                payload_hash="h",
                last_synced_at=datetime.now(),
            )
        ]

        from app.models import TodoistTask, TodoistProject

        mock_todoist_client.create_task.return_value = TodoistTask(
            id="new-task-xyz",
            content="Design review",
            project_id="todoist-proj-1",
            added_at="2026-02-14T10:00:00Z",
            checked=False,
            priority=2,
        )
        mock_todoist_client.get_project.return_value = TodoistProject(
            id="todoist-proj-1", name="My Project", color="green",
        )
        mock_todoist_client.get_comments.return_value = []

        result = await reconcile_handler._create_todoist_tasks_from_notion()

        assert result == 1

        # Verify task was created in Todoist
        mock_todoist_client.create_task.assert_called_once_with(
            content="Design review",
            project_id="todoist-proj-1",
            priority=2,
            due_date="2026-03-15",
            labels=["capsync"],
        )

        # Verify Notion page was updated with Todoist ID
        mock_notion_client.set_todoist_task_id.assert_called_once()

        # Verify Firestore state was saved
        mock_store.save_task_state.assert_called_once()
        saved_state = mock_store.save_task_state.call_args[0][0]
        assert saved_state.todoist_task_id == "new-task-xyz"
        assert saved_state.capacities_object_id == "page-new"
        assert saved_state.sync_source == "notion-created"
        assert saved_state.notion_payload_hash is not None

    @pytest.mark.asyncio
    async def test_skip_archived_pages(
        self, reconcile_handler, mock_notion_client, mock_store
    ):
        """Archived pages are skipped."""
        page = {
            "id": "page-archived",
            "archived": True,
            "properties": {
                "Name": {"title": [{"text": {"content": "Archived task"}}]},
                "Priority": {"select": None},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": [{"id": "proj-1"}]},
            },
        }
        mock_notion_client.get_tasks_without_todoist_id.return_value = [page]
        mock_store.get_all_project_states.return_value = [
            ProjectSyncState(
                todoist_project_id="tp-1",
                capacities_object_id="proj-1",
                payload_hash="h",
                last_synced_at=datetime.now(),
            )
        ]

        result = await reconcile_handler._create_todoist_tasks_from_notion()

        assert result == 0
        reconcile_handler.todoist.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_pages_without_mapped_project(
        self, reconcile_handler, mock_notion_client, mock_store
    ):
        """Pages with no mapped project are skipped."""
        page = {
            "id": "page-no-proj",
            "archived": False,
            "properties": {
                "Name": {"title": [{"text": {"content": "Orphan task"}}]},
                "Priority": {"select": None},
                "Due Date": {"date": None},
                "Completed": {"checkbox": False},
                "Todoist Task ID": {"rich_text": []},
                "Project": {"relation": [{"id": "unknown-proj"}]},
            },
        }
        mock_notion_client.get_tasks_without_todoist_id.return_value = [page]
        mock_store.get_all_project_states.return_value = []  # No project mappings

        result = await reconcile_handler._create_todoist_tasks_from_notion()

        assert result == 0
        reconcile_handler.todoist.create_task.assert_not_called()
