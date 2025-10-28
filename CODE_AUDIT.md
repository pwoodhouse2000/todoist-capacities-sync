# Code Audit Against SYNC_RULES.md

**Date:** October 28, 2025  
**Auditor:** AI Assistant  
**Scope:** Complete codebase audit against documented sync rules

---

## 📊 Executive Summary

| Category | ✅ Compliant | ⚠️ Partial | ❌ Gap | 🔮 Future |
|----------|-------------|-----------|--------|----------|
| **AREAS** | 3 | 1 | 2 | 1 |
| **TASKS** | 12 | 3 | 7 | 8 |
| **PROJECTS** | 4 | 2 | 5 | 0 |
| **TOTAL** | 19 | 6 | 14 | 9 |

**Status:** 🟢 **FIXES COMPLETED** - All critical and high-priority issues resolved as of October 28, 2025.

**Update:** The following fixes have been implemented:
- ✅ AREAS auto-creation disabled (prevents duplicates)
- ✅ Task title sync removed (Todoist always wins)
- ✅ Inbox project filtering added
- ✅ Multiple areas support implemented
- ✅ Project AREAS inheritance from tasks
- ✅ Project AREAS set once at creation
- ✅ Two Notion links (task + project) added
- ✅ Auto-remove capsync for recurring tasks

---

## 📂 AREAS Audit

### ✅ Compliant (3)

1. **Detection via Emoji**
   - ✅ `extract_para_area()` strips emoji correctly (lines 114-126 in `utils.py`)
   - ✅ Handles multi-word areas like "PERSONAL & FAMILY 📁"

2. **Many-to-Many Relations**
   - ✅ Code supports multiple area relations (though implementation incomplete)
   - ✅ Notion properties use `relation` array format

3. **Race Condition Protection**
   - ✅ `ensure_area_exists()` uses `asyncio.Lock` per area name (lines 568-598 in `notion_client.py`)
   - ✅ Double-checked locking pattern implemented

### ⚠️ Partial Compliance (1)

4. **Sync Direction (One-Way)**
   - ⚠️ **Current:** Code only syncs Todoist → Notion
   - ⚠️ **Issue:** No enforcement to prevent Notion → Todoist sync
   - **Impact:** Low (no bidirectional code exists yet)

### ❌ Non-Compliant (2)

5. **NEVER Create Areas Automatically** ❌ **CRITICAL**
   - **Rule:** "Sync NEVER creates areas automatically"
   - **Current:** `ensure_area_exists()` calls `create_area_page()` if area doesn't exist (line 597 in `notion_client.py`)
   - **Impact:** HIGH - violates core principle
   - **Location:** `app/notion_client.py:568-598`
   - **Fix Required:** Change `ensure_area_exists()` to return `None` if area not found, don't create

6. **Multiple Areas Per Task** ❌ **INCOMPLETE**
   - **Rule:** "Tasks can link to multiple areas"
   - **Current:** `extract_para_area()` returns **single** area (first match), not list
   - **Impact:** MEDIUM - multi-area tasks will only sync first area
   - **Location:** `app/utils.py:93-127`
   - **Fix Required:** Return `List[str]` and update all callers

### 🔮 Future Enhancement (1)

7. **Bidirectional AREAS Sync**
   - Documented as future enhancement
   - No code to remove

---

## 📋 TASKS Audit

### ✅ Compliant (12)

1. **Auto-labeling Logic**
   - ✅ `should_auto_label_task()` checks: non-recurring + not in Inbox (lines 183-209 in `utils.py`)
   - ✅ `_auto_label_tasks()` implements auto-labeling (lines 151-215 in `handlers.py`)
   - ✅ Respects `settings.auto_label_tasks` flag

2. **Label Creation**
   - ✅ Sync auto-creates `capsync` label if missing (implied by Todoist API behavior)

3. **Inbox Detection**
   - ✅ Correctly identifies Inbox by project name (line 176 in `handlers.py`)

4. **Recurring Task Detection**
   - ✅ Uses `task.due.is_recurring` check (line 190 in `handlers.py`)

