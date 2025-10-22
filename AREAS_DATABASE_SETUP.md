# ⚠️ AREAS Database Configuration Required

## Issue

The AREAS property is not being set because `notion_areas_database_id` is not configured.

## Root Cause

In your Notion workspace, you have:
- ✅ Tasks database (configured)
- ✅ Projects database (configured)  
- ❌ AREAS database (NOT configured in GCP)

## How to Fix

### Step 1: Find Your AREAS Database ID

1. Open your Notion workspace
2. Find the **AREAS** database
3. Click on it to open
4. Look at the URL in the browser:
   `https://www.notion.so/[WORKSPACE]/[DATABASE_ID]?v=...`
5. Copy the 32-character DATABASE_ID (looks like: `28789c4a21dd801bac9a1234567890ab`)

### Step 2: Add to GCP Secret Manager

For **production/Cloud Run** deployment:

```bash
gcloud secrets create NOTION_AREAS_DATABASE_ID \
  --data-file=- \
  --project=notion-todoist-sync-464419 << 'END'
YOUR_AREAS_DATABASE_ID_HERE
END
```

For **local development** (.env file):

```bash
echo "NOTION_AREAS_DATABASE_ID=YOUR_AREAS_DATABASE_ID_HERE" >> .env
```

### Step 3: Deploy Again

After adding the secret:

```bash
cd /Users/pwoodhouse/Documents/SW\ Projects/TodoistCapacitiesSynvV1

# Reapply SSL fix
python3 -c "import certifi, subprocess; subprocess.run(['gcloud', 'config', 'set', 'core/custom_ca_certs_file', certifi.where()])"

# Deploy
gcloud run deploy todoist-notion-sync --source . \
  --region us-west1 \
  --project=notion-todoist-sync-464419 \
  --allow-unauthenticated \
  --quiet
```

### Step 4: Test It

1. Create a test task in Todoist with:
   - Label: `@capsync`
   - Label: `PERSONAL & FAMILY 📁`

2. Wait for webhook to sync (or manually trigger)

3. Check Notion - **AREAS property should now be populated!** ✅

## Configuration Checklist

- [ ] Found AREAS database ID in Notion
- [ ] Added NOTION_AREAS_DATABASE_ID to GCP Secret Manager
- [ ] Redeployed Cloud Run service
- [ ] Created test task with PERSONAL & FAMILY label
- [ ] AREAS property is now showing in Notion ✅

## Optional: People Database

If you also want people matching to work, configure:

```bash
gcloud secrets create NOTION_PEOPLE_DATABASE_ID \
  --data-file=- \
  --project=notion-todoist-sync-464419 << 'END'
YOUR_PEOPLE_DATABASE_ID_HERE
END
```

---

**Once configured and redeployed, AREAS will be set automatically for all tasks!**

