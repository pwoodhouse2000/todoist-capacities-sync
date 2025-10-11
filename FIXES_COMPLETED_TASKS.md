# 🐛 Bug Fixes - Completed Tasks & Sync Tracking

## Issues Fixed (October 11, 2025)

### 1. ✅ Completed Tasks Now Check the Checkbox (Instead of Deleting)

**Problem:**
When marking a task as complete in Todoist, it was getting deleted/archived in Notion instead of having the "Completed" checkbox checked.

**Root Cause:**
Completed tasks in Todoist may not return labels in the API response, causing the code to think the task no longer had the `capsync` label and should be archived.

**Solution:**
- Added special handling for completed tasks
- If a task is marked as completed AND was previously synced, it will update the Notion checkbox even without the `capsync` label
- The `is_completed` field is properly mapped to the Notion "Completed" checkbox

**Code Changes:**
- `app/pubsub_worker.py` - Added logic to handle completed tasks without labels
- Now checks if task is completed and was previously synced before deciding to archive

**Test It:**
1. Mark a synced task as complete in Todoist
2. Wait 15 minutes (or trigger manual reconciliation)
3. Check Notion - the "Completed" checkbox should be checked ✅
4. The task should NOT be deleted/archived

---

### 2. 📊 Sync Source Tracking (Webhook vs Reconciliation)

**Feature Added:**
You can now see HOW a task was synced by checking Firestore or the logs.

**How It Works:**
- Each synced task now stores a `sync_source` field
- Value is either `"webhook"` or `"reconciliation"`
- Logged in Cloud Logging for debugging

**Check Sync Source:**

#### Option 1: Check Logs
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=todoist-notion-sync AND \
   jsonPayload.message='Processing sync message'" \
  --limit=20 \
  --project=notion-todoist-sync-464419 \
  --format="table(timestamp.date('%H:%M:%S'),jsonPayload.task_id,jsonPayload.sync_source)"
```

#### Option 2: Check Firestore
```bash
gcloud firestore documents get \
  "todoist-notion-v1_tasks/YOUR_TASK_ID" \
  --project=notion-todoist-sync-464419 \
  --format="value(data.sync_source)"
```

#### Option 3: Query via API
You can add an endpoint to query sync states (future enhancement)

**Interpreting Results:**
- `sync_source: "webhook"` = Real-time sync (2-5 seconds after change in Todoist)
- `sync_source: "reconciliation"` = Scheduled sync (every 15 minutes)

---

## Testing the Fixes

### Test 1: Completed Task Checkbox
1. Pick a task that's already synced to Notion
2. Mark it as complete in Todoist
3. Wait up to 15 minutes (or run manual reconciliation)
4. Check Notion - the Completed checkbox should be ✅
5. The task should still be visible (not deleted)

### Test 2: Sync Source Tracking
```bash
# Create a new task in Todoist with capsync label
# Then check the logs:
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   jsonPayload.sync_source IS NOT NULL" \
  --limit=10 \
  --project=notion-todoist-sync-464419 \
  --format="table(timestamp.date('%H:%M:%S'),jsonPayload.message,jsonPayload.sync_source,jsonPayload.task_id)"
```

---

## Manual Reconciliation Command

To test immediately without waiting 15 minutes:

```bash
curl -X POST "https://todoist-notion-sync-769386743044.us-west1.run.app/reconcile" \
  -H "Authorization: Bearer $(gcloud secrets versions access latest --secret=internal-cron-token --project=notion-todoist-sync-464419)" | jq
```

---

## Code Changes Summary

### Files Modified:
1. **app/models.py** - Added `sync_source` field to `TaskSyncState`
2. **app/pubsub_worker.py** - 
   - Added `sync_source` parameter to `process_message()` and `_handle_upsert()`
   - Fixed completed task handling
   - Stores sync_source in Firestore state
3. **app/handlers.py** - 
   - Passes `sync_source="reconciliation"` during reconciliation

### New Fields:
- `TaskSyncState.sync_source` (Optional[str]) - Tracks how the task was synced

---

## Expected Behavior After Fixes

### Completed Tasks:
✅ Task marked complete in Todoist → Notion checkbox checked
✅ Task still visible in Notion
✅ Can be uncompleted in Todoist → Notion checkbox unchecks
❌ NOT deleted/archived unless capsync label is removed

### Sync Source Tracking:
✅ Webhook syncs: `sync_source = "webhook"` (instant, 2-5 seconds)
✅ Reconciliation syncs: `sync_source = "reconciliation"` (scheduled, every 15 min)
✅ Logged in Cloud Logging
✅ Stored in Firestore

---

## Deployment Info

- **Deployed**: October 11, 2025
- **Revision**: todoist-notion-sync-00010-rt7
- **Service URL**: https://todoist-notion-sync-769386743044.us-west1.run.app
- **Status**: ✅ Active

---

## Future Enhancements

Consider adding:
1. API endpoint to query sync states
2. Notion property to show sync source and timestamp
3. Dashboard to monitor sync statistics
4. Alert on repeated reconciliation syncs (might indicate webhook issues)

---

**The fixes are now live!** Test by completing a task in Todoist and watching it update in Notion instead of being deleted. 🎉

