# Todoist ↔ Notion Sync Rules

**Last Updated:** October 28, 2025  
**Version:** 2.0

This document defines the complete sync logic between Todoist and Notion for the three primary data types: Areas, Projects, and Tasks.

---

## 🎯 General Principles

1. **Todoist is Primary for Most Operations:** Task creation, deletion, completion, and content updates originate in Todoist
2. **Notion is the Knowledge Hub:** Rich project and task details, relationships, and organization live in Notion
3. **Simplicity First:** Most sync is one-way (Todoist → Notion) to avoid conflicts
4. **Respectful of Existing Data:** Sync must handle existing synced entities without duplication
5. **`capsync` Label:** Uses `capsync` (without @) internally; Todoist UI displays as `@capsync`

---

## 📂 Data Type 1: AREAS

### Overview
Areas represent the PARA method's organizational structure (Projects, Areas, Resources, Archives). They provide high-level context for tasks and projects.

### Current Areas
- HOME
- HEALTH  
- PROSPER
- WORK
- PERSONAL & FAMILY
- FINANCIAL
- FUN

### Rules

#### Creation
- **Sync NEVER creates areas automatically**
- New areas must be created manually in Notion AREAS DB first
- Then create matching Todoist label: `UPPERCASE + 📁 emoji` (e.g., `HOME 📁`, `WORK 💼`)

#### Detection in Todoist
- Areas are identified by labels with **emoji suffix** (e.g., `HOME 📁`)
- Emoji is **required** to distinguish area labels from regular labels
- Sync extracts area name by stripping emoji

#### Relations
- **Many-to-many:** Tasks and Projects can link to multiple areas
- Example: Vacation project → FUN + PERSONAL & FAMILY
- Most tasks/projects have 1 area; multiple areas is rare

#### Sync Direction
- **One-way:** Todoist → Notion only
- Area relations in Notion are **read-only** from sync perspective
- Editing area relations in Notion does **NOT** sync back to Todoist

#### No Area Label
- If task/project has no area label in Todoist → AREAS property is blank in Notion
- Adding area label later in Todoist → Notion updates on next reconciliation

#### Deletion
- If area deleted from Notion AREAS DB → tasks/projects show no area relation
- Sync does **not** recreate deleted areas

#### Future Enhancements
- 🔮 Bidirectional sync: Edit AREAS relation in Notion → update Todoist labels

---

## 📋 Data Type 2: TASKS

### Overview
Tasks are the atomic units of work. They sync from Todoist to Notion's "Todo DB" and maintain rich metadata.

### The `capsync` Label

#### Auto-labeling Logic
Sync automatically adds `capsync` label to tasks that meet **ALL** criteria:
1. **Non-repeating** (not recurring)
2. **In a project** (not in "Inbox")

#### Auto-labeling Scenarios

| Scenario | Action |
|----------|--------|
| Task created in project (non-recurring) | Auto-add `capsync` |
| Task moved: Inbox → Project | Auto-add `capsync` |
| Task moved: Project → Inbox | Auto-remove `capsync` |
| Task changes: Recurring → One-off | Auto-add `capsync` |
| Task changes: One-off → Recurring | Auto-remove `capsync` |

#### Label Creation
- If `capsync` label doesn't exist in Todoist, sync will create it
- Webhook events are unreliable; reconciliation (every 5 min) ensures labels are added

#### Inbox Handling
- Tasks in Inbox are **never** synced, even if in sections within Inbox
- Sections within Inbox = still considered Inbox

---

### Task Sync Rules

#### Creation
- **One-way:** Todoist → Notion only
- Creating task in Notion does **not** sync to Todoist *(future enhancement)*

#### Properties Synced (Todoist → Notion)
- Title/Content
- Priority (P1-P4 → 🔴🟠🟡⚪)
- Status (checkbox/completion)
- Due Date
- Description
- Labels (excluding system labels like `capsync`)
- Project relation
- AREAS relation
- People relation (assignees)
- Todoist Task ID
- Comments

#### Conflict Resolution
- **Todoist always wins** for all properties
- Edits in Notion are overwritten on next reconciliation
- No timestamp comparison or conflict detection *(future enhancement)*

