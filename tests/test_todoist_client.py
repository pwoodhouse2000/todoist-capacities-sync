"""Integration tests for Todoist API client (with mocking)."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.todoist_client import TodoistClient
from app.models import TodoistTask, TodoistProject


@pytest.fixture
def todoist_client():
    """Create a TodoistClient instance for testing."""
    with patch("app.todoist_client.settings") as mock_settings:
        mock_settings.todoist_oauth_token = "test_token"
        mock_settings.todoist_api_base_url = "https://api.todoist.com/rest/v2"
        mock_settings.max_retries = 3
        mock_settings.retry_delay = 0.1
        mock_settings.request_timeout = 30
        
        client = TodoistClient(
            api_token="test_token",
            base_url="https://api.todoist.com/rest/v2",
        )
        yield client


@pytest.mark.asyncio
class TestTodoistClientTaskOperations:
    """Test Todoist client task operations."""

    async def test_get_task(self, todoist_client, mock_todoist_api_response):
        """Test fetching a single task."""
        mock_response = httpx.Response(200, json=mock_todoist_api_response)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            task = await todoist_client.get_task("12345678")
            
            assert isinstance(task, TodoistTask)
            assert task.id == "12345678"
            assert task.content == "Test task"
            mock_get.assert_awaited_once()

    async def test_get_tasks(self, todoist_client, mock_todoist_api_response):
        """Test fetching all tasks."""
        mock_response = httpx.Response(200, json=[mock_todoist_api_response])
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            tasks = await todoist_client.get_tasks()
            
            assert len(tasks) == 1
            assert isinstance(tasks[0], TodoistTask)
            assert tasks[0].id == "12345678"

    async def test_get_tasks_with_label_filter(self, todoist_client):
        """Test fetching tasks filtered by label."""
        mock_response = httpx.Response(200, json=[])
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            tasks = await todoist_client.get_tasks(label="@capsync")
            
            # Verify label was passed as parameter
            call_args = mock_get.call_args
            assert call_args.kwargs["params"]["label"] == "@capsync"

    async def test_get_active_tasks_with_label(self, todoist_client, mock_todoist_api_response):
        """Test fetching active tasks with specific label."""
        # Create multiple tasks, some with capsync label
        tasks_data = [
            {**mock_todoist_api_response, "id": "1", "labels": ["capsync", "work"]},
            {**mock_todoist_api_response, "id": "2", "labels": ["personal"]},
            {**mock_todoist_api_response, "id": "3", "labels": ["@capsync"]},
        ]
        mock_response = httpx.Response(200, json=tasks_data)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            tasks = await todoist_client.get_active_tasks_with_label("@capsync")
            
            # Should return 2 tasks (one with @capsync, one with capsync)
            assert len(tasks) == 1  # Only exact match "@capsync"


@pytest.mark.asyncio
class TestTodoistClientProjectOperations:
    """Test Todoist client project operations."""

    async def test_get_project(self, todoist_client):
        """Test fetching a single project."""
        mock_project_data = {
            "id": "98765",
            "name": "Test Project",
            "color": "blue",
            "url": "https://todoist.com/app/project/98765",
        }
        mock_response = httpx.Response(200, json=mock_project_data)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            project = await todoist_client.get_project("98765")
            
            assert isinstance(project, TodoistProject)
            assert project.id == "98765"
            assert project.name == "Test Project"

    async def test_get_projects(self, todoist_client):
        """Test fetching all projects."""
        mock_response = httpx.Response(200, json=[
            {"id": "1", "name": "Project 1", "color": "red", "url": "https://todoist.com/app/project/1"},
            {"id": "2", "name": "Project 2", "color": "blue", "url": "https://todoist.com/app/project/2"},
        ])
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            projects = await todoist_client.get_projects()
            
            assert len(projects) == 2
            assert all(isinstance(p, TodoistProject) for p in projects)


@pytest.mark.asyncio
class TestTodoistClientCommentOperations:
    """Test Todoist client comment operations."""

    async def test_get_comments(self, todoist_client):
        """Test fetching task comments."""
        mock_comments_data = [
            {
                "id": "111",
                "task_id": "12345",
                "content": "Comment 1",
                "posted_at": "2025-10-09T12:00:00Z",
            },
            {
                "id": "222",
                "task_id": "12345",
                "content": "Comment 2",
                "posted_at": "2025-10-09T13:00:00Z",
            },
        ]
        mock_response = httpx.Response(200, json=mock_comments_data)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            comments = await todoist_client.get_comments("12345")
            
            assert len(comments) == 2
            assert comments[0].content == "Comment 1"
            assert comments[1].content == "Comment 2"


@pytest.mark.asyncio
class TestTodoistClientErrorHandling:
    """Test error handling in Todoist client."""

    async def test_retry_on_failure(self, todoist_client, mock_todoist_api_response):
        """Test that operations retry on transient failures."""
        mock_response = httpx.Response(200, json=mock_todoist_api_response)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # First two calls fail, third succeeds
            mock_get.side_effect = [
                httpx.TimeoutException("Timeout"),
                httpx.TimeoutException("Another timeout"),
                mock_response,
            ]
            
            task = await todoist_client.get_task("12345678")
            
            assert task.id == "12345678"
            assert mock_get.await_count == 3

    async def test_http_error_raised(self, todoist_client):
        """Test that HTTP errors are properly raised."""
        mock_response = httpx.Response(404, json={"error": "Not found"})
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            with pytest.raises(httpx.HTTPStatusError):
                await todoist_client.get_task("nonexistent")

    async def test_invalid_json_handling(self, todoist_client):
        """Test handling of invalid JSON responses."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = httpx.Response(200, content=b"Invalid JSON")
            mock_get.return_value = mock_response
            
            with pytest.raises(Exception):  # Should raise JSON decode error
                await todoist_client.get_task("12345678")


@pytest.mark.asyncio
class TestTodoistClientHeaders:
    """Test that correct headers are sent."""

    async def test_authorization_header(self, todoist_client, mock_todoist_api_response):
        """Test that Bearer token is included in requests."""
        mock_response = httpx.Response(200, json=mock_todoist_api_response)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            await todoist_client.get_task("12345678")
            
            call_args = mock_get.call_args
            headers = call_args.kwargs["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test_token"

    async def test_content_type_header(self, todoist_client, mock_todoist_api_response):
        """Test that Content-Type header is set."""
        mock_response = httpx.Response(200, json=mock_todoist_api_response)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            await todoist_client.get_task("12345678")
            
            call_args = mock_get.call_args
            headers = call_args.kwargs["headers"]
            assert headers["Content-Type"] == "application/json"

