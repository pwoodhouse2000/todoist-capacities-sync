# ⚠️ Deployment Blockers - October 16, 2025

## Issue: AREAS Property Not Setting in Notion

Your Notion task shows:
- ✅ Labels: PERSONAL & FAMILY 📁, capsync (correctly synced)
- ✅ Project: PERSONAL & FAMILY (correctly synced)
- ❌ AREAS: Empty (NOT synced - this is the issue)

## Root Cause

The fix for PERSONAL & FAMILY area extraction was **committed to GitHub but NOT deployed** to Cloud Run due to SSL certificate verification issues.

**Current Deployed Code:** Revision todoist-notion-sync-00025-wfg (from earlier today, before people matching fix)
**Latest Code in GitHub:** Commit 4268950 (people matching fix) - NOT YET DEPLOYED

## Why Deployment Failed

```
Error: SSLError: certificate verify failed: 
self-signed certificate in certificate chain
```

This is a system-level SSL certificate verification issue on the local machine preventing `gcloud` from communicating with Google Cloud servers.

## Changes That Need Deployment

### 1. ✅ PARA Area Fix (Commit 436fcd2)
- Fixed `extract_para_area()` to handle "PERSONAL & FAMILY" correctly
- Extracts full multi-word areas instead of just first word

### 2. ✅ People Matching Fix (Commit 4268950)  
- Improved fuzzy matching algorithm
- Prevents "MatthewA" from matching "Matt Osse"

Both are in GitHub main branch but not yet on Cloud Run.

## Solutions to Deploy

### Option 1: Deploy from Different Machine
If you have another computer with working gcloud setup:
```bash
cd todoist-capacities-sync
git pull origin main
gcloud run deploy todoist-notion-sync --source . --region us-west1 \
  --project=notion-todoist-sync-464419 --allow-unauthenticated --quiet
```

### Option 2: Use GitHub Actions or CI/CD
Set up automated deployment on push to main branch.

### Option 3: Fix Local SSL Issue
```bash
# Check Python SSL setup
python3 -c "import ssl; print(ssl.get_default_verify_paths())"

# Try updating certificates
/Applications/Python\ 3.9/Install\ Certificates.command
```

### Option 4: Use Terraform Directly
```bash
cd infra/terraform
terraform init
terraform plan -var="image=<new_image_uri>"
terraform apply -var="image=<new_image_uri>" -auto-approve
```

## What Will Work Once Deployed

Once either fix is deployed to Cloud Run:

✅ Tasks with "PERSONAL & FAMILY 📁" label will have AREAS property set correctly
✅ "MatthewA" will match "Matthew Anderson" instead of "Matt Osse"

## Testing Instructions

After deployment:

1. Create a test task in Todoist with labels:
   - `@capsync`
   - `PERSONAL & FAMILY 📁`

2. Wait for webhook to trigger (or manually trigger reconciliation)

3. Check Notion task - AREAS property should be set to "PERSONAL & FAMILY"

## Code Status

| Commit | Status | Deployed? |
|--------|--------|-----------|
| 436fcd2 | PARA Area Fix | ❌ NO - SSL issue |
| 4268950 | People Matching Fix | ❌ NO - SSL issue |
| Deployed: todoist-notion-sync-00025-wfg | Earlier version | ✅ YES (on Cloud Run) |

## Next Steps

1. **Immediate:** Choose one of the deployment options above
2. **Deploy:** Get the latest code to Cloud Run
3. **Test:** Verify AREAS property is now being set
4. **Monitor:** Check Cloud Run logs for any errors

---

**Note:** The code is production-ready and tested. Only deployment is blocked by the SSL certificate issue.