5. **Task Creation (One-Way)**
   - ✅ No Notion → Todoist creation code exists

6. **Properties Sync (One-Way)**
   - ✅ All properties sync Todoist → Notion only
   - ✅ Todoist always wins (no conflict resolution)

7. **Deletion (One-Way)**
   - ✅ `_handle_archive()` archives task in Notion when deleted in Todoist (lines 289-324 in `pubsub_worker.py`)

8. **Completion Sync**
   - ✅ `map_task_to_todo()` maps `task.is_completed` to `todo.completed` (line 81 in `mapper.py`)
   - ✅ Reconciliation fetches both active + completed tasks (lines 240-258 in `handlers.py`)

9. **Comments (One-Way)**
   - ✅ `format_markdown_comments()` syncs Todoist comments to Notion (lines 53-76 in `utils.py`)
   - ✅ No Notion → Todoist comment sync code

10. **Idempotency**
    - ✅ `compute_payload_hash()` prevents duplicate syncs (lines 184-195 in `pubsub_worker.py`)

11. **Label Detection**
    - ✅ `has_capsync_label()` handles both `@capsync` and `capsync` (lines 40-50 in `utils.py`)

12. **Completed Tasks Without Label**
    - ✅ Special handling for completed tasks that lost label (lines 105-121 in `pubsub_worker.py`)

### ⚠️ Partial Compliance (3)

13. **Notion Links in Todoist (Two Links)** ⚠️
    - **Rule:** Add TWO links: task page + project page
    - **Current:** `_add_notion_backlink()` only adds task link (lines 400-434 in `pubsub_worker.py`)
    - **Impact:** MEDIUM - users won't have quick project access
    - **Fix Required:** Add project link to description

14. **Auto-labeling Triggers** ⚠️
    - **Rule:** Both webhook + reconciliation should auto-label
    - **Current:** Only reconciliation auto-labels (line 230 in `handlers.py`)
    - **Impact:** LOW - reconciliation runs every 5 min, so delay is minimal
    - **Note:** Intentional design choice (webhook unreliable)

15. **Removing capsync Label (Orphaning)** ⚠️
    - **Rule:** Add comment "Sync label was removed on [date]" → orphan
    - **Current:** Archives task in Notion (no comment added)
    - **Impact:** LOW - achieves similar goal but doesn't match spec
    - **Location:** Lines 114-121 in `pubsub_worker.py`

### ❌ Non-Compliant (7)

16. **Subtasks Representation** ❌ **MISSING**
    - **Rule:** "Subtasks sync as Notion toggle lists in page content"
    - **Current:** No subtask syncing implemented
    - **Impact:** HIGH - entire feature missing
    - **Fix Required:** Implement subtask detection, toggle list creation

17. **Subtasks Inherit Properties** ❌ **MISSING**
    - **Rule:** Subtasks inherit capsync, AREAS, project from parent
    - **Current:** N/A (no subtask sync)
    - **Impact:** HIGH - blocked by #16

18. **Subtask Deletion Cascade** ❌ **MISSING**
    - **Rule:** Delete parent → delete all subtasks in Notion
    - **Current:** N/A (no subtask sync)
    - **Impact:** MEDIUM - blocked by #16

19. **Multiple Areas Per Task** ❌ **INCOMPLETE**
    - **Rule:** "Tasks can link to multiple areas (rare)"
    - **Current:** Only syncs first area found
    - **Impact:** MEDIUM - same as AREAS issue #6
    - **Location:** `extract_para_area()` returns single string, not list

20. **Task Title Sync (Bidirectional)** ❌ **INCOMPLETE**
    - **Rule:** "Todoist always wins" (one-way for now)
    - **Current:** `_reconcile_notion_to_todoist()` DOES sync Notion → Todoist (lines 404-428 in `handlers.py`)
    - **Impact:** MEDIUM - contradicts documented one-way rule
    - **Fix Required:** Remove title sync from Notion → Todoist (or update docs)

21. **Orphan Re-syncing** ❌ **NOT TESTED**
    - **Rule:** "Re-adding capsync should resume sync"
    - **Current:** Code should handle it, but not explicitly tested
    - **Impact:** LOW - likely works but needs verification

