# Todoist Webhook Configuration

## 🎯 Your Production Service

**Cloud Run URL**: `https://todoist-notion-sync-769386743044.us-west1.run.app`
**Webhook Endpoint**: `https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook`

---

## 📝 Setup Instructions

### Step 1: Go to Todoist App Management
1. Visit: https://developer.todoist.com/appconsole.html
2. Log in with your Todoist account
3. Click on your app or create a new one if needed

### Step 2: Configure Webhook
1. In your app settings, find the **Webhooks** section
2. Click **Add webhook**
3. Enter the following details:
   - **Webhook URL**: `https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook`
   - **Events to watch**:
     - ✅ `item:added`
     - ✅ `item:updated`
     - ✅ `item:completed`
     - ✅ `item:uncompleted`
     - ✅ `item:deleted`
     - ✅ `project:added`
     - ✅ `project:updated`

4. Click **Save** or **Create**

### Step 3: Verify Webhook
1. The webhook should show as "Active" in the console
2. You'll see a webhook ID and secret (note these for troubleshooting)

---

## 🧪 Testing Your Webhook

### Test 1: Create a Task
1. In Todoist, create a new task with the `capsync` label
2. Check your Notion Tasks database - the task should appear within a few seconds
3. Check Cloud Run logs: `gcloud run logs read todoist-notion-sync --region=us-west1 --project=notion-todoist-sync-464419 --limit=50`

### Test 2: Update a Task
1. Edit a task that was synced (change title, due date, or priority)
2. The changes should reflect in Notion within seconds

### Test 3: Complete a Task
1. Mark a synced task as complete in Todoist
2. The task should be marked complete in Notion

---

## 🔍 Monitoring

### View Logs
```bash
# Live tail logs
gcloud run logs tail todoist-notion-sync --region=us-west1 --project=notion-todoist-sync-464419

# Read recent logs
gcloud run logs read todoist-notion-sync --region=us-west1 --project=notion-todoist-sync-464419 --limit=100

# Filter for errors
gcloud run logs read todoist-notion-sync --region=us-west1 --project=notion-todoist-sync-464419 --limit=100 | grep ERROR
```

### Check Service Health
```bash
curl https://todoist-notion-sync-769386743044.us-west1.run.app/
```

### Test Notion Connection
```bash
curl https://todoist-notion-sync-769386743044.us-west1.run.app/test/notion
```

---

## 🐛 Troubleshooting

### Webhook Not Triggering
1. Verify webhook is "Active" in Todoist console
2. Check Cloud Run logs for incoming requests
3. Ensure the task has the `capsync` label
4. Check that the webhook URL is correct

### Tasks Not Syncing
1. Check Firestore for sync state:
   ```bash
   # View in console
   gcloud firestore --project=notion-todoist-sync-464419 console
   ```
2. Review Cloud Run logs for errors
3. Verify Notion database IDs are correct
4. Ensure Notion pages have required properties

### Rate Limiting
- Todoist: 450 requests per 15 minutes
- Notion: 3 requests per second
- The service handles retries automatically

---

## 📊 GCP Resources

All resources are in project: `notion-todoist-sync-464419`

| Resource | Location | Purpose |
|----------|----------|---------|
| Cloud Run Service | us-west1 | Main application |
| Firestore Database | us-west1 | State storage |
| Pub/Sub Topic | global | Job queue |
| Secret Manager | global | API credentials |
| Artifact Registry | us-west1 | Docker images |

---

## 🔄 Updating the Service

When you make code changes:

```bash
# 1. Commit changes
git add .
git commit -m "Update service"
git push

# 2. Rebuild and deploy
cd /Users/pwoodhouse/Documents/SW\ Projects/TodoistCapacitiesSynvV1
gcloud builds submit \
  --tag us-west1-docker.pkg.dev/notion-todoist-sync-464419/todoist-notion-sync/sync-service:latest \
  --project=notion-todoist-sync-464419

gcloud run deploy todoist-notion-sync \
  --image=us-west1-docker.pkg.dev/notion-todoist-sync-464419/todoist-notion-sync/sync-service:latest \
  --platform=managed \
  --region=us-west1 \
  --project=notion-todoist-sync-464419
```

---

## 💰 Cost Estimate

With typical usage (100 tasks, 10 updates/day):
- **Cloud Run**: ~$0.50/month (includes 2M requests free tier)
- **Firestore**: ~$0.25/month (includes 1GB free tier)
- **Pub/Sub**: ~$0.10/month (includes 10GB free tier)
- **Secret Manager**: Free (6 secrets, well under limits)

**Total**: ~$1/month or less

---

## 🎉 You're All Set!

Your service is now deployed and ready to sync. Just configure the webhook in Todoist and you're good to go!

