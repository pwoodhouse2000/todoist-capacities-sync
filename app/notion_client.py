"""Notion API client for creating and updating pages in databases."""

from typing import Any, Dict, List, Optional

from notion_client import AsyncClient
from tenacity import retry, stop_after_attempt, wait_exponential

from app.logging_setup import get_logger
from app.models import NotionProject, NotionToDo
from app.settings import settings

logger = get_logger(__name__)


class NotionClient:
    """Async client for Notion API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        tasks_database_id: Optional[str] = None,
        projects_database_id: Optional[str] = None,
    ) -> None:
        """
        Initialize Notion client.

        Args:
            api_key: Notion integration token (defaults to settings)
            tasks_database_id: Notion database ID for tasks
            projects_database_id: Notion database ID for projects
        """
        self.api_key = api_key or settings.notion_api_key
        self.tasks_db_id = tasks_database_id or settings.notion_tasks_database_id
        self.projects_db_id = projects_database_id or settings.notion_projects_database_id
        self.client = AsyncClient(auth=self.api_key)

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def create_project_page(self, project: NotionProject) -> Dict[str, Any]:
        """
        Create a project page in Notion.

        Args:
            project: NotionProject model with data

        Returns:
            Created page data from Notion
        """
        logger.info(
            "Creating Notion project page",
            extra={"project_name": project.name, "todoist_id": project.todoist_project_id},
        )

        properties = {
            "Name": {"title": [{"text": {"content": project.name}}]},
            "Todoist Project ID": {"rich_text": [{"text": {"content": project.todoist_project_id}}]},
            "Todoist URL": {"url": project.url},
            "Color": {"select": {"name": project.color}},
            "Is Shared": {"checkbox": project.is_shared},
        }

        result = await self.client.pages.create(
            parent={"database_id": self.projects_db_id},
            properties=properties,
        )

        logger.info(
            "Project page created",
            extra={"notion_page_id": result["id"], "project_name": project.name},
        )

        return result

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def create_todo_page(
        self,
        todo: NotionToDo,
        project_page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a todo page in Notion.

        Args:
            todo: NotionToDo model with data
            project_page_id: Notion page ID of the related project

        Returns:
            Created page data from Notion
        """
        logger.info(
            "Creating Notion todo page",
            extra={"title": todo.title, "todoist_id": todo.todoist_task_id},
        )

        # Build properties
        properties: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": todo.title}}]},
            "Todoist Task ID": {"rich_text": [{"text": {"content": todo.todoist_task_id}}]},
            "Todoist URL": {"url": todo.todoist_url},
            "Priority": {"select": {"name": f"P{todo.priority}"}},
            "Completed": {"checkbox": todo.completed},
        }

        # Add project relation if provided
        if project_page_id:
            properties["Project"] = {"relation": [{"id": project_page_id}]}

        # Add due date if present
        if todo.due_date:
            properties["Due Date"] = {"date": {"start": todo.due_date}}

        # Add labels as multi-select
        if todo.todoist_labels:
            properties["Labels"] = {"multi_select": [{"name": label} for label in todo.todoist_labels]}

        # Create the page
        result = await self.client.pages.create(
            parent={"database_id": self.tasks_db_id},
            properties=properties,
        )

        # Add body content if present
        if todo.body or todo.comments_markdown:
            await self._add_page_content(result["id"], todo.body, todo.comments_markdown)

        logger.info(
            "Todo page created",
            extra={"notion_page_id": result["id"], "title": todo.title},
        )

        return result

    async def _add_page_content(
        self,
        page_id: str,
        description: str,
        comments: str,
    ) -> None:
        """
        Add content blocks to a Notion page.

        Args:
            page_id: Notion page ID
            description: Task description
            comments: Comments markdown
        """
        blocks = []

        # Add description if present
        if description:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": description}}]
                },
            })

        # Add comments section if present
        if comments:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Comments"}}]
                },
            })
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": comments[:2000]}}]  # Notion limit
                },
            })

        if blocks:
            await self.client.blocks.children.append(block_id=page_id, children=blocks)

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def update_todo_page(
        self,
        page_id: str,
        todo: NotionToDo,
    ) -> Dict[str, Any]:
        """
        Update an existing todo page in Notion.

        Args:
            page_id: Notion page ID to update
            todo: NotionToDo model with updated data

        Returns:
            Updated page data from Notion
        """
        logger.info(
            "Updating Notion todo page",
            extra={"page_id": page_id, "title": todo.title},
        )

        properties: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": todo.title}}]},
            "Priority": {"select": {"name": f"P{todo.priority}"}},
            "Completed": {"checkbox": todo.completed},
        }

        # Update due date
        if todo.due_date:
            properties["Due Date"] = {"date": {"start": todo.due_date}}

        # Update labels
        if todo.todoist_labels:
            properties["Labels"] = {"multi_select": [{"name": label} for label in todo.todoist_labels]}

        result = await self.client.pages.update(page_id=page_id, properties=properties)

        logger.info("Todo page updated", extra={"page_id": page_id})

        return result

    async def find_project_by_todoist_id(self, todoist_project_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a project page by Todoist project ID.

        Args:
            todoist_project_id: Todoist project ID to search for

        Returns:
            Page data if found, None otherwise
        """
        logger.info(
            "Searching for project by Todoist ID",
            extra={"todoist_project_id": todoist_project_id},
        )

        result = await self.client.databases.query(
            database_id=self.projects_db_id,
            filter={
                "property": "Todoist Project ID",
                "rich_text": {"equals": todoist_project_id},
            },
        )

        if result["results"]:
            return result["results"][0]

        return None

    async def find_todo_by_todoist_id(self, todoist_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a todo page by Todoist task ID.

        Args:
            todoist_task_id: Todoist task ID to search for

        Returns:
            Page data if found, None otherwise
        """
        logger.info(
            "Searching for todo by Todoist ID",
            extra={"todoist_task_id": todoist_task_id},
        )

        result = await self.client.databases.query(
            database_id=self.tasks_db_id,
            filter={
                "property": "Todoist Task ID",
                "rich_text": {"equals": todoist_task_id},
            },
        )

        if result["results"]:
            return result["results"][0]

        return None

    async def archive_page(self, page_id: str) -> Dict[str, Any]:
        """
        Archive a Notion page (mark as completed and archived).

        Args:
            page_id: Notion page ID to archive

        Returns:
            Updated page data
        """
        logger.info("Archiving Notion page", extra={"page_id": page_id})

        return await self.client.pages.update(
            page_id=page_id,
            properties={"Completed": {"checkbox": True}},
            archived=True,
        )

