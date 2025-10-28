# Design: Fix AREAS Database Race Condition & Duplication Bug

## Executive Summary

This document outlines the design for fixing two critical bugs:
1. **Notion API Bug:** `databases.query()` failing with AttributeError, causing duplicate AREA creation
2. **Race Condition:** Multiple workers creating duplicate AREAs simultaneously

## Problem Analysis

### Bug 1: API Failure Leading to Duplicates

**Current Flow:**
```python
async def ensure_area_exists(area_name):
    existing = await find_area_by_name(area_name)  # Returns None due to API error
    if existing:
        return existing["id"]
    
    # Always creates new because existing is always None!
    new_area = await create_area_page(area_name)
    return new_area["id"]
```

**Root Cause:**
- `find_area_by_name()` calls `client.databases.query()` which fails with AttributeError
- Error handling catches it and returns `None`
- `ensure_area_exists()` interprets `None` as "doesn't exist" and creates new entry
- Happens on EVERY task sync → massive duplication

### Bug 2: Classic Check-Then-Create Race Condition

**Scenario:**
```
Time    Worker A              Worker B              Worker C
----    --------              --------              --------
T0      check("HOME")         -                     -
T1      None returned         check("HOME")         -
T2      -                     None returned         check("HOME")
T3      create("HOME")        -                     None returned
T4      -                     create("HOME")        -
T5      -                     -                     create("HOME")

Result: 3 duplicate HOME entries!
```

This happens even if the API works, because:
1. Multiple Pub/Sub messages processed in parallel
2. All check at same time → all get "not found"
3. All proceed to create → duplicates

## Design Goals

1. **Fix API Issue:** Ensure database queries work reliably
2. **Prevent Race Condition:** Even with working API, prevent concurrent duplicates
3. **Handle Edge Cases:** Deal with existing duplicates gracefully
4. **Maintain Performance:** Don't slow down the happy path
5. **Backward Compatible:** Work with existing Notion database structure

## Proposed Solutions

### Solution 1: Fix the Notion API Issue

#### Option 1A: Use Direct HTTP Calls

**Approach:** Bypass the broken `client.databases.query()` entirely.

**Implementation:**
```python
class NotionClient:
    def __init__(self, ...):
        self.client = AsyncClient(auth=self.api_key)
        self._http_client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            timeout=30.0
        )
    
    async def _query_database(
        self, 
        database_id: str, 
        filter: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """Query database using direct HTTP API call."""
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        
        body = {}
        if filter:
            body["filter"] = filter
        body.update(kwargs)
        
        response = await self._http_client.post(url, json=body)
        response.raise_for_status()
        return response.json()
    
    async def find_area_by_name(self, area_name: str) -> Optional[Dict]:
        """Find area using reliable HTTP query."""
        if not self.areas_db_id:
            return None
        
        result = await self._query_database(
            database_id=self.areas_db_id,
            filter={
                "property": "Name",
                "title": {"equals": area_name},
            },
        )
        
        results = result.get("results", [])
        return results[0] if results else None
```

**Pros:**
- Bypasses broken library method
- Direct control over HTTP requests
- Can add custom retry logic
- Works reliably

**Cons:**
- Duplicates functionality the library should provide
- Need to maintain HTTP client separately
- More code to maintain

#### Option 1B: Use Synchronous Client with asyncio.to_thread

**Approach:** Use sync `Client` wrapped in async.

**Implementation:**
```python
import asyncio
from notion_client import Client  # Sync client

class NotionClient:
    def __init__(self, ...):
        self.sync_client = Client(auth=self.api_key)
        self.async_client = AsyncClient(auth=self.api_key)  # For pages.create, etc.
    
    async def _query_database_sync(self, database_id: str, **kwargs) -> Dict:
        """Query using sync client in thread."""
        return await asyncio.to_thread(
            self.sync_client.databases.query,
            database_id=database_id,
            **kwargs
        )
    
    async def find_area_by_name(self, area_name: str) -> Optional[Dict]:
        if not self.areas_db_id:
            return None
        
        result = await self._query_database_sync(
            database_id=self.areas_db_id,
            filter={
                "property": "Name",
                "title": {"equals": area_name},
            },
        )
        
        results = result.get("results", [])
        return results[0] if results else None
```

**Pros:**
- Uses official library
- If sync client works, this will work
- Less code than direct HTTP

**Cons:**
- Thread overhead for each query
- Assumes sync client works where async doesn't
- Mixed sync/async is inelegant

#### Option 1C: Pin Library Version and Fix Upstream

