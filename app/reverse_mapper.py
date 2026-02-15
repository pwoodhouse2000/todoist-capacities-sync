"""Reverse mapper: Extract Notion page properties for Notion→Todoist sync."""

import hashlib
import json
from typing import Any, Dict, List, Optional

from app.logging_setup import get_logger

logger = get_logger(__name__)


def extract_notion_task_properties(page: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract sync-relevant properties from a Notion task page.

    Extracts only the fields that are bidirectionally synced:
    - title, priority, due_date, completed

    Also extracts identifiers needed for sync:
    - todoist_task_id, notion_page_id, last_edited_time

    Args:
        page: Notion page object from API

    Returns:
        Dict with extracted properties
    """
    props = page.get("properties", {})

    # Extract title
    title_prop = props.get("Name", {}).get("title", [])
    title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

    # Extract priority (P1, P2, P3, P4 → 1, 2, 3, 4)
    priority_prop = props.get("Priority", {}).get("select")
    priority = 1
    if priority_prop and priority_prop.get("name"):
        try:
            priority = int(priority_prop["name"].replace("P", ""))
        except (ValueError, TypeError):
            priority = 1

    # Extract due date
    due_date_prop = props.get("Due Date", {}).get("date")
    due_date = None
    if due_date_prop and due_date_prop.get("start"):
        due_date = due_date_prop["start"]

    # Extract completed checkbox
    completed = props.get("Completed", {}).get("checkbox", False)

    # Extract Todoist Task ID
    todoist_id_prop = props.get("Todoist Task ID", {}).get("rich_text", [])
    todoist_task_id = todoist_id_prop[0].get("text", {}).get("content", "") if todoist_id_prop else ""

    # Extract project relation
    project_prop = props.get("Project", {}).get("relation", [])
    project_notion_id = project_prop[0].get("id") if project_prop else None

    return {
        "title": title,
        "priority": priority,
        "due_date": due_date,
        "completed": completed,
        "todoist_task_id": todoist_task_id,
        "notion_page_id": page.get("id", ""),
        "last_edited_time": page.get("last_edited_time", ""),
        "project_notion_id": project_notion_id,
    }


def compute_notion_properties_hash(props: Dict[str, Any]) -> str:
    """
    Compute a hash of the sync-relevant Notion properties.

    Only includes fields that are bidirectionally synced.
    Used for echo suppression: when Todoist→Notion push updates a page,
    we store this hash. When the Notion poller sees the page was "edited",
    it compares hashes and skips if they match (our own echo).

    Args:
        props: Dict from extract_notion_task_properties()

    Returns:
        SHA-256 hex digest of sync-relevant properties
    """
    # Only hash the fields that are bidirectionally synced
    sync_fields = {
        "title": props.get("title", ""),
        "priority": props.get("priority", 1),
        "due_date": props.get("due_date"),
        "completed": props.get("completed", False),
    }

    serialized = json.dumps(sync_fields, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def notion_props_differ(
    notion_props: Dict[str, Any],
    todoist_title: str,
    todoist_priority: int,
    todoist_due_date: Optional[str],
    todoist_completed: bool,
) -> Dict[str, Any]:
    """
    Compare Notion properties against current Todoist state.

    Returns a dict of fields that differ (empty dict if no differences).

    Args:
        notion_props: Dict from extract_notion_task_properties()
        todoist_title: Current Todoist task title
        todoist_priority: Current Todoist task priority
        todoist_due_date: Current Todoist due date (YYYY-MM-DD or None)
        todoist_completed: Current Todoist completion state

    Returns:
        Dict of changed fields with their Notion values, e.g.:
        {"title": "New Title", "priority": 3}
    """
    changes = {}

    if notion_props.get("title", "") != todoist_title:
        changes["title"] = notion_props["title"]

    if notion_props.get("priority", 1) != todoist_priority:
        changes["priority"] = notion_props["priority"]

    # Normalize due dates for comparison
    notion_due = notion_props.get("due_date")
    if notion_due != todoist_due_date:
        # Only flag if they're genuinely different
        # (both None is not a change)
        if notion_due or todoist_due_date:
            changes["due_date"] = notion_due

    if notion_props.get("completed", False) != todoist_completed:
        changes["completed"] = notion_props["completed"]

    return changes
