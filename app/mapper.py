"""Data mapping logic from Todoist to Capacities."""

from datetime import datetime
from typing import List, Optional

from app.logging_setup import get_logger
from app.models import (
    CapacitiesProject,
    CapacitiesToDo,
    TodoistComment,
    TodoistProject,
    TodoistTask,
)
from app.utils import format_markdown_comments, get_current_timestamp

logger = get_logger(__name__)


def map_task_to_todo(
    task: TodoistTask,
    project: TodoistProject,
    comments: List[TodoistComment],
    section_name: Optional[str] = None,
) -> CapacitiesToDo:
    """
    Map a Todoist task to a Capacities @ToDo object.

    Args:
        task: Todoist task
        project: Todoist project the task belongs to
        comments: List of task comments
        section_name: Section name if task is in a section

    Returns:
        CapacitiesToDo object ready for sync
    """
    logger.info(
        "Mapping Todoist task to Capacities ToDo",
        extra={"task_id": task.id, "content": task.content},
    )

    # Build body with description
    body = task.description if task.description else ""

    # Parse due date/time
    due_date = None
    due_time = None
    due_timezone = None

    if task.due:
        due_date = task.due.date
        due_timezone = task.due.timezone

        # Check if it includes time (has 'T' in date string)
        if "T" in task.due.date:
            # Split date and time
            date_part, time_part = task.due.date.split("T")
            due_date = date_part
            due_time = time_part

    # Format comments
    comments_markdown = format_markdown_comments(
        [{"content": c.content, "posted_at": c.posted_at} for c in comments]
    )

    # Current timestamp
    now = get_current_timestamp()

    return CapacitiesToDo(
        title=task.content,
        body=body,
        todoist_task_id=task.id,
        todoist_url=task.url,
        todoist_project_id=task.project_id,
        todoist_project_name=project.name,
        todoist_labels=task.labels,
        priority=task.priority,
        due_date=due_date,
        due_time=due_time,
        due_timezone=due_timezone,
        completed=task.is_completed,
        completed_at=task.completed_at,
        parent_id=task.parent_id,
        section_id=task.section_id,
        section_name=section_name,
        comments_markdown=comments_markdown,
        created_at=task.created_at,
        updated_at=now,
        last_synced_at=now,
        sync_status="ok",
    )


def map_project_to_capacities(project: TodoistProject) -> CapacitiesProject:
    """
    Map a Todoist project to a Capacities Project object.

    Args:
        project: Todoist project

    Returns:
        CapacitiesProject object
    """
    logger.info(
        "Mapping Todoist project to Capacities Project",
        extra={"project_id": project.id, "project_name": project.name},
    )

    return CapacitiesProject(
        todoist_project_id=project.id,
        name=project.name,
        url=project.url,
        is_shared=project.is_shared,
        color=project.color,
        last_synced_at=get_current_timestamp(),
    )


def create_archived_todo(task: TodoistTask, project: TodoistProject) -> CapacitiesToDo:
    """
    Create an archived version of a ToDo (for tasks with @capsync removed).

    Args:
        task: Todoist task
        project: Todoist project

    Returns:
        CapacitiesToDo with archived status
    """
    logger.info(
        "Creating archived ToDo",
        extra={"task_id": task.id},
    )

    now = get_current_timestamp()

    return CapacitiesToDo(
        title=task.content,
        body=task.description,
        todoist_task_id=task.id,
        todoist_url=task.url,
        todoist_project_id=task.project_id,
        todoist_project_name=project.name,
        todoist_labels=task.labels,
        priority=task.priority,
        completed=True,  # Mark as completed when archived
        completed_at=now,
        created_at=task.created_at,
        updated_at=now,
        last_synced_at=now,
        sync_status="archived",
    )

