# 📁 PARA Method - AREAS Integration

## Overview

The sync service now fully supports the **PARA method** (Projects, Areas, Resources, Archives) by automatically linking tasks and projects to their corresponding AREAS in Notion!

## What is PARA?

PARA is a popular organizational method where:
- **Projects**: Short-term efforts with specific goals
- **Areas**: Long-term responsibilities (WORK, HOME, HEALTH, etc.)
- **Resources**: Topics of interest
- **Archives**: Completed items

This feature focuses on **Areas** - linking your tasks and projects to life/work areas.

---

## 🎯 How It Works

### 1. **Label-Based Area Detection**

The service detects AREAS from Todoist labels:

**Supported AREA Labels:**
- `HOME` or `HOME 📁`
- `HEALTH` or `HEALTH 📁`
- `PROSPER` or `PROSPER 📁`
- `WORK` or `WORK 📁`
- `PERSONAL & FAMILY` or `PERSONAL & FAMILY 📁`
- `FINANCIAL` or `FINANCIAL 📁`
- `FUN` or `FUN 📁`

**Label Detection is Smart:**
- ✅ Handles emoji suffixes (`PROSPER 📁`)
- ✅ Case-insensitive matching
- ✅ Works with or without emojis

### 2. **Inheritance from Projects**

**Key Feature:** Tasks inherit AREA from their Todoist project!

**Example:**
```
Todoist Project: "BVI 2025" with label "FUN 📁"
├─ Task: "Decide about water toys"
├─ Task: "Buy snorkel gear"
└─ Task: "Book catamaran"

All tasks → Automatically linked to FUN area in Notion!
```

**Precedence:**
1. Task has area label → Uses task's area
2. Task has no area label → Inherits from project's area
3. Neither has area label → No area relation set

### 3. **Automatic AREAS Page Creation**

The service automatically:
- ✅ Checks if AREA page exists in your AREAS database
- ✅ Creates it if missing
- ✅ Links task/project to the AREA page
- ✅ Maintains relations

---

## 📊 Database Setup

### Your AREAS Database

You already have this set up! ✅

**Location:** Your Notion workspace  
**Name:** AREAS  
**Properties:**
- **Name** (Title) - Area name (PROSPER, HOME, etc.)
- **Todoist Projects** (Relation) - Projects in this area
- **Todoist Tasks** (Relation) - Tasks in this area

### Todoist Tasks Database

**New Property Added:**
- **AREAS** (Relation → AREAS database) - Links to area page

### Todoist Projects Database

**New Property Added:**
- **AREAS** (Relation → AREAS database) - Links to area page

---

## 🔧 Configuration

### Step 1: Get Your AREAS Database ID

1. Open your AREAS database in Notion
2. Click "..." → Copy link
3. Extract the database ID from the URL:
   ```
   https://notion.so/xxxxx?v=yyyyy
                    ^^^^^
                    This is your database ID (32 characters)
   ```

### Step 2: Configure the Service

Add to your environment:

```bash
# In .env (for local testing)
NOTION_AREAS_DATABASE_ID=your_areas_database_id_here

# In production (GCP)
gcloud run services update todoist-notion-sync \
  --region=us-west1 \
  --project=notion-todoist-sync-464419 \
  --set-env-vars="NOTION_AREAS_DATABASE_ID=your_areas_database_id_here"
```

**Or add as a secret:**
```bash
echo -n "your_areas_database_id_here" | \
  gcloud secrets create NOTION_AREAS_DATABASE_ID --data-file=- \
  --project=notion-todoist-sync-464419

# Then update Cloud Run to use it
gcloud run services update todoist-notion-sync \
  --region=us-west1 \
  --project=notion-todoist-sync-464419 \
  --set-secrets="NOTION_AREAS_DATABASE_ID=NOTION_AREAS_DATABASE_ID:latest"
```

---

## 🎯 Examples

### Example 1: Project with AREA Label

**Todoist:**
```
Project: "PROSPER" with label "PROSPER 📁"
Task: "Review Q4 metrics" with label "capsync"
```

**What Happens:**
1. Project syncs → Creates page in "Todoist Projects" DB
2. Project page → Linked to "PROSPER" in AREAS DB
3. Task syncs → Creates page in "Todoist Tasks" DB
4. Task page → Linked to "PROSPER" in AREAS DB (inherited from project)

**Result in Notion:**
- AREAS/PROSPER page shows:
  - 1 related project ("PROSPER")
  - 1 related task ("Review Q4 metrics")

### Example 2: Task with Own AREA Label

**Todoist:**
```
Project: "Inbox" (no area label)
Task: "Annual checkup" with labels "capsync", "HEALTH 📁"
```

