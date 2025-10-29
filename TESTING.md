# Testing Guide

This document provides comprehensive information about testing the Todoist-Notion Sync service.

## 📋 Table of Contents

- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Writing Tests](#writing-tests)
- [Coverage](#coverage)
- [CI/CD](#cicd)

## 🏗️ Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── test_utils.py            # Unit tests for utility functions
├── test_models.py           # Pydantic model validation tests
├── test_mapper.py           # Data mapping/transformation tests
├── test_todoist_client.py   # Todoist API client tests (mocked)
├── test_notion_client.py    # Notion API client tests (mocked)
└── test_end_to_end.py       # Complete workflow integration tests
```

## 🚀 Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Or with poetry (if using poetry)
poetry install --with test
```

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with detailed output
pytest -vv

# Run specific test file
pytest tests/test_utils.py

# Run specific test class
pytest tests/test_utils.py::TestExtractParaAreas

# Run specific test function
pytest tests/test_utils.py::TestExtractParaAreas::test_multiple_areas
```

### Test Categories

Tests are organized by markers:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only end-to-end tests
pytest -m e2e

# Run all except e2e tests
pytest -m "not e2e"
```

### Coverage Reports

```bash
# Run tests with coverage
pytest --cov=app

# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View HTML report
open htmlcov/index.html

# Generate terminal coverage report with missing lines
pytest --cov=app --cov-report=term-missing

# Set minimum coverage threshold (fail if below)
pytest --cov=app --cov-fail-under=80
```

### Fast Testing

```bash
# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Stop at first failure
pytest -x

# Run last failed tests only
pytest --lf

# Run failed tests first, then rest
pytest --ff
```

## 📦 Test Categories

### Unit Tests (`test_utils.py`, `test_models.py`, `test_mapper.py`)

**Purpose:** Test individual functions and classes in isolation.

**Characteristics:**
- Fast execution (no external dependencies)
- Pure functions with deterministic outputs
- No API calls or database connections
- Focus on logic and edge cases

**Example:**
```python
def test_extract_para_areas_multiple():
    """Test extracting multiple PARA areas from labels."""
    labels = ["WORK 📁", "HEALTH 📁", "capsync"]
    areas = extract_para_areas(labels)
    assert "WORK" in areas
    assert "HEALTH" in areas
    assert len(areas) == 2
```

### Integration Tests (`test_todoist_client.py`, `test_notion_client.py`)

**Purpose:** Test API client interactions with mocked external services.

**Characteristics:**
- Mock external API calls
- Test error handling and retries
- Validate request/response formatting
- Test client configuration

**Example:**
```python
@pytest.mark.asyncio
async def test_find_area_by_name_not_found(notion_client):
    """Test finding a non-existent area returns None."""
    mock_response = {"results": []}
    
    with patch.object(notion_client, "_query_database_direct", 
                      new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_response
        result = await notion_client.find_area_by_name("NONEXISTENT")
        assert result is None
```

### End-to-End Tests (`test_end_to_end.py`)

**Purpose:** Test complete workflows from webhook receipt to Notion update.

**Characteristics:**
- Test full sync pipeline
- Multiple components working together
- Simulate real-world scenarios
- Validate state transitions

**Example:**
```python
@pytest.mark.asyncio
async def test_complete_sync_new_task(sync_worker, mock_todoist_client, 
                                       mock_notion_client, mock_store):
    """Test syncing a brand new task from Todoist to Notion."""
    message = PubSubMessage(
        action=SyncAction.UPSERT,
        todoist_task_id="12345678",
    )
    
    await sync_worker.process_message(message)
    
    # Verify complete workflow
    mock_todoist_client.get_task.assert_awaited_once_with("12345678")
    mock_notion_client.create_todo_page.assert_awaited_once()
    mock_store.save_task_state.assert_awaited_once()
```

## ✍️ Writing Tests

### Test Naming Conventions

```python
# ✅ Good: Descriptive, specific, states expected behavior
def test_extract_para_areas_returns_empty_list_when_no_areas_present():
    pass

# ❌ Bad: Vague, doesn't explain what's being tested
def test_areas():
    pass
```

### Test Structure (AAA Pattern)

```python
def test_example():
    # Arrange: Set up test data and preconditions
    labels = ["WORK 📁", "capsync"]
    
    # Act: Execute the function under test
    result = extract_para_areas(labels)
    
    # Assert: Verify the expected outcome
    assert result == ["WORK"]
```

### Using Fixtures

```python
@pytest.fixture
def sample_todoist_task() -> TodoistTask:
    """Reusable test data for Todoist tasks."""
    return TodoistTask(
        id="12345678",
        content="Test task",
        labels=["capsync", "WORK 📁"],
        priority=3,
    )

def test_with_fixture(sample_todoist_task):
    """Test using the fixture."""
    assert sample_todoist_task.id == "12345678"
```

### Mocking External Calls

```python
@pytest.mark.asyncio
async def test_api_call_with_mock():
    """Test API call with mocked response."""
    mock_response = httpx.Response(200, json={"result": "success"})
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        # Call your function that makes the API request
        result = await your_function()
        
        # Verify mock was called correctly
        mock_get.assert_awaited_once()
        assert result == {"result": "success"}
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_retry_on_failure(todoist_client):
    """Test that operations retry on transient failures."""
    mock_response = httpx.Response(200, json={"id": "123"})
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # First two calls fail, third succeeds
        mock_get.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Another timeout"),
            mock_response,
        ]
        
        task = await todoist_client.get_task("123")
        
        assert task.id == "123"
        assert mock_get.await_count == 3  # Verify retries occurred
```

### Testing New Features

When adding a new feature, write tests that cover:

1. **Happy path:** Feature works as expected
2. **Edge cases:** Boundary conditions, empty inputs, null values
3. **Error cases:** Invalid inputs, API failures, timeouts
4. **Integration:** Feature works with existing functionality

**Example for new AREAS feature:**

```python
class TestAreasSync:
    """Test AREAS synchronization feature."""
    
    def test_extract_single_area(self):
        """Happy path: Extract one area."""
        assert extract_para_areas(["WORK 📁"]) == ["WORK"]
    
    def test_extract_multiple_areas(self):
        """Happy path: Extract multiple areas."""
        result = extract_para_areas(["WORK 📁", "HEALTH 📁"])
        assert len(result) == 2
    
    def test_no_areas(self):
        """Edge case: No areas present."""
        assert extract_para_areas(["urgent"]) == []
    
    def test_empty_labels(self):
        """Edge case: Empty input."""
        assert extract_para_areas([]) == []
    
    def test_area_without_emoji_ignored(self):
        """Feature requirement: Emoji is mandatory."""
        assert extract_para_areas(["WORK"]) == []
    
    @pytest.mark.asyncio
    async def test_area_not_found_returns_none(self, notion_client):
        """Error case: Area doesn't exist in Notion."""
        mock_response = {"results": []}
        with patch.object(notion_client, "_query_database_direct") as mock:
            mock.return_value = mock_response
            result = await notion_client.find_area_by_name("UNKNOWN")
            assert result is None
```

## 📊 Coverage

### Current Coverage

**Target:** 80%+ coverage on application code

**Excluded from coverage:**
- External API response handling (actual API calls)
- Main entry points (`if __name__ == "__main__"`)
- Configuration loading
- Logging statements

### Viewing Coverage Reports

After running `pytest --cov=app --cov-report=html`, the HTML report shows:

- **Green:** Lines executed during tests
- **Red:** Lines not executed
- **Yellow:** Partially covered branches

### Improving Coverage

```bash
# Find files with low coverage
pytest --cov=app --cov-report=term-missing | grep -E "^app/"

# Focus tests on specific module
pytest tests/test_utils.py --cov=app.utils --cov-report=term-missing
```

## 🔄 CI/CD

### GitHub Actions (if configured)

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements-test.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v2
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Set up git hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

**`.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## 🐛 Debugging Tests

### Run with Debug Output

```bash
# Show print statements
pytest -s

# Show detailed tracebacks
pytest -vv

# Drop into debugger on failure
pytest --pdb

# Drop into debugger at start of test
pytest --trace
```

### Using pytest-pudb

```bash
pip install pytest-pudb

# Run with visual debugger
pytest --pudb
```

### Debugging Async Tests

```python
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    # Add debug prints
    print("Starting test...")
    result = await your_async_function()
    print(f"Result: {result}")
    assert result is not None
```

## 📝 Test Checklist

Before submitting code, ensure:

- [ ] All new functions have unit tests
- [ ] Edge cases are covered
- [ ] Error handling is tested
- [ ] Integration tests pass
- [ ] Coverage is ≥80%
- [ ] Tests are documented
- [ ] No flaky tests (run multiple times)
- [ ] Mocks are used for external dependencies
- [ ] Tests follow naming conventions
- [ ] Tests are organized logically

## 🔗 Related Documentation

- [README.md](README.md) - Main project documentation
- [SYNC_RULES.md](SYNC_RULES.md) - Complete synchronization rules
- [CODE_AUDIT.md](CODE_AUDIT.md) - Code audit against sync rules
- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)

---

**Last Updated:** October 28, 2025  
**Test Framework:** pytest 7.x  
**Coverage Tool:** pytest-cov