#### Notion Links in Todoist
On **first sync only**, sync adds to Todoist task description:
```
---
📝 View Task in Notion: [link to Notion task page]
📁 View Project in Notion: [link to Notion project page]
```
- Appended to existing description (doesn't overwrite user content)
- Separator (`---`) for visual distinction

#### Deletion
- **One-way:** Delete in Todoist → delete in Notion
- Deleting in Notion does **not** delete in Todoist *(future enhancement)*

#### Completion
- **One-way:** Complete in Todoist → check box in Notion
- Checking box in Notion does **not** complete in Todoist *(future enhancement)*
- Both active **and completed** tasks are synced

#### Comments
- **One-way:** Todoist comments → Notion
- Notion comments do **not** sync to Todoist *(future enhancement)*
- Exception: "View in Notion" links (see above)

---

### Orphaning Tasks

#### Removing `capsync` Label
If user manually removes `capsync` label in Todoist:
1. Sync appends to Notion page content: `Sync label was removed on [date]`
2. Task becomes **orphaned** (no longer synced)
3. Page remains in Notion (not deleted)

#### Re-syncing Orphaned Tasks
- If user manually re-adds `capsync` label → sync resumes
- This is an **extreme edge case**

---

### Subtasks

#### Representation in Notion
- Subtasks sync as **Notion toggle lists** in page content
- Appear flattened in Todo DB list view
- Todoist Task ID maintains consistency

#### Inheritance
Subtasks inherit from parent task:
- `capsync` label (auto-added)
- AREAS relation
- Project relation

#### Nesting Levels
- Sync **all nesting levels** (Task → Subtask → Sub-subtask)
- Typically 2 levels; 3+ levels is rare

#### Deletion
- Deleting parent task in Todoist → delete parent + all subtasks in Notion

---

## 📁 Data Type 3: PROJECTS

### Overview
Projects are containers for tasks. They sync from Todoist to Notion's "Projects DB" and provide organizational structure.

### Which Projects Sync
- **All active** (not archived) Todoist projects
- **Except "Inbox"** (Inbox never syncs)
- Both personal and team projects

### Project Sync Rules

#### Creation
- **One-way:** Todoist → Notion only
- Sync auto-creates project in Notion when it sees tasks with new project ID
- Only syncs projects with **≥1 task meeting sync criteria** (non-recurring + has `capsync`)

#### Properties

| Property | Initial Creation | Post-Creation Updates |
|----------|------------------|----------------------|
| **Name** | Todoist | **Notion wins** (bidirectional) |
| **Color** | Todoist | Ignored (no sync) |
| **AREAS** | Todoist (inherited from tasks) | Notion-controlled (no sync) |
| **Status** | "Active" | Synced bidirectionally (see below) |
| **Tasks Relation** | Auto-linked | Auto-maintained |

#### Name Sync (Bidirectional)
- **Post-creation:** If project name changes in Notion → update Todoist
- **Conflict:** Notion always wins (no timestamp comparison)

#### Status Property
- Notion Projects DB has "Status" select property: `Active` or `Archived`
- Syncs bidirectionally:
  - Archive in Todoist → Status = "Archived" in Notion
  - Unarchive in Todoist → Status = "Active" in Notion

#### Deletion
- **One-way:** Delete in Todoist → delete in Notion
- **Cascade:** All tasks in that project are also deleted in Notion
- This is a **rare** operation

#### Project Becomes Empty
- Project had synced tasks, but all tasks removed/deleted
- → Status set to "Archived" in Notion (preserves information)

---

### Project AREAS Inheritance

#### Logic
- Project AREAS are inherited from **all areas present** in project's tasks
- Example: Project with 5 WORK tasks + 2 HOME tasks → AREAS: WORK, HOME

#### When Applied
- **At project creation only**
- Post-creation, AREAS are **Notion-controlled** (no auto-updates from tasks)
- This prevents churn as task composition changes

#### Multiple Areas
- Projects can have multiple AREAS (many-to-many relation)
- Unusual but supported (e.g., vacation project spanning FUN + PERSONAL & FAMILY)

---

### Notion Link in Todoist
- Todoist projects have **no description field**
- Sync adds Notion link as **project comment** on first sync:
  ```
  📁 View Project in Notion: [link to Notion project page]
  ```

---

### Project Sections
- Todoist sections (e.g., "To Do", "In Progress", "Done") are **ignored completely**
- No representation in Notion

---

## 🔄 Sync Execution

### Sync Order (Reconciliation)
Entities sync in this order to maintain referential integrity:

1. **AREAS** - Ensure all areas exist (though sync doesn't create them)
2. **Projects** - May need to link to areas
3. **Tasks** - May need to link to projects & areas  
4. **Subtasks** - Need parent tasks to exist

### Reconciliation Schedule
- Runs **every 2 hours (5am-9pm Pacific)** via Cloud Scheduler (cost-optimized)
- Fetches all Todoist tasks with `capsync` label (active + completed)
- Compares with Notion state
- Applies updates as needed
- 9 syncs per day during active hours, none overnight (saves ~60% on costs)

### Webhook Events
- Todoist webhooks provide real-time updates
- **Unreliable** (may miss events)
- Reconciliation acts as safety net

### Idempotency
- Sync computes payload hash to skip unchanged tasks
- Prevents unnecessary API calls and Notion updates

---

## 🚀 Future Enhancements

### High Priority
1. **Bidirectional Task Creation:** Create tasks in Notion → sync to Todoist
2. **Bidirectional Completion:** Check box in Notion → complete in Todoist
3. **Bidirectional Deletion:** Delete in Notion → delete in Todoist
4. **Bidirectional AREAS:** Edit area relations in Notion → update Todoist labels

### Medium Priority
5. **Conflict Detection:** Timestamp-based conflict resolution with warnings
6. **Subtask Toggle Lists:** Properly render subtasks as Notion toggle blocks
7. **Sync Status Dashboard:** Visibility into sync health, errors, orphaned tasks

### Low Priority
8. **Notion → Todoist Comments:** Sync Notion comments back to Todoist
9. **Project Sections Support:** Represent Todoist sections in Notion
10. **Recurring Task Support:** Option to sync recurring tasks with special handling

---

## 📊 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                         TODOIST                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  AREAS   │    │ PROJECTS │    │  TASKS   │              │
│  │ (labels) │    │          │    │          │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
└───────┼───────────────┼───────────────┼─────────────────────┘
        │               │               │
        │ One-way       │ Name: ←→      │ One-way
        │ (T→N)         │ Status: ←→    │ (T→N)
        │               │ Others: One   │
        ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                         NOTION                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ AREAS DB │    │PROJECTS  │    │ TODO DB  │              │
│  │          │◄───┤   DB     │◄───┤          │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                   (relations)     (relations)               │
└─────────────────────────────────────────────────────────────┘

Legend:
  →   One-way sync (Todoist → Notion)
  ←→  Bidirectional sync
  ◄── Database relations
```

---

## 🔧 Implementation Notes

### Key Files
- `app/handlers.py` - Reconciliation logic, auto-labeling
- `app/notion_client.py` - Notion API interactions, area/project/task creation
- `app/todoist_client.py` - Todoist API interactions, label management
- `app/mapper.py` - Property mapping (Priority, Labels, etc.)
- `app/store.py` - Firestore state management, idempotency

### Critical Functions
- `reconcile()` - Main reconciliation loop
- `ensure_area_exists()` - Area lookup/creation with race condition protection
- `sync_project_to_notion()` - Project sync with AREAS inheritance
- `sync_task_to_notion()` - Task sync with all properties
- `compute_payload_hash()` - Idempotency check

### Error Handling
- Graceful degradation on API errors
- Logging with structured context
- Firestore error state tracking

---

## 📝 Notes

- This document reflects the current implementation as of October 2025
- All "future enhancements" are documented but not yet implemented
- Sync respects existing data from weeks of prior operation
- Changes to these rules require careful migration planning

---

**Questions or Issues?** See `PROJECT_STATUS.md` or `GETTING_STARTED.md`








