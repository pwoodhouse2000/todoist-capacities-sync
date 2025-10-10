# 🔄 Todoist → Notion Sync Setup Guide

**Last Updated**: October 2025  
**Difficulty**: Beginner  
**Time Required**: 10-15 minutes

## 📋 Overview

This service syncs your Todoist tasks (with the `capsync` label) to Notion databases automatically. This guide will walk you through the complete setup process with detailed instructions and common pitfalls to avoid.

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

## 🆘 Troubleshooting

### Common Issues & Solutions

#### Issue: "Labels is not a property that exists"
**Cause**: Property name mismatch or missing property  
**Solution**:
1. Open your Tasks database in Notion
2. Check the property is named exactly "Labels" (case-sensitive)
3. Verify it's type "Multi-select"
4. If it's named "Label" (singular), rename it to "Labels"

#### Issue: "No tasks with @capsync label found"
**Cause**: Label not saved or misspelled  
**Solutions**:
- Label is case-sensitive: use `capsync` not `Capsync`
- Don't include @ symbol when creating the label in Todoist
- Verify label is saved (refresh Todoist)
- Check using: `curl "http://localhost:8000/test/todoist?capsync_only=true"`

#### Issue: "Integration doesn't have access"
**Cause**: Databases not shared with integration  
**Solution**:
1. Open each database in Notion
2. Click "•••" menu → "Connections"
3. Find your integration and click to connect
4. Verify with: `curl "http://localhost:8000/test/notion"`

#### Issue: "Invalid database ID format"
**Cause**: Database ID includes URL parameters  
**Solution**:
- Database ID should be 32 hex characters: `28789c4a21dd80db9edcfe4ffb342bfb`
- Remove any `?` or `&` and everything after them
- Remove hyphens if present

#### Issue: Task synced but missing content
**Cause**: Property type mismatch  
**Solution**:
- Verify all properties match the exact types specified
- "Todoist Task ID" must be "Text" not "Number"
- "Project" must be "Relation" linking to Projects database

## 📚 Lessons Learned

### Best Practices

1. **Label Naming**
   - Use lowercase: `capsync` not `@capsync` or `Capsync`
   - The @ symbol is only for our documentation
   - Todoist labels are case-sensitive

2. **Property Names**
   - Match names exactly (case-sensitive)
   - Use plural "Labels" not singular "Label"
   - Don't use special characters in property names

3. **Database Setup Order**
   - Create Projects database first
   - Then create Tasks database
   - Add "Project" relation last (needs Projects to exist)

4. **Testing Flow**
   - Test API connections first (`./test_apis.sh`)
   - Do a dry run before real sync
   - Start with one simple task
   - Check Notion immediately after sync

5. **Common Mistakes to Avoid**
   - ❌ Not sharing databases with integration
   - ❌ Using full database URLs instead of IDs
   - ❌ Creating label with @ symbol in Todoist
   - ❌ Misspelling property names
   - ❌ Using wrong property types (Text vs Number)

### Performance Tips

1. **For Many Tasks**
   - Sync a few tasks first to verify setup
   - Then add label to more tasks in batches
   - Use filters in Todoist to add labels in bulk

2. **Notion Views**
   - Create filtered views for active tasks
   - Use calendar view for tasks with due dates
   - Create kanban by priority or project

3. **Organization**
   - Use Notion's relation property to link tasks to projects
   - Create rollups in Projects to see task counts
   - Add formulas for task completion percentages

## 🎯 Next Steps

Once setup is complete:

### 1. **Test the Sync**
```bash
# Start the service
./run_simple.sh

# Test APIs
./test_apis.sh

# Find a task with capsync label
curl "http://localhost:8000/test/todoist?capsync_only=true"

# Sync it to Notion
curl "http://localhost:8000/test/sync-task/TASK_ID?dry_run=false"
```

### 2. **Deploy to Production** (Optional)
See [DEPLOYMENT.md](DEPLOYMENT.md) for deploying to Google Cloud Run for:
- Automatic webhook-based sync
- Hourly reconciliation
- Scalable infrastructure

### 3. **Customize Your Notion Databases**
- Add custom properties for your workflow
- Create filtered views and templates
- Set up relations to other databases

## 🔄 Updating the Integration

If you need to change configuration:

1. **Update Environment Variables**
   ```bash
   # Edit .env file
   nano .env
   
   # Restart service
   pkill -f uvicorn
   ./run_simple.sh
   ```

2. **Test Changes**
   ```bash
   ./test_apis.sh
   ```

3. **Verify Sync Still Works**
   ```bash
   curl "http://localhost:8000/test/sync-task/TASK_ID?dry_run=true"
   ```

## 📞 Getting Help

If you encounter issues:

1. **Check Logs**
   ```bash
   tail -f /tmp/uvicorn.log
   ```

2. **Verify Configuration**
   ```bash
   # Test Todoist connection
   curl "http://localhost:8000/test/todoist"
   
   # Test Notion connection
   curl "http://localhost:8000/test/notion"
   ```

3. **Review Documentation**
   - [CODE_REVIEW.md](CODE_REVIEW.md) - Security and best practices
   - [API.md](API.md) - API endpoint documentation
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment

4. **Open an Issue**
   - [GitHub Issues](https://github.com/pwoodhouse2000/todoist-capacities-sync/issues)
   - Include error messages and logs
   - Describe what you've already tried

## 🎉 Success Checklist

- ✅ Notion integration created
- ✅ Two databases created with correct properties
- ✅ Databases shared with integration
- ✅ Database IDs added to `.env`
- ✅ Service starts without errors
- ✅ Both API tests pass
- ✅ Test task synced successfully
- ✅ Task visible in Notion with all data

**Congratulations! Your Todoist → Notion sync is fully operational!** 🚀

Now you can:
- Add `capsync` label to any Todoist task to sync it
- Edit tasks in Todoist and they'll update in Notion
- Use Notion's powerful views and relations
- Keep Todoist as your task entry point

Enjoy your enhanced productivity workflow! 💪

