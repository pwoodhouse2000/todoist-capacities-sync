# Investigation: Notion API `databases.query()` AttributeError

## Problem Statement

The application is experiencing consistent `AttributeError` when trying to call `client.databases.query()` on the `AsyncClient` from the `notion-client` library:

```
AttributeError: 'DatabasesEndpoint' object has no attribute 'query'
```

This error occurs in multiple locations:
- `find_project_by_todoist_id()`
- `find_todo_by_todoist_id()`
- `find_area_by_name()`
- `match_person()` (during people matching)

## Current Code Pattern

```python
from notion_client import AsyncClient

client = AsyncClient(auth=api_key)

# This fails with AttributeError
result = await client.databases.query(
    database_id=database_id,
    filter={...}
)
```

## Hypotheses

### Hypothesis 1: Version Mismatch or API Change

**Theory:** The `notion-client` library version being installed in production differs from what's expected, or the API changed between versions.

**Current Version:** `notion-client = "^2.2.1"` in `pyproject.toml`

**Evidence:**
- The caret (`^`) allows any version `>=2.2.1, <3.0.0`
- Docker build uses `poetry lock --no-update` which could use different versions on different builds
- No poetry.lock file is committed to the repository

**Test:** Run `scripts/test_notion_api.py` to check:
1. What version is actually installed
2. What attributes exist on `client.databases`
3. Whether sync `Client` works differently than `AsyncClient`

### Hypothesis 2: AsyncClient vs Client API Differences

**Theory:** The `AsyncClient` has a different API structure than the synchronous `Client`.

**Evidence:**
- Error message specifically mentions `DatabasesEndpoint` object
- This could be an intermediate object that doesn't expose the same methods
- Async APIs sometimes have different method names (e.g., `query_async()`)

**Test:** Compare sync vs async client behavior in diagnostic script.

### Hypothesis 3: Initialization Issue

**Theory:** The `AsyncClient` is not being initialized correctly, resulting in incomplete endpoint setup.

**Evidence:**
- The error is consistent across all deployments
- Other Notion API calls might be working (e.g., `pages.create`, `pages.update`)

**Test:** Check if other endpoints work (pages, blocks, etc.)

### Hypothesis 4: Import/Module Issue

**Theory:** There's a namespace collision or incorrect import of the `notion-client` library.

**Evidence:**
- The application has multiple async contexts (FastAPI, Pub/Sub worker)
- Possible module caching issues

**Test:** Check imports and module paths.

## Diagnostic Steps

### Step 1: Run Diagnostic Script

```bash
cd /Users/pete/SOFTWARE\ REPO/Todoist\ Notion\ Sync/todoist-capacities-sync
python scripts/test_notion_api.py
```

This will test:
- AsyncClient availability and attributes
- Sync Client for comparison
- Direct HTTP API call as fallback

### Step 2: Check Installed Version in Production

```bash
# Check deployed container's notion-client version
gcloud run services describe todoist-notion-sync \
  --region us-west1 \
  --project=notion-todoist-sync-464419 \
  --format='value(spec.template.spec.containers[0].image)' \
  | xargs docker run --rm --entrypoint pip  list | grep notion-client
```

Alternative: Add version logging to the application startup.

### Step 3: Check Poetry Lock File

```bash
# Generate lock file to see what versions are resolved
poetry lock
cat poetry.lock | grep -A 10 "name = \"notion-client\""
```

### Step 4: Test Direct API Approach

If the library has issues, we can bypass it and use direct HTTP calls:

```python
import httpx

async def query_database_direct(database_id: str, filter: dict):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"filter": filter})
        return response.json()
```

## Known Workarounds

### Current Implementation (Temporary)

Currently using error handling to gracefully skip failed queries:

```python
try:
    result = await self.client.databases.query(...)
except (AttributeError, TypeError) as e:
    logger.warning("Notion client API error - skipping lookup")
    return None
```

**Problems with this approach:**
- Can't find existing records
- Creates duplicates (as seen in AREAS database)
- Degrades functionality

### Better Workaround (If Library Issue Confirmed)

Replace library calls with direct HTTP:

```python
async def _query_database(self, database_id: str, **kwargs) -> Dict:
    """Direct HTTP query to Notion database API."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=kwargs, timeout=30.0)
        response.raise_for_status()
        return response.json()
```

## Next Steps

1. ✅ **Created diagnostic script** (`scripts/test_notion_api.py`)
2. ⏳ **Run diagnostic locally** to understand API structure
3. ⏳ **Generate and commit poetry.lock** to pin exact versions
4. ⏳ **Test in production** to see if local vs deployed differ
5. ⏳ **Implement permanent fix** based on findings

## Potential Fixes

### Fix Option 1: Pin Exact Version

If version inconsistency is the issue:

```toml
# In pyproject.toml
notion-client = "2.2.1"  # Remove caret to pin exact version
```

Then:
```bash
poetry lock
poetry export -f requirements.txt --output requirements.txt --without-hashes
# Commit both poetry.lock and requirements.txt
```

### Fix Option 2: Use Direct HTTP Calls

If the library is fundamentally broken:

1. Create a `_query_database_direct()` helper method
2. Replace all `client.databases.query()` calls with the helper
3. Continue using the library for `pages.create()`, `pages.update()`, etc.

### Fix Option 3: Switch to Synchronous Client

If only AsyncClient is broken:

1. Use sync `Client` instead of `AsyncClient`
2. Wrap in `asyncio.to_thread()` to maintain async compatibility:

```python
import asyncio
from notion_client import Client

client = Client(auth=api_key)

async def query_database(database_id, **kwargs):
    return await asyncio.to_thread(
        client.databases.query,
        database_id=database_id,
        **kwargs
    )
```

### Fix Option 4: Update to Latest Version

If newer version fixes the issue:

```toml
# In pyproject.toml
notion-client = "^2.3.0"  # Or latest stable
```

## References

- Notion API Documentation: https://developers.notion.com/reference/post-database-query
- notion-client GitHub: https://github.com/ramnes/notion-sdk-py
- notion-client PyPI: https://pypi.org/project/notion-client/

## Investigation Log

| Date | Investigator | Finding |
|------|-------------|---------|
| 2025-10-27 | AI Assistant | Discovered AttributeError affecting all database queries |
| 2025-10-27 | AI Assistant | Created diagnostic script and workaround |
| 2025-10-27 | AI Assistant | Documented hypotheses and potential fixes |

---

**Status:** 🔴 Active Investigation

**Impact:** HIGH - Causing duplicate AREA entries and degraded functionality

**Priority:** P0 - Needs immediate resolution