**Approach:** Identify exact working version, pin it, and/or contribute fix to library.

**Implementation:**
```toml
# pyproject.toml
notion-client = "2.2.1"  # Pin exact version

# Generate and commit poetry.lock
```

```bash
poetry lock
poetry install
# Test to ensure it works
# Commit poetry.lock
```

**Pros:**
- If it's a version issue, this is cleanest
- Uses library as intended
- No workaround code

**Cons:**
- Requires finding a working version
- May not exist if AsyncClient is fundamentally broken
- Delays fix until upstream resolution

**Recommendation:** **Option 1A (Direct HTTP)** is most reliable in short term. Can migrate back to library later if fixed.

### Solution 2: Prevent Race Condition

Even with working API, need to prevent concurrent duplicate creation.

#### Option 2A: Application-Level Locking

**Approach:** Use in-memory lock per area name.

**Implementation:**
```python
import asyncio
from typing import Dict

class NotionClient:
    def __init__(self, ...):
        self._area_locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()  # Lock for the locks dict
    
    async def _get_area_lock(self, area_name: str) -> asyncio.Lock:
        """Get or create a lock for this area name."""
        async with self._locks_lock:
            if area_name not in self._area_locks:
                self._area_locks[area_name] = asyncio.Lock()
            return self._area_locks[area_name]
    
    async def ensure_area_exists(self, area_name: str) -> Optional[str]:
        """Ensure area exists with lock protection."""
        if not self.areas_db_id:
            return None
        
        # Acquire lock for this specific area
        lock = await self._get_area_lock(area_name)
        async with lock:
            # Check again after acquiring lock
            existing_area = await self.find_area_by_name(area_name)
            if existing_area:
                return existing_area["id"]
            
            # Still doesn't exist, create it
            new_area = await self.create_area_page(area_name)
            return new_area["id"]
```

**Pros:**
- Prevents race condition within single instance
- No external dependencies
- Fast (in-memory)

**Cons:**
- Doesn't work across multiple Cloud Run instances
- If multiple containers run simultaneously, still have race
- Lock state lost on restart

#### Option 2B: Firestore-Based Distributed Lock

**Approach:** Use Firestore transactions for distributed locking.

**Implementation:**
```python
from google.cloud import firestore

class NotionClient:
    def __init__(self, ...):
        self.firestore_client = firestore.AsyncClient()
    
    async def ensure_area_exists(self, area_name: str) -> Optional[str]:
        """Ensure area exists using Firestore transaction."""
        if not self.areas_db_id:
            return None
        
        # Use Firestore to track area page IDs
        doc_ref = self.firestore_client.collection("area_cache").document(area_name)
        
        @firestore.async_transactional
        async def create_or_get_area(transaction):
            # Read cached area ID
            snapshot = await doc_ref.get(transaction=transaction)
            
            if snapshot.exists:
                cached_data = snapshot.to_dict()
                # Verify it still exists in Notion
                try:
                    await self.async_client.pages.retrieve(cached_data["page_id"])
                    return cached_data["page_id"]
                except:
                    # Cached page doesn't exist, continue to create
                    pass
            
            # Check Notion
            existing_area = await self.find_area_by_name(area_name)
            if existing_area:
                page_id = existing_area["id"]
                # Cache it
                transaction.set(doc_ref, {
                    "page_id": page_id,
                    "area_name": area_name,
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
                return page_id
            
            # Create new area
            new_area = await self.create_area_page(area_name)
            page_id = new_area["id"]
            
            # Cache it
            transaction.set(doc_ref, {
                "page_id": page_id,
                "area_name": area_name,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            return page_id
        
        transaction = self.firestore_client.transaction()
        return await create_or_get_area(transaction)
```

**Pros:**
- Works across multiple Cloud Run instances
- Survives restarts
- Provides caching benefit
- Leverages existing Firestore usage

**Cons:**
- Extra Firestore read/write on each area access
- More complex
- Latency increase

#### Option 2C: Notion-Native Unique Constraint (If Available)

**Approach:** Use Notion's built-in duplicate prevention.

**Investigation Needed:** Check if Notion supports unique constraints on Title properties.

**Pros:**
- Most reliable if supported
- No application logic needed

**Cons:**
- May not be supported by Notion
- Would require API investigation

**Recommendation:** **Option 2A (In-Memory Lock)** for immediate fix + **Option 2B (Firestore)** for production robustness.

### Solution 3: Handle Existing Duplicates

#### Approach: Startup Deduplication Check

