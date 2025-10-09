# 🔄 Todoist → Notion Sync Setup Guide

## 📋 Overview

This service now syncs your Todoist tasks (with the `@capsync` label) to Notion databases! The migration from Capacities to Notion is complete.

## 🚀 Quick Setup (5 Steps)

### 1. Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **"+ New integration"**
3. Name it: `Todoist Sync`
4. Select your workspace
5. **Copy the "Internal Integration Secret"** (starts with `secret_...`)

### 2. Create Two Notion Databases

#### Projects Database

1. In Notion, create a new **full-page database**
2. Name it: `Todoist Projects`
3. Add these properties:
   - **Name** (Title) - already exists
   - **Todoist Project ID** (Text)
   - **Todoist URL** (URL)
   - **Color** (Select) - optional
   - **Is Shared** (Checkbox) - optional

#### Tasks Database

1. Create another **full-page database**
2. Name it: `Todoist Tasks`
3. Add these properties:
   - **Name** (Title) - already exists
   - **Todoist Task ID** (Text)
   - **Todoist URL** (URL)
   - **Priority** (Select) - create options: P1, P2, P3, P4
   - **Labels** (Multi-select)
   - **Due Date** (Date)
   - **Completed** (Checkbox)
   - **Project** (Relation) → Link to your "Todoist Projects" database

### 3. Share Databases with Your Integration

1. Open each database page
2. Click the **"•••"** menu (top right)
3. Scroll to **"Connections"** or **"Add connections"**
4. Select your `Todoist Sync` integration
5. Repeat for both databases

### 4. Get Database IDs

#### Method 1: From the URL

Open each database as a full page. The URL will look like:
```
https://www.notion.so/workspace-name/<DATABASE_ID>?v=...
```

The DATABASE_ID is the 32-character string (with hyphens) after your workspace name.

Example:
```
https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6?v=...
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                   This is your database ID
```

#### Method 2: Using "Copy link to database"

1. Click the **"•••"** menu on the database
2. Choose **"Copy link"**
3. Extract the ID from the URL

### 5. Update Your `.env` File

Edit the `.env` file in your project root:

```bash
# Todoist API (already configured)
TODOIST_OAUTH_TOKEN=c48f86e2730782b3b263e45b3f589ccad89e5b66

# Notion API - Add these!
NOTION_API_KEY=secret_YOUR_INTEGRATION_SECRET_HERE
NOTION_TASKS_DATABASE_ID=YOUR_TASKS_DATABASE_ID_HERE
NOTION_PROJECTS_DATABASE_ID=YOUR_PROJECTS_DATABASE_ID_HERE

# Internal token for cron jobs
INTERNAL_CRON_TOKEN=dev-token-change-in-production
```

## ✅ Testing Your Setup

### 1. Start the Service

```bash
./run_simple.sh
```

Wait for the service to start (you'll see "Application startup complete").

### 2. Run the Test Script

In a **new terminal**:

```bash
chmod +x test_apis.sh
./test_apis.sh
```

You should see:
- ✅ Service is running
- ✅ Todoist API connected successfully
- ✅ Notion API connected successfully

### 3. Test Syncing a Real Task

1. **In Todoist**: Create a test task and add the `@capsync` label
2. **Get the task ID**: 
   - Use the test endpoint: `curl "http://localhost:8000/test/todoist?show_tasks=true"`
   - Find your task in the output and copy its numeric ID

3. **Test dry run** (simulation):
   ```bash
   curl "http://localhost:8000/test/sync-task/YOUR_TASK_ID?dry_run=true" | python3 -m json.tool
   ```

4. **Actually sync to Notion**:
   ```bash
   curl "http://localhost:8000/test/sync-task/YOUR_TASK_ID?dry_run=false" | python3 -m json.tool
   ```

5. **Check Notion**: You should see:
   - A new page in your Projects database (if it didn't exist)
   - A new page in your Tasks database with all the task details!

## 🎯 What Gets Synced?

### From Todoist → Notion

**Project Information:**
- Project name
- Todoist project URL
- Color
- Shared status

**Task Information:**
- Task title
- Description (in page body)
- Priority (P1-P4)
- Due date
- Labels (as multi-select)
- Completion status
- Comments (in page body)
- Link to project page (relation)

## 🔧 Troubleshooting

### "Notion API error"

**Check:**
1. Integration secret is correct in `.env`
2. Database IDs are correct (32 chars with hyphens)
3. Databases are **shared** with your integration
4. All required properties exist in your databases

### "Task does not have @capsync label"

**Solution:**
- Add the `@capsync` label to your task in Todoist
- Only tasks with this label will sync

### "Failed to create in Notion"

**Common causes:**
1. Missing properties in database (check the error message)
2. Integration doesn't have access to database
3. Wrong database ID

## 📚 Next Steps

Once testing works:

1. **Set up webhooks** (for automatic sync on Todoist changes)
2. **Deploy to Google Cloud Run** (for production)
3. **Configure hourly reconciliation** (to catch any missed updates)

All the infrastructure code is already in place - just needs GCP setup!

## 🆘 Need Help?

- Check the logs: `tail -f /tmp/uvicorn.log`
- Test individual components using the `/test/*` endpoints
- Verify all credentials and IDs are correct

## 🎉 Success!

Once you see your Todoist tasks appearing in Notion, you're all set! The architecture is designed for:
- ✅ Real-time sync via webhooks
- ✅ Automatic project creation
- ✅ Conflict resolution (updates existing pages)
- ✅ Scalable cloud deployment

Enjoy your new Todoist ↔ Notion sync! 🚀

