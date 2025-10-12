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
        areas_database_id: Optional[str] = None,
        people_database_id: Optional[str] = None,
    ) -> None:
        """
        Initialize Notion client.

        Args:
            api_key: Notion integration token (defaults to settings)
            tasks_database_id: Notion database ID for tasks
            projects_database_id: Notion database ID for projects
            areas_database_id: Notion database ID for PARA areas
            people_database_id: Notion database ID for people
        """
        self.api_key = api_key or settings.notion_api_key
        self.tasks_db_id = tasks_database_id or settings.notion_tasks_database_id
        self.projects_db_id = projects_database_id or settings.notion_projects_database_id
        self.areas_db_id = areas_database_id or settings.notion_areas_database_id
        self.people_db_id = people_database_id or settings.notion_people_database_id
        self.client = AsyncClient(auth=self.api_key)

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def create_project_page(
        self, 
        project: NotionProject, 
        area_page_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a project page in Notion.

        Args:
            project: NotionProject model with data
            area_page_id: Optional AREAS page ID for PARA method

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
        
        # Add AREAS relation if provided
        if area_page_id:
            properties["AREAS"] = {"relation": [{"id": area_page_id}]}

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
        area_page_id: Optional[str] = None,
        people_page_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a todo page in Notion.

        Args:
            todo: NotionToDo model with data
            project_page_id: Notion page ID of the related project
            area_page_id: Optional AREAS page ID for PARA method
            people_page_ids: Optional list of People page IDs for person assignments

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

        # Add AREAS relation if provided (PARA method)
        if area_page_id:
            properties["AREAS"] = {"relation": [{"id": area_page_id}]}

        # Add People relations if provided
        if people_page_ids:
            properties["People"] = {"relation": [{"id": pid} for pid in people_page_ids]}

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
        area_page_id: Optional[str] = None,
        people_page_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing todo page in Notion.

        Args:
            page_id: Notion page ID to update
            todo: NotionToDo model with updated data
            area_page_id: Optional AREAS page ID for PARA method
            people_page_ids: Optional list of People page IDs for person assignments

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

        # Update AREAS relation if provided
        if area_page_id:
            properties["AREAS"] = {"relation": [{"id": area_page_id}]}

        # Update People relations if provided
        if people_page_ids:
            properties["People"] = {"relation": [{"id": pid} for pid in people_page_ids]}

        result = await self.client.pages.update(page_id=page_id, properties=properties)

        # Note: We don't update body content on updates to preserve manual edits in Notion
        # Description is only synced on initial task creation

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

    async def find_area_by_name(self, area_name: str) -> Optional[Dict[str, Any]]:
        """
        Find an area page by name in the AREAS database.

        Args:
            area_name: Area name (e.g., "PROSPER", "HOME")

        Returns:
            Page dict if found, None otherwise
        """
        if not self.areas_db_id:
            return None
            
        logger.info("Searching for area in AREAS database", extra={"area_name": area_name})

        response = await self.client.databases.query(
            database_id=self.areas_db_id,
            filter={
                "property": "Name",
                "title": {"equals": area_name},
            },
        )

        results = response.get("results", [])
        if results:
            logger.info(
                "Found existing area page",
                extra={"area_name": area_name, "page_id": results[0]["id"]},
            )
            return results[0]

        return None

    async def create_area_page(self, area_name: str) -> Dict[str, Any]:
        """
        Create an area page in the AREAS database.

        Args:
            area_name: Area name (e.g., "PROSPER", "HOME")

        Returns:
            Created page data
        """
        if not self.areas_db_id:
            raise ValueError("AREAS database ID not configured")
            
        logger.info("Creating area page", extra={"area_name": area_name})

        properties = {
            "Name": {"title": [{"text": {"content": area_name}}]},
        }

        result = await self.client.pages.create(
            parent={"database_id": self.areas_db_id},
            properties=properties,
        )

        logger.info(
            "Area page created",
            extra={"area_name": area_name, "page_id": result["id"]},
        )

        return result

    async def ensure_area_exists(self, area_name: str) -> Optional[str]:
        """
        Ensure an area page exists, create if needed.

        Args:
            area_name: Area name (e.g., "PROSPER", "HOME")

        Returns:
            Area page ID, or None if AREAS database not configured
        """
        if not self.areas_db_id:
            return None
            
        # Try to find existing area
        existing_area = await self.find_area_by_name(area_name)
        if existing_area:
            return existing_area["id"]

        # Create new area
        new_area = await self.create_area_page(area_name)
        return new_area["id"]

    async def find_person_by_name(self, person_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a person page by name in the People database.
        
        Uses fuzzy matching to handle variations like:
        - "DougD" matches "Doug Diego"
        - "VarshaA" matches "Varsha"
        
        Args:
            person_name: Person name from Todoist label (e.g., "DougD", "VarshaA")
            
        Returns:
            Person page dict if found, None otherwise
        """
        if not self.people_db_id:
            return None
            
        logger.info(
            "Searching for person in People database",
            extra={"person_name": person_name},
        )
        
        # Query all people with pagination (we'll do fuzzy matching client-side)
        results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            query_params = {
                "database_id": self.people_db_id,
                "page_size": 100,
            }
            if start_cursor:
                query_params["start_cursor"] = start_cursor
                
            response = await self.client.databases.query(**query_params)
            results.extend(response.get("results", []))
            
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")
        
        logger.info(
            "Fetched all people from database",
            extra={"person_name": person_name, "total_people": len(results)},
        )
        
        # Try exact match first
        for page in results:
            title_prop = page.get("properties", {}).get("Name", {})
            if title_prop and "title" in title_prop and title_prop["title"]:
                page_name = title_prop["title"][0]["text"]["content"]
                
                # Exact match (case-insensitive)
                if page_name.lower() == person_name.lower():
                    logger.info(
                        "Found person (exact match)",
                        extra={"label": person_name, "notion_name": page_name, "page_id": page["id"]},
                    )
                    return page
        
        # Try fuzzy matching - check if label is contained in or contains the page name
        for page in results:
            title_prop = page.get("properties", {}).get("Name", {})
            if title_prop and "title" in title_prop and title_prop["title"]:
                page_name = title_prop["title"][0]["text"]["content"]
                
                # Fuzzy match: "DougD" matches "Doug Diego"
                label_lower = person_name.lower()
                name_lower = page_name.lower()
                
                # Check if label starts with page name or vice versa
                if (label_lower in name_lower or name_lower in label_lower or
                    label_lower.startswith(name_lower.split()[0]) or
                    name_lower.startswith(label_lower)):
                    logger.info(
                        "Found person (fuzzy match)",
                        extra={"label": person_name, "notion_name": page_name, "page_id": page["id"]},
                    )
                    return page
        
        logger.info(
            "No matching person found",
            extra={"person_name": person_name},
        )
        return None

    async def match_people(self, person_names: List[str]) -> List[str]:
        """
        Match person names to People database pages.
        
        Args:
            person_names: List of person names from Todoist labels
            
        Returns:
            List of Notion page IDs for matched people
        """
        if not self.people_db_id or not person_names:
            return []
        
        matched_page_ids = []
        for person_name in person_names:
            person_page = await self.find_person_by_name(person_name)
            if person_page:
                matched_page_ids.append(person_page["id"])
        
        return matched_page_ids

