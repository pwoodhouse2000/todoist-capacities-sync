# 🔗 Webhook Setup - Quick Reference

## Your Webhook URL
```
https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook
```

## Setup Location
https://developer.todoist.com/appconsole.html

## Events to Enable
When configuring the webhook, check these events:

- ✅ `item:added` - New task created
- ✅ `item:updated` - Task modified
- ✅ `item:completed` - Task marked done
- ✅ `item:uncompleted` - Task unmarked
- ✅ `item:deleted` - Task deleted
- ✅ `note:added` - Comment added
- ✅ `note:updated` - Comment edited

## How to Test

### Option 1: Real Test (Recommended)
1. Create a new task in Todoist
2. Add the `capsync` label
3. Wait 2-5 seconds
4. Check your Notion Tasks database
5. The task should appear!

### Option 2: Simulated Test
```bash
cd "/Users/pete/SOFTWARE REPO/Todoist Notion Sync/todoist-capacities-sync"
./test_webhook_live.sh
```

### Option 3: Watch Logs Live
```bash
gcloud run services logs tail todoist-notion-sync \
  --region=us-west1 \
  --project=notion-todoist-sync-464419
```

Then create a task in Todoist with `capsync` label and watch the logs in real-time!

## What Happens When Webhook Works

### Before Webhook:
- 😴 Tasks sync every 15 minutes via reconciliation
- ⏰ Up to 15-minute delay

### After Webhook:
- ⚡ Tasks sync in 2-5 seconds
- 🎯 Instant updates when you change a task
- 💬 Comments sync immediately
- ✅ Completion status syncs instantly

## Troubleshooting

### Webhook shows "Failed" or "Inactive"
- Verify the URL is exactly correct
- Make sure Cloud Run service is running: `curl https://todoist-notion-sync-769386743044.us-west1.run.app/health`
- Try deleting and re-adding the webhook

### Tasks still not syncing immediately
1. Check webhook status in Todoist console (should be "Active")
2. Watch the logs while creating a task
3. Verify the task has `capsync` label

### View Recent Webhook Activity
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=todoist-notion-sync AND jsonPayload.message=~'webhook'" \
  --limit=10 \
  --project=notion-todoist-sync-464419 \
  --format="table(timestamp,jsonPayload.message)"
```

## Success Indicators

✅ Webhook shows "Active" status in Todoist console
✅ Creating task with `capsync` → appears in Notion within 5 seconds
✅ Updating task → changes appear immediately in Notion
✅ Completing task → status updates in Notion
✅ Logs show "Received Todoist webhook" messages

## Current Status

- Service URL: ✅ Active
- Service Health: ✅ Healthy
- Todoist API: ✅ Connected
- Notion API: ✅ Connected
- Tasks with capsync label: 10
- Webhook: ⏳ **Needs Configuration** (follow steps above)

---

**Once configured, your sync will be fully automatic and real-time!** 🚀

