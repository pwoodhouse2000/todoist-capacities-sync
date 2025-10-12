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
        # Remove emoji and extra characters, get just the text
        clean_label = label.split()[0].strip().upper()
        
        # Check if it matches any PARA area
        for area in settings.para_area_labels:
            if clean_label == area.upper() or label.upper() == area.upper():
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