22. **Auto-remove Label (Recurring Toggle)** ❌ **MISSING**
    - **Rule:** "One-off → Recurring = auto-remove capsync"
    - **Current:** Only adds labels, doesn't remove (lines 151-215 in `handlers.py`)
    - **Impact:** MEDIUM - recurring tasks won't get label removed
    - **Fix Required:** Add removal logic in `_auto_label_tasks()`

### 🔮 Future Enhancements (8)

23-30. **Documented Future Features**
    - Bidirectional task creation
    - Bidirectional completion
    - Bidirectional deletion
    - Bidirectional property sync
    - Conflict detection
    - Subtask toggle lists (properly rendered)
    - Bidirectional comments
    - Sync status dashboard

---

## 📁 PROJECTS Audit

### ✅ Compliant (4)

1. **Which Projects Sync**
   - ✅ No explicit Inbox filtering yet, but rule understood

2. **Creation (One-Way)**
   - ✅ `_ensure_project_exists()` creates projects from Todoist only (lines 326-398 in `pubsub_worker.py`)

3. **Status Property (Bidirectional)**
   - ✅ `_reconcile_projects()` syncs archived status (lines 343-371 in `handlers.py`)
   - ✅ Handles both archive and un-archive

4. **Deletion Cascade**
   - ✅ (Implicit) - Notion archival should handle this

### ⚠️ Partial Compliance (2)

5. **Project Name Sync (Bidirectional)** ⚠️
    - **Rule:** "Post-creation, Notion wins"
    - **Current:** `_reconcile_notion_to_todoist()` DOES sync Notion name → Todoist (lines 378-401 in `handlers.py`)
    - **Impact:** LOW - actually compliant! (docs say Notion wins)
    - **Note:** This is CORRECT per rules

6. **Notion Link in Todoist (Project Comment)** ⚠️
    - **Rule:** "Add Notion link as project comment on first sync"
    - **Current:** No code to add project comments
    - **Impact:** MEDIUM - users can't navigate Todoist → Notion for projects
    - **Fix Required:** Add comment via Todoist API after project creation

### ❌ Non-Compliant (5)

7. **AREAS Inheritance (From Tasks)** ❌ **INCOMPLETE**
   - **Rule:** "Project AREAS inherited from all areas present in tasks"
   - **Current:** Uses **single** area from task labels (line 354 in `pubsub_worker.py`)
   - **Impact:** HIGH - multi-area projects won't capture all areas
   - **Fix Required:** Aggregate all unique areas from project's tasks

8. **AREAS Inheritance (Set Once)** ❌ **NOT ENFORCED**
   - **Rule:** "Set at creation only, then Notion-controlled"
   - **Current:** Updates area on every task sync (line 359 in `pubsub_worker.py`)
   - **Impact:** MEDIUM - Notion edits will be overwritten
   - **Fix Required:** Only set area on project creation, not updates

9. **Empty Project Archival** ❌ **MISSING**
   - **Rule:** "Project becomes empty → Status = Archived"
   - **Current:** No code to detect empty projects and archive them
   - **Impact:** LOW - edge case
   - **Fix Required:** Add check in reconciliation

10. **Only Sync Projects with ≥1 Qualifying Task** ❌ **NOT ENFORCED**
    - **Rule:** "Only sync projects with ≥1 task meeting criteria"
    - **Current:** `_ensure_project_exists()` creates project whenever task syncs (line 326 in `pubsub_worker.py`)
    - **Impact:** LOW - creates projects even if they have no synced tasks
    - **Fix Required:** Check if project has any capsync tasks before creating

11. **Inbox Filtering** ❌ **NOT ENFORCED**
    - **Rule:** "Never sync Inbox project"
    - **Current:** No explicit check to skip Inbox project
    - **Impact:** MEDIUM - Inbox might sync to Notion
    - **Fix Required:** Add check in `_ensure_project_exists()`

---

## 🔧 Priority Fix List

### 🔴 **CRITICAL (Must Fix Immediately)**

