"""Todoist API client for fetching tasks, projects, sections, and comments."""

from typing import Any, Dict, List, Optional, Union

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.logging_setup import get_logger
from app.models import TodoistComment, TodoistProject, TodoistSection, TodoistTask
from app.settings import settings

logger = get_logger(__name__)


class TodoistClient:
    """Async HTTP client for Todoist REST API v2."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Initialize Todoist client.

        Args:
            api_token: Todoist OAuth token (defaults to settings)
            base_url: API base URL (defaults to settings)
        """
        self.api_token = api_token or settings.todoist_oauth_token
        self.base_url = base_url or settings.todoist_api_base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Union[Dict, List]:
        """
        Make GET request to Todoist API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/tasks")
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            logger.info("Todoist GET request", extra={"endpoint": endpoint, "params": params})
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10),
    )
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict:
        """
        Make POST request to Todoist API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/tasks/123")
            data: JSON data to send

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            logger.info("Todoist POST request", extra={"endpoint": endpoint})
            response = await client.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()

    async def get_task(self, task_id: str) -> TodoistTask:
        """
        Fetch a single task by ID.

        Args:
            task_id: Todoist task ID

        Returns:
            TodoistTask object
        """
        logger.info("Fetching Todoist task", extra={"task_id": task_id})
        data = await self._get(f"/tasks/{task_id}")
        return TodoistTask(**data)

    async def get_tasks(self, label: Optional[str] = None) -> List[TodoistTask]:
        """
        Fetch all tasks, optionally filtered by label.

        Args:
            label: Filter by label name (e.g., "@capsync")

        Returns:
            List of TodoistTask objects
        """
        params = {}
        if label:
            params["label"] = label

        logger.info("Fetching Todoist tasks", extra={"label": label})
        data = await self._get("/tasks", params=params)
        return [TodoistTask(**task) for task in data]

    async def get_project(self, project_id: str) -> TodoistProject:
        """
        Fetch a single project by ID.

        Args:
            project_id: Todoist project ID

        Returns:
            TodoistProject object
        """
        logger.info("Fetching Todoist project", extra={"project_id": project_id})
        data = await self._get(f"/projects/{project_id}")
        return TodoistProject(**data)

    async def get_projects(self) -> List[TodoistProject]:
        """
        Fetch all projects.

        Returns:
            List of TodoistProject objects
        """
        logger.info("Fetching all Todoist projects")
        data = await self._get("/projects")
        return [TodoistProject(**project) for project in data]

    async def get_section(self, section_id: str) -> TodoistSection:
        """
        Fetch a single section by ID.

        Args:
            section_id: Todoist section ID

        Returns:
            TodoistSection object
        """
        logger.info("Fetching Todoist section", extra={"section_id": section_id})
        data = await self._get(f"/sections/{section_id}")
        return TodoistSection(**data)

    async def get_sections(self, project_id: Optional[str] = None) -> List[TodoistSection]:
        """
        Fetch sections, optionally filtered by project.

        Args:
            project_id: Filter by project ID

        Returns:
            List of TodoistSection objects
        """
        params = {}
        if project_id:
            params["project_id"] = project_id

        logger.info("Fetching Todoist sections", extra={"project_id": project_id})
        data = await self._get("/sections", params=params)
        return [TodoistSection(**section) for section in data]

    async def get_comments(self, task_id: str) -> List[TodoistComment]:
        """
        Fetch all comments for a task.

        Args:
            task_id: Todoist task ID

        Returns:
            List of TodoistComment objects
        """
        logger.info("Fetching Todoist comments", extra={"task_id": task_id})
        data = await self._get("/comments", params={"task_id": task_id})
        return [TodoistComment(**comment) for comment in data]

    async def get_active_tasks_with_label(self, label: str = "capsync") -> List[TodoistTask]:
        """
        Fetch all active tasks with the specified label.

        Args:
            label: Label to filter by (default: "capsync")

        Returns:
            List of TodoistTask objects
        """
        logger.info("Fetching active tasks with label", extra={"label": label})
        # Note: Todoist API doesn't support direct label filtering in v2
        # We need to fetch all tasks and filter client-side
        # Check for both "@capsync" and "capsync" to handle both label formats
        all_tasks = await self.get_tasks()
        return [task for task in all_tasks if label in task.labels or f"@{label}" in task.labels]

    async def update_task_description(self, task_id: str, new_description: str) -> TodoistTask:
        """
        Update a task's description.

        Args:
            task_id: Todoist task ID
            new_description: New description text

        Returns:
            Updated TodoistTask object
        """
        logger.info(
            "Updating Todoist task description",
            extra={"task_id": task_id, "description_length": len(new_description)},
        )
        data = await self._post(f"/tasks/{task_id}", {"description": new_description})
        return TodoistTask(**data)

