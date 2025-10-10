# 🔍 Quick Debug Guide

## Current Status

✅ **Service is working** - Manual sync tested successfully  
❌ **Webhook not configured** - Todoist isn't sending events yet

---

## Fix: Configure Todoist Webhook

### Step 1: Access Todoist Developer Console
1. Go to: **https://developer.todoist.com/appconsole.html**
2. Sign in with your Todoist account
3. You should see your apps listed

### Step 2: Create or Select App
- If you have an app already, select it
- If not, click **"Create a new app"**
  - Name: "Notion Sync" (or whatever you prefer)
  - Description: "Sync Todoist tasks to Notion"
  - Click "Create"

### Step 3: Add Webhook
1. In your app settings, find the **"Webhooks"** section
2. Click **"Add Webhook"** or **"+"**
3. Fill in:
   ```
   Webhook URL: https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook
   ```
4. Select events to watch:
   - ✅ `item:added`
   - ✅ `item:updated`  
   - ✅ `item:completed`
   - ✅ `item:uncompleted`
   - ✅ `item:deleted`
   - ✅ `project:added`
   - ✅ `project:updated`
5. Click **"Save"** or **"Add"**

### Step 4: Verify Webhook Shows "Active"
- The webhook should show a green status or "Active"
- You'll see a Webhook ID and possibly a secret

---

## Testing After Setup

### Test 1: Create a new task in Todoist
```bash
1. Open Todoist
2. Create a new task
3. Add the label: capsync
4. Wait 2-3 seconds
5. Check your Notion Tasks database
```

### Test 2: Update an existing task
```bash
1. Change the title of a synced task
2. Wait 2-3 seconds
3. Check if the change appears in Notion
```

### Test 3: Check logs (if it's not working)
```bash
# View recent service activity
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=todoist-notion-sync" \
  --limit=20 \
  --project=notion-todoist-sync-464419 \
  --format="value(timestamp,jsonPayload.message)"
```

Or visit the Cloud Console:
https://console.cloud.google.com/run/detail/us-west1/todoist-notion-sync/logs?project=notion-todoist-sync-464419

---

## Manual Sync (Workaround)

While webhook is being set up, you can manually sync tasks:

```bash
# Sync a specific task by ID
curl "https://todoist-notion-sync-769386743044.us-west1.run.app/test/sync-task/YOUR_TASK_ID?dry_run=false"

# Example:
curl "https://todoist-notion-sync-769386743044.us-west1.run.app/test/sync-task/9625088106?dry_run=false"
```

To get task IDs:
```bash
curl "https://todoist-notion-sync-769386743044.us-west1.run.app/test/todoist?capsync_only=true"
```

---

## Common Issues

### Issue: Webhook shows "Failed" or "Inactive"
**Solution**: 
- Check the webhook URL is exactly: `https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook`
- Ensure Cloud Run service is running (visit the URL in browser)
- Try deleting and re-adding the webhook

### Issue: Task doesn't have `capsync` label
**Solution**: Only tasks with the `capsync` label will sync. Add it to your tasks.

### Issue: Changes not appearing in Notion
**Solution**:
1. Check Cloud Run logs for errors
2. Verify Notion databases have the right properties
3. Try manual sync to see if it works

### Issue: "Service Unavailable" errors
**Solution**:
- Cloud Run may be cold-starting (takes 5-10 seconds for first request)
- Webhook timeout may be too short - Todoist should retry automatically

---

## Webhook Event Format

When configured, Todoist will send POST requests like this:

```json
{
  "event_name": "item:added",
  "user_id": "12345",
  "event_data": {
    "id": "9625088106",
    "content": "Task name",
    "project_id": "123",
    "labels": ["capsync"],
    ...
  }
}
```

Your service receives this, publishes to Pub/Sub, and processes asynchronously.

---

## Test Webhook Manually

Run the test script:
```bash
cd /Users/pwoodhouse/Documents/SW\ Projects/TodoistCapacitiesSynvV1
./test_webhook.sh
```

This simulates a Todoist webhook event to verify your endpoint works.

---

## Success Indicators

✅ Webhook shows "Active" in Todoist console  
✅ Creating a task with `capsync` label → appears in Notion within 5 seconds  
✅ Updating task in Todoist → updates in Notion  
✅ Completing task in Todoist → marks complete in Notion  
✅ Cloud Run logs show webhook events being received  

---

## Need Help?

1. **Check service health**:
   ```bash
   curl https://todoist-notion-sync-769386743044.us-west1.run.app/
   ```

2. **Check Notion connection**:
   ```bash
   curl https://todoist-notion-sync-769386743044.us-west1.run.app/test/notion
   ```

3. **View logs in GCP Console**:
   https://console.cloud.google.com/run/detail/us-west1/todoist-notion-sync/logs?project=notion-todoist-sync-464419

---

## Once It's Working

After webhook is configured, your sync will be **fully automatic**:
- Create task with `capsync` → appears in Notion instantly
- Update task → syncs immediately
- Complete task → updates Notion status
- No manual intervention needed! 🎉

