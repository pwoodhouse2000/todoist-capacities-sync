# Deployment Status - October 22, 2025

## Latest Changes (Committed & Pushed)

### Commit: a0220df
**fix: Set Status property to Active when creating/updating Notion projects**

Projects now properly have their Status property set to 'Active' when:
- Creating a new project page in Notion
- Updating an existing project page in Notion

The Status property will be updated to 'Archived' by the reconciliation
handler when a project is archived in Todoist.

### Commit: 59a95fb  
**fix: Resolve critical bugs in sync worker**

- Bug #1: Implement snapshot parsing to avoid unnecessary API calls
- Bug #2: Consolidate duplicate existing_state fetches  
- Bug #3: Verify Completed checkbox properly synced
- Tests: Update end-to-end tests to match new function signatures

## Current Deployment Status

**Latest Deployed Revision**: todoist-notion-sync-00075-8qq
- Status: ✅ HEALTHY
- Health Check: ✅ PASSING

## Pending Deployment

The following commits are ready to deploy but blocked by local SSL certificate issues:

```
a0220df fix: Set Status property to Active when creating/updating Notion projects
59a95fb fix: Resolve critical bugs in sync worker
```

Both commits are:
- ✅ Tested locally (unit tests passing)
- ✅ Pushed to GitHub main branch
- ✅ Ready for production

## How to Deploy

### Option 1: GitHub Actions (Recommended)
Set up a GitHub Actions workflow to deploy on push to main branch.
This avoids local SSL issues and ensures consistent deployments.

### Option 2: From Another Machine
If you have another computer with working gcloud setup:
```bash
git clone https://github.com/pwoodhouse2000/todoist-capacities-sync.git
cd todoist-capacities-sync
gcloud run deploy todoist-notion-sync --source . \
  --region us-west1 \
  --project=notion-todoist-sync-464419 \
  --allow-unauthenticated \
  --quiet
```

### Option 3: Google Cloud Console
1. Go to Cloud Run in Google Cloud Console
2. Click on "todoist-notion-sync" service
3. Click "Deploy new revision"
4. Set "Source code" to GitHub
5. Select the main branch

### Option 4: Fix Local SSL Issue
The local issue is a self-signed certificate in the cert chain. Try:
```bash
# Reinstall Python certificates
/Applications/Python\ 3.9/Install\ Certificates.command

# Or clear gcloud config
gcloud config unset core/custom_ca_certs_file
gcloud auth application-default login
```

## Testing Done

✅ 49 unit tests passing (mapper, utils, models)
✅ Code linting: no errors
✅ Snapshot parsing: working correctly
✅ Idempotency checks: consistent
✅ Status property: now set on creation and updates

## Expected Behavior After Deployment

### New Projects
- Status property will be set to "Active"
- Will remain "Active" until project is archived in Todoist

### Project Updates  
- Status property will be maintained as "Active" for active projects
- Reconciliation will update to "Archived" when project archived in Todoist

### Snapshot Parsing
- Faster sync times for webhook-triggered tasks (uses cached data)
- Fewer API calls to Todoist

### Bug Fixes
- No more duplicate state fetches (prevents race conditions)
- Completed checkbox syncs correctly
- Idempotency checks work consistently
