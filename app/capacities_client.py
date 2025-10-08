"""Capacities API client for creating and updating objects."""

from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.logging_setup import get_logger
from app.models import CapacitiesProject, CapacitiesToDo
from app.settings import settings

logger = get_logger(__name__)


class CapacitiesClient:
    """Async HTTP client for Capacities API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        space_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Initialize Capacities client.

        Args:
            api_key: Capacities API key (defaults to settings)
            space_id: Capacities space ID (defaults to settings)
            base_url: API base URL (defaults to settings)
        """
        self.api_key = api_key or settings.capacities_api_key
        self.space_id = space_id or settings.capacities_space_id
        self.base_url = base_url or settings.capacities_api_base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict:
        """
        Make HTTP request to Capacities API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint
            json_data: JSON body data
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            logger.info(
                "Capacities API request",
                extra={
                    "method": method,
                    "endpoint": endpoint,
                    "has_data": json_data is not None,
                },
            )
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_data,
                params=params,
            )
            response.raise_for_status()
            return response.json() if response.content else {}

    async def get_space_info(self) -> Dict[str, Any]:
        """
        Get space information including structures and property definitions.

        Returns:
            Space info dictionary with structures
        """
        logger.info("Fetching Capacities space info")
        return await self._request("GET", "/space-info", params={"spaceId": self.space_id})

    async def create_object(
        self,
        structure_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new object in Capacities.

        Note: The exact endpoint and payload structure may need adjustment
        based on the actual Capacities API documentation.

        Args:
            structure_id: The structure/object type ID
            properties: Object properties

        Returns:
            Created object data including ID
        """
        payload = {
            "spaceId": self.space_id,
            "structureId": structure_id,
            "properties": properties,
        }

        logger.info(
            "Creating Capacities object",
            extra={"structure_id": structure_id},
        )

        # TODO: Verify exact endpoint - may be /save-object, /create-object, or similar
        return await self._request("POST", "/save-object", json_data=payload)

    async def update_object(
        self,
        object_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing object in Capacities.

        Args:
            object_id: Capacities object ID
            properties: Updated properties

        Returns:
            Updated object data
        """
        payload = {
            "spaceId": self.space_id,
            "objectId": object_id,
            "properties": properties,
        }

        logger.info(
            "Updating Capacities object",
            extra={"object_id": object_id},
        )

        # TODO: Verify exact endpoint
        return await self._request("POST", "/save-object", json_data=payload)

    async def search_objects(
        self,
        structure_id: str,
        query: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for objects by structure and optional query.

        Args:
            structure_id: Filter by structure ID
            query: Additional search criteria

        Returns:
            List of matching objects
        """
        params = {
            "spaceId": self.space_id,
            "structureId": structure_id,
        }
        if query:
            params.update(query)

        logger.info(
            "Searching Capacities objects",
            extra={"structure_id": structure_id},
        )

        # TODO: Verify exact endpoint
        return await self._request("GET", "/search", params=params)

    async def find_object_by_property(
        self,
        structure_id: str,
        property_name: str,
        property_value: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find an object by a specific property value.

        Args:
            structure_id: Structure ID to search within
            property_name: Property name to match
            property_value: Property value to match

        Returns:
            Object data if found, None otherwise
        """
        objects = await self.search_objects(
            structure_id=structure_id,
            query={property_name: property_value},
        )
        return objects[0] if objects else None

    async def upsert_todo(
        self,
        todo: CapacitiesToDo,
        existing_object_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a @ToDo object in Capacities.

        Args:
            todo: CapacitiesToDo model with data
            existing_object_id: If provided, update instead of create

        Returns:
            Created/updated object data
        """
        # Convert model to Capacities properties format
        properties = self._todo_to_properties(todo)

        if existing_object_id:
            return await self.update_object(existing_object_id, properties)
        else:
            # Structure ID for @ToDo (custom structure - need to get from space-info)
            # Using placeholder - will need to be determined dynamically
            return await self.create_object("todo_structure_id", properties)

    async def upsert_project(
        self,
        project: CapacitiesProject,
        existing_object_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a Project object in Capacities.

        Args:
            project: CapacitiesProject model with data
            existing_object_id: If provided, update instead of create

        Returns:
            Created/updated object data
        """
        properties = self._project_to_properties(project)

        if existing_object_id:
            return await self.update_object(existing_object_id, properties)
        else:
            # Structure ID for Project (custom structure)
            return await self.create_object("project_structure_id", properties)

    def _todo_to_properties(self, todo: CapacitiesToDo) -> Dict[str, Any]:
        """
        Convert CapacitiesToDo model to Capacities properties format.

        Args:
            todo: CapacitiesToDo model

        Returns:
            Properties dictionary for Capacities API
        """
        # TODO: Adjust based on actual Capacities API property format
        # This is a best-guess structure
        return {
            "title": todo.title,
            "body": todo.body,
            "todoist_task_id": todo.todoist_task_id,
            "todoist_url": todo.todoist_url,
            "todoist_project_id": todo.todoist_project_id,
            "todoist_project_name": todo.todoist_project_name,
            "todoist_labels": todo.todoist_labels,
            "priority": todo.priority,
            "due_date": todo.due_date,
            "due_time": todo.due_time,
            "due_timezone": todo.due_timezone,
            "completed": todo.completed,
            "completed_at": todo.completed_at,
            "parent_id": todo.parent_id,
            "section_id": todo.section_id,
            "section_name": todo.section_name,
            "comments_markdown": todo.comments_markdown,
            "created_at": todo.created_at,
            "updated_at": todo.updated_at,
            "last_synced_at": todo.last_synced_at,
            "sync_status": todo.sync_status,
            "error_note": todo.error_note,
        }

    def _project_to_properties(self, project: CapacitiesProject) -> Dict[str, Any]:
        """
        Convert CapacitiesProject model to Capacities properties format.

        Args:
            project: CapacitiesProject model

        Returns:
            Properties dictionary for Capacities API
        """
        return {
            "todoist_project_id": project.todoist_project_id,
            "name": project.name,
            "url": project.url,
            "is_shared": project.is_shared,
            "color": project.color,
            "last_synced_at": project.last_synced_at,
        }

