"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from app.models import (
    TodoistTask,
    TodoistProject,
    TodoistDue,
    NotionToDo,
    NotionProject,
    SyncAction,
    SyncStatus,
    PubSubMessage,
)


class TestTodoistModels:
    """Test Todoist data models."""

    def test_todoist_task_minimal(self):
        """Test creating a task with minimal required fields."""
        task = TodoistTask(
            id="123",
            content="Test task",
            project_id="456",
            added_at="2025-10-09T12:00:00Z",
        )
        assert task.id == "123"
        assert task.content == "Test task"
        assert task.description == ""  # Default value
        assert task.labels == []  # Default value
        assert task.priority == 1  # Default value

    def test_todoist_task_with_due_date(self):
        """Test task with due date information."""
        task = TodoistTask(
            id="123",
            content="Test task",
            project_id="456",
            added_at="2025-10-09T12:00:00Z",
            due=TodoistDue(
                date="2025-10-15",
                string="Oct 15",
                timezone="America/Los_Angeles",
                is_recurring=False,
            ),
        )
        assert task.due is not None
        assert task.due.date == "2025-10-15"
        assert task.due.timezone == "America/Los_Angeles"

    def test_todoist_project_required_fields(self):
        """Test project with all required fields."""
        project = TodoistProject(
            id="789",
            name="My Project",
            color="blue",
        )
        assert project.id == "789"
        assert project.name == "My Project"
        assert project.is_shared is False  # Default value


class TestNotionModels:
    """Test Notion data models."""

    def test_notion_todo_creation(self):
        """Test creating a Notion ToDo."""
        todo = NotionToDo(
            title="Test",
            todoist_task_id="123",
            todoist_url="https://app.todoist.com/app/task/123",
            todoist_project_id="456",
            todoist_project_name="Project",
            created_at="2025-10-09T12:00:00Z",
            updated_at="2025-10-09T12:00:00Z",
        )
        assert todo.title == "Test"
        assert todo.body == ""  # Default value
        assert todo.completed is False  # Default value
        assert todo.sync_status == "ok"  # Default value

    def test_notion_project_creation(self):
        """Test creating a Notion Project."""
        project = NotionProject(
            todoist_project_id="123",
            name="Test Project",
            url="https://app.todoist.com/app/project/123",
            color="red",
        )
        assert project.todoist_project_id == "123"
        assert project.name == "Test Project"
        assert project.is_shared is False  # Default value


class TestSyncModels:
    """Test sync-related models."""

    def test_sync_action_enum(self):
        """Test SyncAction enum values."""
        assert SyncAction.UPSERT == "UPSERT"
        assert SyncAction.ARCHIVE == "ARCHIVE"

    def test_sync_status_enum(self):
        """Test SyncStatus enum values."""
        assert SyncStatus.OK == "ok"
        assert SyncStatus.ARCHIVED == "archived"
        assert SyncStatus.ERROR == "error"

    def test_pubsub_message_minimal(self):
        """Test creating a PubSub message."""
        message = PubSubMessage(
            action=SyncAction.UPSERT,
            todoist_task_id="12345",
        )
        assert message.action == SyncAction.UPSERT
        assert message.todoist_task_id == "12345"
        assert message.snapshot is None  # Optional field

    def test_pubsub_message_with_snapshot(self):
        """Test PubSub message with task snapshot."""
        message = PubSubMessage(
            action=SyncAction.ARCHIVE,
            todoist_task_id="12345",
            snapshot={"content": "Test", "id": "12345"},
        )
        assert message.snapshot is not None
        assert message.snapshot["content"] == "Test"


class TestModelValidation:
    """Test model validation rules."""

    def test_todoist_task_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            TodoistTask(
                id="123",
                # Missing 'content'
                project_id="456",
                added_at="2025-10-09T12:00:00Z",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("content",) for e in errors)

    def test_model_extra_fields_ignored(self):
        """Test that extra fields are handled appropriately."""
        # Pydantic should ignore extra fields with ConfigDict(extra="ignore")
        task = TodoistTask(
            id="123",
            content="Test",
            project_id="456",
            added_at="2025-10-09T12:00:00Z",
            extra_field="ignored",  # This should be ignored
        )
        assert task.id == "123"
        assert not hasattr(task, "extra_field")

