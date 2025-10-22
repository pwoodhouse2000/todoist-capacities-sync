"""End-to-end regression tests for the sync workflow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.mapper import map_task_to_todo, map_project_to_notion
from app.pubsub_worker import SyncWorker
from app.models import PubSubMessage, SyncAction, TodoistTask, TodoistProject, TodoistComment


@pytest.mark.asyncio
class TestEndToEndSyncWorkflow:
    """Test the complete sync workflow from Todoist to Notion."""

    @pytest.fixture
    def mock_todoist_client(self, sample_todoist_task, sample_todoist_project, sample_todoist_comments):
        """Mock Todoist client with pre-configured responses."""
        mock_client = AsyncMock()
        mock_client.get_task.return_value = sample_todoist_task
        mock_client.get_project.return_value = sample_todoist_project
        mock_client.get_comments.return_value = sample_todoist_comments
        return mock_client

    @pytest.fixture
    def mock_notion_client(self, mock_notion_page_response):
        """Mock Notion client with pre-configured responses."""
        mock_client = AsyncMock()
        mock_client.find_project_by_todoist_id.return_value = None  # Project doesn't exist
        mock_client.create_project_page.return_value = {"id": "proj_page_id"}
        mock_client.find_todo_by_todoist_id.return_value = None  # Task doesn't exist
        mock_client.create_todo_page.return_value = mock_notion_page_response
        return mock_client

    @pytest.fixture
    def mock_store(self):
        """Mock Firestore store."""
        mock_store = AsyncMock()
        mock_store.get_task_state.return_value = None  # No existing state
        mock_store.get_project_state.return_value = None
        mock_store.save_task_state.return_value = None
        mock_store.save_project_state.return_value = None
        return mock_store

    @pytest.fixture
    def sync_worker(self, mock_todoist_client, mock_notion_client, mock_store):
        """Create a SyncWorker instance with mocked dependencies."""
        return SyncWorker(mock_todoist_client, mock_notion_client, mock_store)

    async def test_complete_sync_new_task(
        self,
        sync_worker,
        mock_todoist_client,
        mock_notion_client,
        mock_store,
    ):
        """Test syncing a brand new task from Todoist to Notion."""
        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="12345678",
        )

        # Execute the sync
        await sync_worker.process_message(message)

        # Verify the complete workflow
        # 1. Task fetched from Todoist
        mock_todoist_client.get_task.assert_awaited_once_with("12345678")
        
        # 2. Project and comments fetched
        mock_todoist_client.get_project.assert_awaited_once()
        mock_todoist_client.get_comments.assert_awaited_once_with("12345678")
        
        # 3. Project created in Notion
        mock_notion_client.find_project_by_todoist_id.assert_awaited_once()
        mock_notion_client.create_project_page.assert_awaited_once()
        
        # 4. Task created in Notion
        mock_notion_client.find_todo_by_todoist_id.assert_awaited_once_with("12345678")
        mock_notion_client.create_todo_page.assert_awaited_once()
        
        # 5. State saved to Firestore
        mock_store.save_project_state.assert_awaited_once()
        mock_store.save_task_state.assert_awaited_once()

    async def test_sync_existing_task_update(
        self,
        sync_worker,
        mock_todoist_client,
        mock_notion_client,
        mock_store,
    ):
        """Test updating an existing task."""
        # Simulate existing Notion page
        existing_page = {"id": "existing_page_id"}
        mock_notion_client.find_todo_by_todoist_id.return_value = existing_page

        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="12345678",
        )

        await sync_worker.process_message(message)

        # Verify update was called instead of create
        mock_notion_client.update_todo_page.assert_awaited_once_with(
            "existing_page_id",
            unittest.mock.ANY,  # The NotionToDo object
            None,  # area_page_id
            [],    # people_page_ids
            project_page_id="proj_page_id",
        )
        mock_notion_client.create_todo_page.assert_not_awaited()

    async def test_sync_task_without_capsync_label(
        self,
        sync_worker,
        mock_todoist_client,
        mock_notion_client,
        sample_todoist_task,
    ):
        """Test that tasks without @capsync label are skipped."""
        # Remove capsync label
        sample_todoist_task.labels = ["work", "personal"]
        mock_todoist_client.get_task.return_value = sample_todoist_task

        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="12345678",
        )

        await sync_worker.process_message(message)

        # Verify nothing was created in Notion
        mock_notion_client.create_project_page.assert_not_awaited()
        mock_notion_client.create_todo_page.assert_not_awaited()

    async def test_sync_archive_task(
        self,
        sync_worker,
        mock_todoist_client,
        mock_notion_client,
        mock_store,
    ):
        """Test archiving a task."""
        from app.models import TaskSyncState, SyncStatus
        
        # Simulate existing sync state
        existing_state = TaskSyncState(
            todoist_task_id="12345678",
            capacities_object_id="notion_page_id",
            payload_hash="somehash",
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
        )
        mock_store.get_task_state.return_value = existing_state

        message = PubSubMessage(
            action=SyncAction.ARCHIVE,
            todoist_task_id="12345678",
        )

        await sync_worker.process_message(message)

        # Verify archive was called
        mock_notion_client.archive_page.assert_awaited_once_with("notion_page_id")
        mock_store.mark_task_archived.assert_awaited_once()

    async def test_idempotency_unchanged_task(
        self,
        sync_worker,
        mock_store,
        sample_todoist_task,
    ):
        """Test that unchanged tasks are not re-synced (idempotency)."""
        from app.models import TaskSyncState, SyncStatus
        from app.utils import compute_payload_hash
        from app.mapper import map_task_to_todo

        # Create the task data
        mock_project = MagicMock()
        mock_project.name = "Test Project"
        todo = map_task_to_todo(sample_todoist_task, mock_project, [], None)
        
        # Simulate existing state with same hash
        existing_state = TaskSyncState(
            todoist_task_id="12345678",
            capacities_object_id="notion_page_id",
            payload_hash=compute_payload_hash(todo.model_dump()),
            last_synced_at=datetime.now(),
            sync_status=SyncStatus.OK,
        )
        mock_store.get_task_state.return_value = existing_state

        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="12345678",
        )

        # Mock get_project to avoid errors
        with patch.object(sync_worker.todoist, 'get_project', new_callable=AsyncMock) as mock_get_project:
            mock_get_project.return_value = mock_project
            with patch.object(sync_worker.todoist, 'get_comments', new_callable=AsyncMock) as mock_get_comments:
                mock_get_comments.return_value = []
                
                await sync_worker.process_message(message)

        # Verify nothing was updated (idempotent)
        # Save should not be called since task unchanged
        assert mock_store.save_task_state.await_count == 0


@pytest.mark.asyncio
class TestMapperIntegration:
    """Test the mapping layer integration."""

    def test_complete_task_mapping(
        self,
        sample_todoist_task,
        sample_todoist_project,
        sample_todoist_comments,
    ):
        """Test mapping a complete Todoist task to Notion ToDo."""
        todo = map_task_to_todo(
            sample_todoist_task,
            sample_todoist_project,
            sample_todoist_comments,
            section_name="My Section",
        )

        # Verify all fields were mapped correctly
        assert todo.title == sample_todoist_task.content
        assert todo.body == sample_todoist_task.description
        assert todo.todoist_task_id == sample_todoist_task.id
        assert todo.todoist_project_name == sample_todoist_project.name
        assert todo.section_name == "My Section"
        assert len(todo.todoist_labels) == 2
        assert "First comment" in todo.comments_markdown
        assert "Second comment" in todo.comments_markdown

    def test_project_mapping(self, sample_todoist_project):
        """Test mapping a Todoist project to Notion Project."""
        project = map_project_to_notion(sample_todoist_project)

        assert project.todoist_project_id == sample_todoist_project.id
        assert project.name == sample_todoist_project.name
        assert project.url == sample_todoist_project.url
        assert project.color == sample_todoist_project.color


@pytest.mark.asyncio
class TestErrorRecovery:
    """Test error handling and recovery."""

    async def test_task_not_found_in_todoist(
        self,
        sync_worker,
        mock_todoist_client,
        mock_store,
    ):
        """Test handling of tasks that no longer exist in Todoist."""
        import httpx
        
        # Simulate 404 from Todoist
        mock_todoist_client.get_task.side_effect = httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="nonexistent",
        )

        # Should handle gracefully and log error
        await sync_worker.process_message(message)
        
        # Verify error was tracked
        mock_store.mark_task_error.assert_awaited_once()

    async def test_notion_api_error(
        self,
        sync_worker,
        mock_notion_client,
        mock_store,
    ):
        """Test handling of Notion API errors."""
        # Simulate Notion API error
        mock_notion_client.create_todo_page.side_effect = Exception("Notion API error")

        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="12345678",
        )

        await sync_worker.process_message(message)

        # Verify error was logged
        mock_store.mark_task_error.assert_awaited_once()


# Add unittest.mock import for ANY matcher
import unittest.mock

