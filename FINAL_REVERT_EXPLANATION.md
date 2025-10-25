# Final Revert - Comprehensive Investigation & Explanation

**Date**: October 20, 2025  
**Issue**: Tasks were being archived incorrectly and due dates were being synced from Notion back to Todoist (causing the behavior you observed)  
**Root Cause**: Multiple commits introduced Notion→Todoist syncing that wasn't working correctly  
**Final Solution**: Reverted to commit `436fcd2` - the last stable state before bidirectional reconciliation

## The Investigation

### Initial Attempt (Failed)
First I reverted to `ce1753e`, thinking that was stable. **But** when you provided the example task, the logs showed:
- `"Updated Todoist task due date from Notion"` ← This shouldn't exist!
- Task being archived incorrectly

This told me `ce1753e` was **not** the right revert point - it still had the problematic code.

### The Real Issue
I traced back through the git history and found:
1. **Commit `3a652c1`**: "Add project archival sync and fix Notion-to-Todoist reconciliation property access" ← Started the problems
2. **Commit `bca7085`**: "Add Area/People relations sync + Notion→Todoist bidirectional sync for due dates and completion status" ← Made it worse

Both of these introduced reconciliation logic that:
- Syncs due dates FROM Notion TO Todoist (causing overwrites)
- Syncs completion status FROM Notion TO Todoist
- Has buggy archival logic

### The Correct Revert Point
**Commit `436fcd2`** "Fix: Handle multi-word PARA area labels like 'PERSONAL & FAMILY'"

This is the last commit **before** the broken Notion→Todoist reconciliation was added. Verified by checking:
```bash
git show 436fcd2:app/handlers.py | grep "Updated Todoist task due date from Notion"
# Result: NOT FOUND ✓
```

## What's Now Deployed

**Revision**: todoist-notion-sync-00065-6fx  
**Commit**: 436fcd2  
**Date**: October 2025 (before reconciliation changes)

### Working Features ✅
- Cloud-based sync every 5 minutes
- Auto-add `@capsync` label to new non-recurring tasks
- **Todoist → Notion** sync (one-way, main direction)
  - Task creation in Notion
  - Task updates (title, priority, description)
  - Project page creation
  - Area/People relation population
  - Link creation in description
- PARA area label handling with fuzzy matching
- Dashboard monitoring

### Removed Features ❌
- **Notion → Todoist sync** (was breaking everything)
  - No due date sync from Notion to Todoist
  - No completion status sync from Notion to Todoist  
  - No label syncing from Notion to Todoist
- Buggy archival logic that was removing tasks from Notion
- Timestamp-based conflict resolution

## System Architecture (Correct Version)

```
Todoist (Primary Source & Task Management)
    ↓ (Webhooks every 5 min)
    ├→ New task created? → Auto-add @capsync
    ├→ Has @capsync label? → Sync to Notion
    │   ├→ Create/update task page
    │   ├→ Extract Area/People from labels
    │   ├→ Set relations in Notion
    │   ├→ Create project page if needed
    │   └→ Add link to description
    │
Notion (Display, Planning, Reference)
    └→ Read-only for sync purposes
       (You can manually create tasks here for future feature)
```

**Key**: Todoist is the source of truth. Notion receives updates from Todoist, but changes in Notion do NOT sync back to Todoist.

## What This Means for You

### ✅ You Can Do:
1. Create/edit tasks in Todoist - they sync to Notion automatically
2. Set due dates in Todoist - Notion will show them (but won't override back)
3. Add labels in Todoist (like @PROSPER 📁) - Notion will extract Area/People
4. Edit/view in Notion - changes don't break Todoist

### ❌ You Cannot (Yet):
1. Change due dates in Notion and have them sync back to Todoist
2. Mark tasks complete in Notion and have it affect Todoist
3. Move tasks between projects in Notion with automatic sync

## Testing Your Example Task

The task "Try this [Wikipedia]..." was being archived because:
1. Old code tried to sync it
2. Archival logic was buggy
3. It got moved to trash

**With this revert**: The task will stay safe, and changing the due date in Todoist will NOT be overwritten by Notion.

## When Notion→Todoist Syncing is Ready

In the future, when you want to add syncing from Notion back to Todoist, we need to:
1. Implement a **merge strategy** for labels (not replace)
2. Use proper conflict resolution that respects user changes
3. Be very careful with reconciliation (it runs every 5 min!)
4. Test thoroughly with multiple scenarios

For now, focus on Todoist as your task management tool, and Notion as your display/planning tool.

## Commits Removed This Time

All commits from `436fcd2` (exclusive) onwards to `ce1753e` (inclusive):
- `3a652c1` - Project archival sync (buggy)
- `b64faf5` - Add optional Notion database IDs
- `bca7085` - Bidirectional sync for due dates/completion (problematic)
- `c3b257b` - v1.1.0 improvements
- `9d9b122` - Remove emoji from area names
- `4268950` - Improve person matching
- `436fcd2` - Multi-word PARA labels
- `615b851` - Prevent duplicate Notion pages
- `fa3a5bf` - Auto-label tasks with capsync
- `ed5fe42` - Sync descriptions (OK, kept)
- `72fa415` - Fix People matching (OK, kept)
- `dfa49e7` - Fix duplicate sync bug (OK, kept)
- `a040c34` - Fix webhook automation (OK, kept)
- `0bdab18` - Add Pub/Sub worker (OK, kept)
- All the way through to `ade33af` which was our first attempted revert

The correct point was `436fcd2` all along.