**What Happens:**
1. Task extracts "HEALTH" from labels
2. Finds/creates HEALTH page in AREAS
3. Links task to HEALTH area

### Example 3: BVI 2025 Vacation Planning

**Todoist:**
```
Project: "BVI 2025" with label "FUN 📁"
├─ "Decide about water toys" + capsync
├─ "Buy snorkel gear" + capsync
└─ "Book catamaran" + capsync
```

**Result:**
All 3 tasks automatically linked to FUN area! Perfect for separating work from fun. 🏖️

---

## 📈 Benefits

### 1. **Automatic Categorization**
✅ No manual work - areas detected from existing labels  
✅ Task inherits from project  
✅ Consistent organization  

### 2. **PARA Method Support**
✅ Projects grouped by life areas  
✅ Tasks categorized automatically  
✅ Easy filtering and views  

### 3. **Notion Power Features**
✅ Filter tasks by area  
✅ Create area-specific dashboards  
✅ Track workload per area  
✅ Rollups and formulas per area  

### 4. **Existing Workflow Preserved**
✅ Uses labels you already have  
✅ No changes needed to Todoist  
✅ Optional feature (can disable)  

---

## 🧪 Testing

### Test 1: Project with Area Label

1. In Todoist, find a project with one of your area labels (e.g., PROSPER 📁)
2. Create a task in that project with `capsync` label
3. Wait for sync (up to 5 minutes)
4. Check Notion:
   - Task page should have AREAS relation to PROSPER
   - PROSPER area should show the task in its relations

### Test 2: Task with Direct Area Label

1. Create a task in Inbox
2. Add labels: `capsync`, `HEALTH 📁`
3. Wait for sync
4. Check Notion - should link to HEALTH area

### Test 3: Area Auto-Creation

1. Create new area label in Todoist: `TEST-AREA`
2. Add to `para_area_labels` in settings
3. Create task with `capsync` and `TEST-AREA` labels
4. Wait for sync
5. Check Notion - new "TEST-AREA" page created in AREAS database!

---

## 🔍 Monitoring

### Check Area Assignments in Logs

```bash
gcloud logging read \
  "jsonPayload.message:'assigned to AREA'" \
  --project=notion-todoist-sync-464419 \
  --limit=20 \
  --format="table(timestamp.date('%H:%M:%S'),jsonPayload.task_id,jsonPayload.area)"
```

### View Created Areas

```bash
# Query AREAS database
# (Will be available after first sync with area labels)
```

---

## ⚙️ Configuration Options

### Customize AREA Labels

Edit `app/settings.py`:

```python
para_area_labels: list[str] = [
    "HOME", "HEALTH", "PROSPER", "WORK", 
    "PERSONAL & FAMILY", "FINANCIAL", "FUN",
    # Add your custom areas:
    "LEARNING", "HOBBIES", "TRAVEL"
]
```

### Disable PARA Feature

Set in environment:
```bash
ENABLE_PARA_AREAS=false
```

---

## 💡 Pro Tips

### 1. **Use Project-Level Labels**
Add area label to the Todoist PROJECT → all tasks automatically inherit it!

### 2. **Notion Views by Area**
Create filtered views in your Tasks database:
- WORK tasks only
- HOME tasks only
- FUN tasks only

### 3. **Area Dashboards**
In your AREAS database, add rollup properties:
- Count of active tasks per area
- Count of completed tasks
- Next upcoming task per area

### 4. **Combine with Other Features**
- Area + Priority → "High priority work tasks"
- Area + Due Date → "Home tasks due this week"
- Area + Person → "Work tasks assigned to James"

---

## 🚀 Next Steps

After deployment, the service will:

1. ✅ Detect area labels in tasks and projects
2. ✅ Find or create corresponding AREA pages
3. ✅ Link tasks and projects to areas
4. ✅ Maintain relationships automatically

**All your existing tasks will get area assignments on the next sync!**

---

## 📝 Technical Details

**Files Modified:**
- `app/settings.py` - Added AREAS database config and PARA labels
- `app/utils.py` - Added `extract_para_area()` function
- `app/notion_client.py` - Added AREAS database methods
- `app/pubsub_worker.py` - Added AREA detection and linking logic

**Database Queries Added:**
- Find area by name (cached via Firestore)
- Create area if missing
- Set relation properties

**API Calls per Sync:**
- +1 query to check if area exists (first time only)
- +1 create if area is new
- Subsequent syncs: 0 additional calls (uses existing area page)

---

**This perfectly integrates the PARA method into your Todoist-Notion workflow!** 🎉

