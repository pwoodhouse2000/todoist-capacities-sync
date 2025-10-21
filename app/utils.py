"""Utility functions for the sync service."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import orjson

from app.settings import settings


def compute_payload_hash(data: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash of a payload for idempotency checks.

    Args:
        data: Dictionary to hash

    Returns:
        SHA-256 hash as hex string
    """
    # Use orjson for deterministic JSON serialization
    json_bytes = orjson.dumps(
        data,
        option=orjson.OPT_SORT_KEYS | orjson.OPT_SERIALIZE_NUMPY,
    )
    return hashlib.sha256(json_bytes).hexdigest()


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO format timestamp string to datetime."""
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))


def has_capsync_label(labels: list[str]) -> bool:
    """
    Check if task has the @capsync label.

    Args:
        labels: List of label names from Todoist

    Returns:
        True if @capsync label is present
    """
    return "@capsync" in labels or "capsync" in labels


def format_markdown_comments(comments: List[Dict[str, Any]]) -> str:
    """
    Format Todoist comments as markdown.

    Args:
        comments: List of comment dictionaries with 'content', 'posted_at' fields

    Returns:
        Formatted markdown string
    """
    if not comments:
        return ""

    formatted_parts = []
    for comment in comments:
        content = comment.get("content", "")
        posted_at = comment.get("posted_at", "")

        # Format: **Author** · Timestamp
        # Content
        formatted_parts.append(f"**Comment** · {posted_at}\n\n{content}")

    return "\n\n---\n\n".join(formatted_parts)


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a dictionary."""
    return data.get(key, default)


def build_todoist_task_url(task_id: str) -> str:
    """Build a Todoist task URL."""
    return f"https://todoist.com/showTask?id={task_id}"


def build_todoist_project_url(project_id: str) -> str:
    """Build a Todoist project URL."""
    return f"https://todoist.com/app/project/{project_id}"


def extract_para_area(labels: List[str]) -> Optional[str]:
    """
    Extract PARA area from labels.
    
    Looks for labels matching PARA areas (HOME, HEALTH, PROSPER, WORK, etc.)
    Handles both plain labels and emoji-suffixed labels (e.g., "PROSPER 📁")
    Also handles multi-word areas like "PERSONAL & FAMILY 📁"
    
    Args:
        labels: List of label names from Todoist
        
    Returns:
        Area name if found, None otherwise
    """
    from app.settings import settings
    
    if not settings.enable_para_areas or not labels:
        return None
    
    # Check each label against defined PARA areas
    for label in labels:
        # Remove emoji by stripping all non-ASCII characters at the end
        # This handles "PERSONAL & FAMILY 📁" -> "PERSONAL & FAMILY"
        clean_label = label.strip()
        # Remove trailing emoji/special characters
        while clean_label and ord(clean_label[-1]) > 127:
            clean_label = clean_label[:-1].strip()
        
        # Check if it matches any PARA area (case-insensitive)
        for area in settings.para_area_labels:
            if clean_label.upper() == area.upper():
                return area
    
    return None


def extract_person_labels(labels: List[str]) -> List[str]:
    """
    Extract person labels from Todoist labels.
    
    Person labels are identified by the 👤 emoji suffix.
    Examples: "DougD 👤", "VarshaA 👤", "JamesH 👤"
    
    Args:
        labels: List of label names from Todoist
        
    Returns:
        List of person names (without emoji)
    """
    from app.settings import settings
    
    if not settings.enable_people_matching or not labels:
        return []
    
    person_labels = []
    for label in labels:
        if settings.person_label_emoji in label:
            # Extract the name before the emoji
            person_name = label.replace(settings.person_label_emoji, "").strip()
            person_labels.append(person_name)
    
    return person_labels


def get_area_label_from_parent_project(parent_project_name: Optional[str]) -> Optional[str]:
    """
    Try to match a parent project name to a PARA area label.
    
    This enables automatic inheritance of Area labels from parent projects.
    Matching is case-insensitive and strips emoji.
    
    Examples:
        "PROSPER 📂" -> "PROSPER"
        "HEALTH" -> "HEALTH"
        "PERSONAL & FAMILY" -> "PERSONAL & FAMILY"
    
    Args:
        parent_project_name: Name of parent project
        
    Returns:
        Area label name if match found, None otherwise
    """
    from app.settings import settings
    
    if not parent_project_name or not settings.enable_para_areas:
        return None
    
    # Clean the parent project name (remove emoji)
    clean_name = parent_project_name.strip()
    while clean_name and ord(clean_name[-1]) > 127:
        clean_name = clean_name[:-1].strip()
    
    # Try to match against defined PARA areas (case-insensitive)
    for area in settings.para_area_labels:
        if clean_name.upper() == area.upper():
            return area
    
    return None


def strip_notion_backlink(description: str) -> str:
    """
    Strip Notion backlink from task description to avoid circular sync.
    
    Removes any line containing "notion.so" links that we add as backlinks.
    Example: "🔗 [View in Notion](https://notion.so/...)"
    
    Args:
        description: Task description text
        
    Returns:
        Description with Notion backlink removed
    """
    if not description:
        return description
    
    # Split by lines and filter out lines containing notion.so
    lines = description.split('\n')
    filtered_lines = [line for line in lines if 'notion.so' not in line.lower()]
    
    # Join back and strip trailing whitespace
    result = '\n'.join(filtered_lines).strip()
    
    return result


def should_auto_label_task(task_project_id: str, is_recurring: bool, is_inbox: bool) -> bool:
    """
    Determine if a task should automatically get the capsync label.
    
    Tasks are auto-labeled if they are:
    - Not in the Inbox
    - Not recurring
    - Not completed (caller should pre-filter completed tasks)
    
    Args:
        task_project_id: Task's project ID
        is_recurring: Whether the task has a recurring due date
        is_inbox: Whether the task's project is the Inbox
        
    Returns:
        True if task should be auto-labeled
    """
    # Don't label tasks in Inbox
    if is_inbox:
        return False
    
    # Don't label recurring tasks
    if is_recurring:
        return False
    
    return True

