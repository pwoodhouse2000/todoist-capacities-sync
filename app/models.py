"""Pydantic models for Todoist and Capacities data structures."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Todoist Models
# ============================================================================


class TodoistDue(BaseModel):
    """Todoist due date information."""

    date: str  # YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    string: str  # Human-readable date string
    timezone: Optional[str] = None
    is_recurring: bool = False


class TodoistTask(BaseModel):
    """Todoist task object."""

    id: str
    content: str
    description: str = ""
    project_id: str
    section_id: Optional[str] = None
    parent_id: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    priority: int = 1  # 1-4
    due: Optional[TodoistDue] = None
    url: str
    created_at: str
    is_completed: bool = False
    completed_at: Optional[str] = None


class TodoistProject(BaseModel):
    """Todoist project object."""

    id: str
    name: str
    color: str
    is_shared: bool = False
    url: str


class TodoistSection(BaseModel):
    """Todoist section object."""

    id: str
    name: str
    project_id: str


class TodoistComment(BaseModel):
    """Todoist comment object."""

    id: str
    task_id: str
    content: str
    posted_at: str


# ============================================================================
# Notion Models
# ============================================================================


class NotionToDo(BaseModel):
    """Notion page for a ToDo item."""

    # Core fields
    title: str
    body: str = ""  # Description

    # Todoist identifiers
    todoist_task_id: str
    todoist_url: str
    todoist_project_id: str
    todoist_project_name: str

    # Metadata
    todoist_labels: list[str] = Field(default_factory=list)
    priority: int = 1
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    due_timezone: Optional[str] = None

    # State
    completed: bool = False
    completed_at: Optional[str] = None

    # Hierarchy
    parent_id: Optional[str] = None
    section_id: Optional[str] = None
    section_name: Optional[str] = None

    # Comments
    comments_markdown: str = ""

    # Sync metadata
    created_at: str
    updated_at: str
    last_synced_at: Optional[str] = None
    sync_status: str = "ok"  # ok | archived | error
    error_note: Optional[str] = None


class NotionProject(BaseModel):
    """Notion page for a Project."""

    todoist_project_id: str
    name: str
    url: str
    is_shared: bool = False
    color: str
    last_synced_at: Optional[str] = None


# ============================================================================
# Sync State Models (stored in Firestore)
# ============================================================================


class SyncStatus(str, Enum):
    """Sync status enum."""

    OK = "ok"
    ARCHIVED = "archived"
    ERROR = "error"


class TaskSyncState(BaseModel):
    """Task sync state stored in Firestore."""

    todoist_task_id: str
    capacities_object_id: Optional[str] = None
    payload_hash: str
    last_synced_at: datetime
    sync_status: SyncStatus = SyncStatus.OK
    error_message: Optional[str] = None


class ProjectSyncState(BaseModel):
    """Project sync state stored in Firestore."""

    todoist_project_id: str
    capacities_object_id: Optional[str] = None
    payload_hash: str
    last_synced_at: datetime


# ============================================================================
# Pub/Sub Message Models
# ============================================================================


class SyncAction(str, Enum):
    """Sync action types."""

    UPSERT = "UPSERT"
    ARCHIVE = "ARCHIVE"


class PubSubMessage(BaseModel):
    """Pub/Sub message format for sync jobs."""

    action: SyncAction
    todoist_task_id: str
    snapshot: Optional[dict[str, Any]] = None  # Optional task snapshot to avoid re-fetch


# ============================================================================
# Webhook Models
# ============================================================================


class TodoistWebhookEvent(BaseModel):
    """Todoist webhook event payload."""

    event_name: str  # e.g., "item:added", "item:updated", "item:completed"
    event_data: dict[str, Any]
    user_id: str
    version: str = "9"

