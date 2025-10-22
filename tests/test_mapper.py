"""Tests for data mapping logic."""

from datetime import datetime

import pytest

from app.mapper import map_project_to_notion, map_task_to_todo
from app.models import TodoistComment, TodoistDue, TodoistProject, TodoistTask


def test_map_task_to_todo_basic() -> None:
    """Test basic task mapping."""
    task = TodoistTask(
        id="123",
        content="Test task",
        description="Test description",
        project_id="proj-1",
        labels=["@capsync", "work"],
        priority=2,
        url="https://todoist.com/showTask?id=123",
        created_at="2025-01-01T00:00:00Z",
    )

    project = TodoistProject(
        id="proj-1",
        name="Work Project",
        color="blue",
        url="https://todoist.com/app/project/proj-1",
    )

    comments = []

    todo = map_task_to_todo(task, project, comments)

    assert todo.title == "Test task"
    assert todo.body == "Test description"
    assert todo.todoist_task_id == "123"
    assert todo.todoist_project_name == "Work Project"
    assert todo.todoist_labels == ["@capsync", "work"]
    assert todo.priority == 2
    assert todo.sync_status == "ok"


def test_map_task_with_due_date() -> None:
    """Test task mapping with due date."""
    task = TodoistTask(
        id="123",
        content="Task with due",
        project_id="proj-1",
        due=TodoistDue(
            date="2025-12-31",
            string="Dec 31",
            timezone="America/Los_Angeles",
        ),
        url="https://todoist.com/showTask?id=123",
        created_at="2025-01-01T00:00:00Z",
    )

    project = TodoistProject(
        id="proj-1",
        name="Test Project",
        color="red",
        url="https://todoist.com/app/project/proj-1",
    )

    todo = map_task_to_todo(task, project, [])

    assert todo.due_date == "2025-12-31"
    assert todo.due_timezone == "America/Los_Angeles"
    assert todo.due_time is None


def test_map_task_with_due_datetime() -> None:
    """Test task mapping with due date and time."""
    task = TodoistTask(
        id="123",
        content="Task with datetime",
        project_id="proj-1",
        due=TodoistDue(
            date="2025-12-31T15:30:00",
            string="Dec 31 at 3:30 PM",
            timezone="America/New_York",
        ),
        url="https://todoist.com/showTask?id=123",
        created_at="2025-01-01T00:00:00Z",
    )

    project = TodoistProject(
        id="proj-1",
        name="Test Project",
        color="green",
        url="https://todoist.com/app/project/proj-1",
    )

    todo = map_task_to_todo(task, project, [])

    assert todo.due_date == "2025-12-31"
    assert todo.due_time == "15:30:00"
    assert todo.due_timezone == "America/New_York"


def test_map_task_with_comments() -> None:
    """Test task mapping with comments."""
    task = TodoistTask(
        id="123",
        content="Task with comments",
        project_id="proj-1",
        url="https://todoist.com/showTask?id=123",
        created_at="2025-01-01T00:00:00Z",
    )

    project = TodoistProject(
        id="proj-1",
        name="Test Project",
        color="purple",
        url="https://todoist.com/app/project/proj-1",
    )

    comments = [
        TodoistComment(
            id="c1",
            task_id="123",
            content="First comment",
            posted_at="2025-01-02T10:00:00Z",
        ),
        TodoistComment(
            id="c2",
            task_id="123",
            content="Second comment",
            posted_at="2025-01-03T11:00:00Z",
        ),
    ]

    todo = map_task_to_todo(task, project, comments)

    assert "First comment" in todo.comments_markdown
    assert "Second comment" in todo.comments_markdown
    assert "2025-01-02T10:00:00Z" in todo.comments_markdown


def test_map_project_to_capacities() -> None:
    """Test project mapping."""
    project = TodoistProject(
        id="proj-1",
        name="My Project",
        color="orange",
        is_shared=True,
        url="https://todoist.com/app/project/proj-1",
    )

    capacities_project = map_project_to_notion(project)

    assert capacities_project.todoist_project_id == "proj-1"
    assert capacities_project.name == "My Project"
    assert capacities_project.color == "orange"
    assert capacities_project.is_shared is True
    assert capacities_project.url == project.url
    assert capacities_project.last_synced_at is not None

