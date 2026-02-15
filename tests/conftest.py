"""Pytest configuration and shared fixtures."""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from app.models import (
    TodoistTask,
    TodoistProject,
    TodoistComment,
    TodoistDue,
    NotionToDo,
    NotionProject,
)


@pytest.fixture
def sample_todoist_task() -> TodoistTask:
    """Sample Todoist task for testing."""
    return TodoistTask(
        id="12345678",
        content="Test task",
        description="Task description",
        project_id="98765",
        section_id=None,
        parent_id=None,
        labels=["capsync", "work"],
        priority=3,
        due=TodoistDue(
            date="2025-10-15",
            string="Oct 15",
            timezone="America/Los_Angeles",
            is_recurring=False,
        ),
        added_at="2025-10-01T10:00:00Z",
        checked=False,
        completed_at=None,
    )


@pytest.fixture
def sample_todoist_project() -> TodoistProject:
    """Sample Todoist project for testing."""
    return TodoistProject(
        id="98765",
        name="Test Project",
        color="blue",
        is_shared=False,
    )


@pytest.fixture
def sample_todoist_comments() -> list[TodoistComment]:
    """Sample Todoist comments for testing."""
    return [
        TodoistComment(
            id="111",
            task_id="12345678",
            content="First comment",
            posted_at="2025-10-02T12:00:00Z",
        ),
        TodoistComment(
            id="222",
            task_id="12345678",
            content="Second comment with **markdown**",
            posted_at="2025-10-03T14:00:00Z",
        ),
    ]


@pytest.fixture
def sample_notion_todo() -> NotionToDo:
    """Sample Notion ToDo for testing."""
    return NotionToDo(
        title="Test task",
        body="Task description",
        todoist_task_id="12345678",
        todoist_url="https://todoist.com/showTask?id=12345678",
        todoist_project_id="98765",
        todoist_project_name="Test Project",
        todoist_labels=["capsync", "work"],
        priority=3,
        due_date="2025-10-15",
        due_time=None,
        due_timezone="America/Los_Angeles",
        completed=False,
        completed_at=None,
        created_at="2025-10-01T10:00:00Z",
        updated_at="2025-10-09T18:00:00Z",
    )


@pytest.fixture
def sample_notion_project() -> NotionProject:
    """Sample Notion Project for testing."""
    return NotionProject(
        todoist_project_id="98765",
        name="Test Project",
        url="https://todoist.com/app/project/98765",
        is_shared=False,
        color="blue",
        last_synced_at="2025-10-09T18:00:00Z",
    )


@pytest.fixture
def mock_notion_page_response() -> Dict[str, Any]:
    """Mock Notion API page creation response."""
    return {
        "id": "28889c4a-21dd-8179-bbef-cc12e5c1e145",
        "created_time": "2025-10-09T18:00:00.000Z",
        "last_edited_time": "2025-10-09T18:00:00.000Z",
        "object": "page",
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {"content": "Test task"},
                    }
                ]
            },
        },
    }


@pytest.fixture
def mock_todoist_api_response() -> Dict[str, Any]:
    """Mock Todoist API task response."""
    return {
        "id": "12345678",
        "content": "Test task",
        "description": "Task description",
        "project_id": "98765",
        "labels": ["capsync", "work"],
        "priority": 3,
        "due": {
            "date": "2025-10-15",
            "string": "Oct 15",
            "timezone": "America/Los_Angeles",
            "is_recurring": False,
        },
        "added_at": "2025-10-01T10:00:00Z",
        "checked": False,
    }