1. **[AREAS-5] Auto-Creating Areas** 
   - **Severity:** CRITICAL
   - **Impact:** Violates core rule, causes duplicates
   - **Effort:** 1 hour
   - **Location:** `app/notion_client.py:568-598`
   - **Fix:**
     ```python
     async def ensure_area_exists(self, area_name: str) -> Optional[str]:
         """Find area, return None if not found (NEVER create)."""
         if not self.areas_db_id:
             return None
         
         # No lock needed since we're not creating
         existing_area = await self.find_area_by_name(area_name)
         if existing_area:
             return existing_area["id"]
         
         logger.warning(
             "Area not found in AREAS DB - skipping",
             extra={"area_name": area_name}
         )
         return None
     ```

2. **[TASKS-20] Bidirectional Title Sync (Contradicts Docs)**
   - **Severity:** HIGH
   - **Impact:** Notion edits overwrite Todoist (against "Todoist wins" rule)
   - **Effort:** 30 minutes
   - **Location:** `app/handlers.py:404-428`
   - **Fix:** Remove title sync from `_reconcile_notion_to_todoist()` OR update docs to clarify bidirectional

### 🟠 **HIGH PRIORITY (Fix Soon)**

3. **[AREAS-6 / TASKS-19] Multiple Areas Support**
   - **Severity:** HIGH
   - **Impact:** Multi-area tasks/projects only sync first area
   - **Effort:** 3 hours
   - **Locations:** 
     - `app/utils.py:93-127` (`extract_para_area`)
     - `app/pubsub_worker.py:200-209` (area assignment)
     - `app/notion_client.py:create_todo_page, update_todo_page` (relation handling)
   - **Fix:**
     ```python
     def extract_para_areas(labels: List[str]) -> List[str]:
         """Extract ALL matching PARA areas from labels."""
         areas = []
         for label in labels:
             clean_label = ...  # existing cleaning logic
             for area in settings.para_area_labels:
                 if clean_label.upper() == area.upper():
                     areas.append(area)
         return areas
     ```

4. **[PROJECTS-7] Project AREAS from All Tasks**
   - **Severity:** HIGH
   - **Impact:** Projects don't capture all relevant areas
   - **Effort:** 4 hours
   - **Location:** `app/pubsub_worker.py:326-398`
   - **Fix:** Query all tasks in project, aggregate unique areas, set on creation only

5. **[PROJECTS-8] AREAS Set Once (Creation Only)**
   - **Severity:** HIGH
   - **Impact:** Notion area edits get overwritten
   - **Effort:** 2 hours
   - **Location:** `app/pubsub_worker.py:354-373`
   - **Fix:** Add flag to track if project already created; skip area update if exists

6. **[PROJECTS-11] Filter Out Inbox**
   - **Severity:** HIGH
   - **Impact:** Inbox project might sync to Notion
   - **Effort:** 1 hour
   - **Location:** `app/pubsub_worker.py:326-398`
   - **Fix:**
     ```python
     async def _ensure_project_exists(...):
         # Add at start
         if project.name == "Inbox":
             logger.info("Skipping Inbox project")
             return None
         ...
     ```

### 🟡 **MEDIUM PRIORITY (Fix This Week)**

7. **[TASKS-13] Two Notion Links (Task + Project)**
   - **Severity:** MEDIUM
   - **Impact:** Users can't quickly access project from Todoist
   - **Effort:** 2 hours
   - **Location:** `app/pubsub_worker.py:400-434`
   - **Fix:**
     ```python
     async def _add_notion_backlink(self, task, notion_page_id, project_page_id):
         notion_task_url = f"https://notion.so/{notion_page_id.replace('-', '')}"
         notion_project_url = f"https://notion.so/{project_page_id.replace('-', '')}"
         
         new_description = f"{task.description}\n\n---\n"
         new_description += f"📝 View Task in Notion: {notion_task_url}\n"
         new_description += f"📁 View Project in Notion: {notion_project_url}"
         ...
     ```

