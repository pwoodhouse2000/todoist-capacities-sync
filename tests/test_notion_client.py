"""Integration tests for Notion API client (with mocking)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.notion_client import NotionClient
from app.models import NotionToDo, NotionProject


@pytest.fixture
def notion_client():
    """Create a NotionClient instance for testing."""
    with patch("app.notion_client.settings") as mock_settings:
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_tasks_database_id = "test_tasks_db"
        mock_settings.notion_projects_database_id = "test_projects_db"
        mock_settings.max_retries = 3
        mock_settings.retry_delay = 0.1  # Faster for tests
        
        client = NotionClient(
            api_key="test_key",
            tasks_database_id="test_tasks_db",
            projects_database_id="test_projects_db",
        )
        yield client


@pytest.mark.asyncio
class TestNotionClientProjectOperations:
    """Test Notion client project operations."""

    async def test_create_project_page(self, notion_client, sample_notion_project):
        """Test creating a project page in Notion."""
        mock_response = {
            "id": "page123",
            "properties": {"Name": {"title": [{"text": {"content": "Test Project"}}]}},
        }
        
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            result = await notion_client.create_project_page(sample_notion_project)
            
            assert result["id"] == "page123"
            mock_create.assert_awaited_once()
            call_args = mock_create.call_args
            assert call_args.kwargs["parent"]["database_id"] == "test_projects_db"

    async def test_find_project_by_todoist_id_found(self, notion_client):
        """Test finding an existing project."""
        mock_response = {
            "results": [
                {"id": "page123", "properties": {}}
            ]
        }
        
        with patch.object(notion_client.client.databases, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            
            result = await notion_client.find_project_by_todoist_id("123")
            
            assert result is not None
            assert result["id"] == "page123"
            mock_query.assert_awaited_once()

    async def test_find_project_by_todoist_id_not_found(self, notion_client):
        """Test finding a non-existent project."""
        mock_response = {"results": []}
        
        with patch.object(notion_client.client.databases, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            
            result = await notion_client.find_project_by_todoist_id("nonexistent")
            
            assert result is None


@pytest.mark.asyncio
class TestNotionClientTodoOperations:
    """Test Notion client todo operations."""

    async def test_create_todo_page(self, notion_client, sample_notion_todo):
        """Test creating a todo page in Notion."""
        mock_response = {
            "id": "page456",
            "properties": {"Name": {"title": [{"text": {"content": "Test task"}}]}},
        }
        
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            result = await notion_client.create_todo_page(sample_notion_todo, project_page_id="proj123")
            
            assert result["id"] == "page456"
            mock_create.assert_awaited_once()
            call_args = mock_create.call_args
            
            # Verify project relation was added
            properties = call_args.kwargs["properties"]
            assert "Project" in properties
            assert properties["Project"]["relation"][0]["id"] == "proj123"

    async def test_create_todo_page_without_project(self, notion_client, sample_notion_todo):
        """Test creating a todo without project relation."""
        mock_response = {"id": "page456"}
        
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            result = await notion_client.create_todo_page(sample_notion_todo, project_page_id=None)
            
            call_args = mock_create.call_args
            properties = call_args.kwargs["properties"]
            assert "Project" not in properties

    async def test_create_todo_page_with_content(self, notion_client, sample_notion_todo):
        """Test creating a todo with body content and comments."""
        sample_notion_todo.body = "Task description"
        sample_notion_todo.comments_markdown = "Comment 1\n\nComment 2"
        
        mock_response = {"id": "page456"}
        
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create, \
             patch.object(notion_client.client.blocks.children, "append", new_callable=AsyncMock) as mock_append:
            mock_create.return_value = mock_response
            
            await notion_client.create_todo_page(sample_notion_todo)
            
            # Verify content was added
            mock_append.assert_awaited_once()
            call_args = mock_append.call_args
            blocks = call_args.kwargs["children"]
            assert len(blocks) > 0

    async def test_update_todo_page(self, notion_client, sample_notion_todo):
        """Test updating an existing todo page."""
        mock_response = {"id": "page456"}
        
        with patch.object(notion_client.client.pages, "update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_response
            
            result = await notion_client.update_todo_page("page456", sample_notion_todo)
            
            assert result["id"] == "page456"
            mock_update.assert_awaited_once()
            call_args = mock_update.call_args
            assert call_args.kwargs["page_id"] == "page456"

    async def test_find_todo_by_todoist_id(self, notion_client):
        """Test finding a todo by Todoist task ID."""
        mock_response = {
            "results": [
                {"id": "page456", "properties": {}}
            ]
        }
        
        with patch.object(notion_client.client.databases, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            
            result = await notion_client.find_todo_by_todoist_id("task123")
            
            assert result is not None
            assert result["id"] == "page456"

    async def test_archive_page(self, notion_client):
        """Test archiving a page."""
        mock_response = {"id": "page456", "archived": True}
        
        with patch.object(notion_client.client.pages, "update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_response
            
            result = await notion_client.archive_page("page456")
            
            assert result["archived"] is True
            call_args = mock_update.call_args
            assert call_args.kwargs["archived"] is True


@pytest.mark.asyncio
class TestNotionClientErrorHandling:
    """Test error handling in Notion client."""

    async def test_retry_on_failure(self, notion_client, sample_notion_project):
        """Test that operations retry on failure."""
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create:
            # First two calls fail, third succeeds
            mock_create.side_effect = [
                Exception("Temporary error"),
                Exception("Another error"),
                {"id": "page123"},
            ]
            
            result = await notion_client.create_project_page(sample_notion_project)
            
            assert result["id"] == "page123"
            assert mock_create.await_count == 3

    async def test_max_retries_exceeded(self, notion_client, sample_notion_project):
        """Test that retries stop after max attempts."""
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Persistent error")
            
            with pytest.raises(Exception, match="Persistent error"):
                await notion_client.create_project_page(sample_notion_project)
            
            assert mock_create.await_count == 3  # max_retries from fixture

    async def test_comment_truncation(self, notion_client, sample_notion_todo):
        """Test that long comments are truncated."""
        # Create a comment longer than 2000 chars
        long_comment = "x" * 3000
        sample_notion_todo.comments_markdown = long_comment
        
        mock_response = {"id": "page456"}
        
        with patch.object(notion_client.client.pages, "create", new_callable=AsyncMock) as mock_create, \
             patch.object(notion_client.client.blocks.children, "append", new_callable=AsyncMock) as mock_append:
            mock_create.return_value = mock_response
            
            await notion_client.create_todo_page(sample_notion_todo)
            
            # Verify content was truncated
            call_args = mock_append.call_args
            blocks = call_args.kwargs["children"]
            comment_block = next((b for b in blocks if b["type"] == "paragraph"), None)
            if comment_block:
                content = comment_block["paragraph"]["rich_text"][0]["text"]["content"]
                assert len(content) <= 2000

