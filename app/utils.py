"""Utility functions for the sync service."""

import hashlib
from datetime import datetime, timezone
from typing import Any

import orjson

from app.settings import settings


def compute_payload_hash(data: dict[str, Any]) -> str:
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


def format_markdown_comments(comments: list[dict[str, Any]]) -> str:
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


def safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a dictionary."""
    return data.get(key, default)


def build_todoist_task_url(task_id: str) -> str:
    """Build a Todoist task URL."""
    return f"https://todoist.com/showTask?id={task_id}"


def build_todoist_project_url(project_id: str) -> str:
    """Build a Todoist project URL."""
    return f"https://todoist.com/app/project/{project_id}"