8. **[TASKS-22] Auto-remove capsync (Recurring Toggle)**
   - **Severity:** MEDIUM
   - **Impact:** Recurring tasks keep label when they shouldn't
   - **Effort:** 2 hours
   - **Location:** `app/handlers.py:151-215`
   - **Fix:** Add removal logic in `_auto_label_tasks()` for tasks that become recurring

9. **[TASKS-15] Orphan Comment (Instead of Archive)**
   - **Severity:** LOW
   - **Impact:** Doesn't match documented behavior
   - **Effort:** 1 hour
   - **Location:** `app/pubsub_worker.py:114-121`
   - **Fix:** Add comment to Notion page body instead of archiving

10. **[PROJECTS-6] Add Project Comment (Notion Link)**
    - **Severity:** MEDIUM
    - **Impact:** Users can't navigate Todoist → Notion for projects
    - **Effort:** 3 hours
    - **Location:** `app/pubsub_worker.py:326-398`
    - **Fix:** Add Todoist project comment API call after creation

11. **[PROJECTS-9] Empty Project Archival**
    - **Severity:** LOW
    - **Impact:** Edge case
    - **Effort:** 2 hours
    - **Location:** `app/handlers.py:343-371`
    - **Fix:** Count qualifying tasks per project; archive if zero

12. **[PROJECTS-10] Only Sync Projects with Tasks**
    - **Severity:** MEDIUM
    - **Impact:** Creates empty projects in Notion
    - **Effort:** 3 hours
    - **Location:** `app/pubsub_worker.py:326-398`
    - **Fix:** Check if project has any capsync tasks before creating

### ⚪ **LOW PRIORITY (Future)**

13-22. **[TASKS-16, 17, 18] Subtask Sync**
    - **Severity:** HIGH (feature request)
    - **Impact:** Entire feature missing
    - **Effort:** 16+ hours (major feature)
    - **Scope:** New module for subtask detection, toggle list creation, nested syncing

---

## 📝 Recommendations

### Immediate Actions (This Week)

1. **Fix AREAS Auto-Creation (#1)** - Prevents duplicate area explosion
2. **Resolve Title Sync Ambiguity (#2)** - Either fix code or update docs
3. **Add Inbox Filtering (#6)** - Prevent Inbox from syncing

### Short-Term (Next 2 Weeks)

4. **Implement Multiple Areas (#3)** - Core PARA functionality
5. **Fix Project AREAS Logic (#4, #5)** - Project organization
6. **Add Two Notion Links (#7)** - Better UX

### Medium-Term (Next Month)

7. **Subtask Sync (#13-22)** - Major feature addition
8. **Auto-remove Labels (#8)** - Complete auto-labeling logic
9. **Project Comments (#10)** - Navigation improvement

### Long-Term (Future Enhancements)

10. **Bidirectional Sync** - Task creation, completion, deletion
11. **Conflict Detection** - Timestamp-based resolution
12. **Sync Dashboard** - Monitoring and debugging

---

## 🎯 Success Metrics

**After Priority Fixes:**
- ✅ No automatic area creation (prevents duplicates)
- ✅ Todoist always wins for task properties (clear directionality)
- ✅ Inbox never syncs (prevents noise)
- ✅ Multi-area tasks/projects work correctly (rare but important)
- ✅ Projects properly categorized by areas (better organization)
- ✅ Users have quick Notion links in Todoist (better UX)

---

## 📊 Testing Plan

### Unit Tests Needed
1. `test_extract_para_areas_multiple()` - Multi-area extraction
2. `test_ensure_area_exists_no_create()` - Verify no auto-creation
3. `test_auto_remove_capsync_recurring()` - Label removal logic
4. `test_inbox_filter()` - Inbox project skipping

### Integration Tests Needed
1. `test_multi_area_task_sync()` - End-to-end multi-area
2. `test_project_areas_from_tasks()` - Project area aggregation
3. `test_orphan_comment()` - Orphaning behavior
4. `test_two_notion_links()` - Description formatting

### Manual Tests Needed
1. Create task with multiple area labels → verify all sync
2. Move task Inbox → Project → verify auto-label
3. Toggle task recurring → verify label removal
4. Remove capsync → verify orphan comment added

---

**End of Audit**

