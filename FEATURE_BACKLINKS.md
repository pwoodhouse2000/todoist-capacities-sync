# 🔗 Bidirectional Linking Feature

## Overview

The service now automatically adds a link back to the Notion page in your Todoist task description!

## How It Works

### Before:
```
Todoist Task → Creates → Notion Page
                         (one-way)
```

### After:
```
Todoist Task ←→ Notion Page
(with link)     (bidirectional)
```

## What Gets Added

When a task is synced to Notion, the service automatically appends this to the Todoist task description:

```markdown
🔗 [View in Notion](https://notion.so/xxxxx)
```

### Example:

**Todoist Task Before:**
- Title: "Buy new sailing gloves"
- Description: "Need waterproof ones for December trip"

**Todoist Task After Sync:**
- Title: "Buy new sailing gloves"
- Description: "Need waterproof ones for December trip

🔗 [View in Notion](https://notion.so/28989c4a21dd8121b35be6ebd6f05973)"

## Smart Behavior

✅ **No duplicates**: Won't add link if one already exists  
✅ **Safe**: If adding link fails, sync still succeeds  
✅ **Clean formatting**: Adds proper spacing before the link  
✅ **Configurable**: Can be disabled via environment variable  

## Configuration

### Enable/Disable

Set in `.env` or environment variables:

```bash
# Enable backlinks (default)
ADD_NOTION_BACKLINK=true

# Disable backlinks
ADD_NOTION_BACKLINK=false
```

In production (GCP Secret Manager):
```bash
gcloud run services update todoist-notion-sync \
  --region=us-west1 \
  --project=notion-todoist-sync-464419 \
  --set-env-vars="ADD_NOTION_BACKLINK=true"
```

## Use Cases

### 1. Quick Access to Details
- See task in Todoist
- Click link to view full details, comments, and context in Notion

### 2. Knowledge Management
- Use Todoist for quick task capture
- Click link to access rich Notion page with research, notes, etc.

### 3. Project Context
- Task in Todoist shows what needs to be done
- Notion page has full project context and documentation

## Technical Details

### Implementation

**Files Modified:**
- `app/todoist_client.py` - Added `update_task_description()` method
- `app/pubsub_worker.py` - Added `_add_notion_backlink()` method
- `app/settings.py` - Added `add_notion_backlink` feature flag

**Process Flow:**
1. Task synced to Notion successfully
2. Get Notion page ID
3. Construct Notion URL
4. Check if link already exists in description
5. If not, append link with emoji and markdown formatting
6. Update Todoist task via API
7. Log success/failure (doesn't break sync if update fails)

### API Calls

**Additional Cost:**
- +1 Todoist API call per NEW task sync
- +0 calls for existing tasks (link already present)
- Minimal cost impact (~$0.05-0.10/month for typical usage)

### Idempotency

The backlink logic is idempotent:
- Checks if `notion.so` is already in description
- Won't add duplicate links
- Safe to run multiple times

## Testing

### Test the Feature

1. **Create a new task** in Todoist:
   ```
   Title: "Test backlink feature"
   Description: "This is my original description"
   Label: capsync
   ```

2. **Wait for sync** (up to 5 minutes)

3. **Check Todoist task**:
   - Open the task
   - Description should now have: "This is my original description

   🔗 [View in Notion](https://notion.so/xxxxx)"

4. **Click the link** - it should open the Notion page!

### Test Update (Won't Duplicate)

1. **Update the task** in Todoist (change title or add comment)
2. **Wait for sync**
3. **Check description** - should still have ONE link, not duplicated

## Logging

Look for these log messages:

```bash
# Successful backlink addition
gcloud logging read \
  "jsonPayload.message='Added Notion backlink to Todoist task'" \
  --project=notion-todoist-sync-464419 \
  --limit=10
```

```bash
# Already has link (skipped)
gcloud logging read \
  "jsonPayload.message='Notion link already in task description'" \
  --project=notion-todoist-sync-464419 \
  --limit=10
```

## Customization

### Change the Link Format

Edit `app/pubsub_worker.py`, line ~297:

```python
# Current format:
new_description = f"{task.description}{separator}🔗 [View in Notion]({notion_url})"

# Custom examples:
new_description = f"{task.description}{separator}📝 View full details: {notion_url}"
new_description = f"{task.description}{separator}[Open in Notion]({notion_url})"
new_description = f"{task.description}{separator}Notion: {notion_url}"
```

### Add Additional Metadata

You could also add:
```python
new_description = f"{task.description}{separator}🔗 [View in Notion]({notion_url})\n_Synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
```

## Troubleshooting

### Link not appearing

**Check:**
1. Feature enabled? `ADD_NOTION_BACKLINK=true`
2. Check logs for errors
3. Verify Todoist API token has write permissions
4. Check rate limits

### Multiple links appearing

**This shouldn't happen**, but if it does:
1. Check the idempotency logic in `_add_notion_backlink()`
2. Ensure `notion.so` check is working
3. Review logs for duplicate sync calls

## Benefits

✅ **Seamless workflow**: Capture in Todoist, expand in Notion  
✅ **Quick access**: One click to full context  
✅ **No manual linking**: Completely automatic  
✅ **Safe**: Won't break sync if backlink fails  
✅ **Smart**: Won't duplicate links on updates  

## Limitations

- Link is added to description only (not as a custom field)
- Requires Todoist API write permissions
- Adds small delay to sync (~0.5 seconds per task)
- One additional API call per new task

---

**Enjoy your bidirectional Todoist ↔ Notion workflow!** 🚀

