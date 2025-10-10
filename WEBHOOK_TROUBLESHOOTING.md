# 🔍 Webhook Troubleshooting

Your webhook shows as "Active" in Todoist but tasks aren't auto-syncing. Let's fix it!

---

## ⚠️ Most Likely Issue: URL Truncated

In your screenshot, the Callback URL shows:
```
https://todoist-notion-sync-769386743044.us-west1.run.ap
```

But it should be:
```
https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook
```

### Fix:
1. In Todoist, click on the **Callback URL** field
2. Verify the FULL URL (it might be cut off in the display)
3. If it's wrong or incomplete, update it to:
   ```
   https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook
   ```
4. Click **"Update webhook"**
5. Verify status still shows **"Active"**

---

## 🧪 Test if Webhook is Working

### Quick Test:
```bash
# Run this script to see recent tasks in Notion
./check_recent_sync.sh
```

### Live Test:
1. Create a NEW task in Todoist:
   - Title: "Webhook test [timestamp]"
   - Label: **capsync**
   
2. Wait 5 seconds

3. Run the check script:
   ```bash
   ./check_recent_sync.sh
   ```

4. If your new task appears → ✅ Webhook is working!
   If it doesn't appear → ❌ Webhook still has issues

---

## 🔧 Alternative: Check Webhook Directly

Visit the GCP Console to see logs:
https://console.cloud.google.com/run/detail/us-west1/todoist-notion-sync/logs?project=notion-todoist-sync-464419

Look for:
- ✅ `POST /todoist/webhook` - Todoist is sending events
- ❌ No webhook requests - Todoist isn't sending events

---

## 🎯 If Still Not Working

### Option 1: Try Deactivating and Re-adding Webhook
1. In Todoist, click **"Deactivate webhook"**
2. Wait 10 seconds
3. Re-add the webhook with the correct URL
4. Make sure all events are checked:
   - ✅ item:added
   - ✅ item:updated
   - ✅ item:completed
   - ✅ item:uncompleted
   - ✅ item:deleted
   - ✅ project:added
   - ✅ project:updated

### Option 2: Check Webhook Version
- Make sure it's set to **"Todoist API v1"** (as shown in your screenshot)
- Some webhook versions might have different payload formats

### Option 3: Check Events are Selected
Looking at your screenshot, these should be checked:
- ✅ item:added
- ✅ item:updated
- ✅ item:completed
- ✅ item:uncompleted
- ✅ item:deleted
- ✅ project:added
- ✅ project:updated

### Option 4: Verify Service is Running
```bash
# This should return "running"
curl -s https://todoist-notion-sync-769386743044.us-west1.run.app/ | grep status
```

### Option 5: Test Webhook Endpoint Manually
```bash
# Run the webhook test script
./test_webhook.sh
```

This simulates a Todoist webhook event. If it works, your service is fine and the issue is with Todoist sending events.

---

## 🐛 Common Issues

### Issue 1: URL Missing `/todoist/webhook`
**Symptom**: URL ends at `.app` without `/todoist/webhook`  
**Fix**: Add `/todoist/webhook` to the end of the URL

### Issue 2: Cold Start Delays
**Symptom**: First webhook takes 10+ seconds  
**Fix**: This is normal for Cloud Run. Subsequent requests are fast.

### Issue 3: Webhook Shows "Failed"
**Symptom**: Status shows "Failed" or "Inactive"  
**Fix**: 
- Verify URL is correct
- Check service is running
- Try deactivating and re-adding

### Issue 4: Only Some Events Work
**Symptom**: Task creation works but updates don't  
**Fix**: Check all desired events are checked in Todoist

---

## ✅ Success Indicators

Once working, you should see:
- ✅ Create task with `capsync` label → appears in Notion in 2-5 seconds
- ✅ Update task → changes sync to Notion
- ✅ Complete task → status updates in Notion
- ✅ Webhook logs appear in Cloud Run

---

## 🆘 Manual Sync Workaround

While debugging, you can manually sync tasks:

```bash
# List all capsync tasks
curl "https://todoist-notion-sync-769386743044.us-west1.run.app/test/todoist?capsync_only=true"

# Sync a specific task
curl "https://todoist-notion-sync-769386743044.us-west1.run.app/test/sync-task/TASK_ID?dry_run=false"
```

---

## 📞 Need More Help?

1. Check the full webhook URL in Todoist (click the field to see it all)
2. Run `./check_recent_sync.sh` after creating a test task
3. Try the live test above
4. Check Cloud Console logs for any errors

**Most likely fix**: Just verify the URL is complete in Todoist! The UI might be truncating it for display, but the actual value needs to be correct.