**Implementation:**
```python
# In app/main.py startup event

@app.on_event("startup")
async def startup_check_areas():
    """Check for and warn about duplicate areas."""
    notion_client = app.state.notion_client
    
    # Fetch all areas
    all_areas = await notion_client.get_all_areas()
    
    # Group by name
    area_groups = {}
    for area in all_areas:
        name = area.get("properties", {}).get("Name", {})...
        if name not in area_groups:
            area_groups[name] = []
        area_groups[name].append(area)
    
    # Check for duplicates
    duplicates_found = False
    for name, areas in area_groups.items():
        if len(areas) > 1:
            duplicates_found = True
            logger.warning(
                f"Found {len(areas)} duplicate entries for area '{name}'",
                extra={"area_name": name, "count": len(areas)}
            )
    
    if duplicates_found:
        logger.error(
            "DUPLICATE AREAS DETECTED! Run cleanup script: "
            "python scripts/cleanup_duplicate_areas.py"
        )
```

**Pros:**
- Alerts to problem immediately
- Doesn't break startup
- Provides remediation path

**Cons:**
- Doesn't fix automatically
- Adds startup latency

## Implementation Plan

### Phase 1: Immediate Fix (This Deploy)

1. ✅ **Implement direct HTTP fallback** (Option 1A)
   - Add `_query_database_direct()` method
   - Replace all `client.databases.query()` calls
   - Keep existing error handling as secondary safety

2. ✅ **Add in-memory locking** (Option 2A)
   - Implement `_get_area_lock()`
   - Wrap `ensure_area_exists()` with lock

3. ✅ **Create cleanup script** (Done)
   - `scripts/cleanup_duplicate_areas.py`

### Phase 2: Production Hardening (Next Deploy)

4. **Add Firestore caching** (Option 2B)
   - Implement distributed lock via Firestore
   - Cache area page IDs for performance

5. **Add startup duplicate check** (Solution 3)
   - Warn on startup if duplicates exist
   - Log cleanup instructions

6. **Add monitoring**
   - Alert if duplicate areas created
   - Track area creation rate

### Phase 3: Root Cause Resolution (Future)

7. **Investigate library issue fully**
   - Run diagnostic script locally and in production
   - Determine if version pinning helps
   - Consider upstream bug report/PR

8. **Migrate back to library if fixed**
   - Once library is reliable, remove HTTP workaround
   - Keep Firestore caching for performance

## Code Changes Required

### Files to Modify:

1. **`app/notion_client.py`**
   - Add `_http_client` initialization
   - Add `_query_database_direct()` method
   - Add `_area_locks` and `_get_area_lock()`
   - Modify `find_area_by_name()` to use direct HTTP
   - Modify `find_todo_by_todoist_id()` to use direct HTTP
   - Modify `find_project_by_todoist_id()` to use direct HTTP
   - Modify `match_person()` to use direct HTTP
   - Modify `ensure_area_exists()` to use locking

2. **`app/main.py`**
   - Add startup event for duplicate detection

3. **`pyproject.toml`** (if needed)
   - Add `httpx` if not already present (it is)

4. **`requirements.txt`** (regenerate)
   - `poetry export -f requirements.txt`

### Testing Required:

1. **Unit Tests:**
   - Test `_query_database_direct()` with mocked httpx
   - Test locking mechanism with concurrent calls
   - Test duplicate detection logic

2. **Integration Tests:**
   - Test area creation with parallel requests
   - Verify no duplicates created
   - Test fallback scenarios

3. **Manual Testing:**
   - Run cleanup script on production (dry-run first)
   - Deploy new code
   - Verify no new duplicates created
   - Monitor logs for 24 hours

## Rollback Plan

If deployment causes issues:

1. **Immediate:** Route traffic back to previous revision
2. **Quick Fix:** Revert changes to `notion_client.py`
3. **Long Term:** Address root cause in development

## Success Metrics

1. **No new duplicate AREAS created** (0 duplicates after 48 hours)
2. **All database queries succeed** (0 AttributeError logs)
3. **Performance maintained** (query latency < 500ms p95)
4. **Existing duplicates cleaned up** (7 total AREA entries only)

## Timeline

- **Phase 1:** 2-4 hours (coding + testing + deploy)
- **Phase 2:** 4-6 hours (Firestore integration + monitoring)
- **Phase 3:** TBD (depends on library investigation)

---

**Status:** 📝 Design Complete - Ready for Implementation

**Next Step:** Implement Phase 1 changes

**Owner:** TBD

**Last Updated:** 2025-10-27


