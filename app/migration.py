"""One-time migration: Update Notion pages and Firestore with v1 Todoist IDs."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.logging_setup import get_logger
from app.mapper import map_project_to_notion, map_task_to_todo
from app.models import ProjectSyncState, SyncStatus, TaskSyncState
from app.notion_client import NotionClient
from app.store import FirestoreStore
from app.todoist_client import TodoistClient
from app.utils import build_todoist_project_url, build_todoist_task_url, compute_payload_hash

logger = get_logger(__name__)


def _get_text_prop(page: Dict[str, Any], prop_name: str) -> str:
    """Extract text from a Notion page property."""
    props = page.get("properties", {})
    prop = props.get(prop_name, {})
    if "rich_text" in prop and prop["rich_text"]:
        return prop["rich_text"][0].get("text", {}).get("content", "")
    if "title" in prop and prop["title"]:
        return prop["title"][0].get("text", {}).get("content", "")
    return ""


def _is_v1_id(task_id: str) -> bool:
    """Check if a Todoist ID is v1 format (alphanumeric, not purely numeric)."""
    return bool(task_id) and not task_id.isdigit()


async def run_v1_id_migration(
    todoist: TodoistClient,
    notion: NotionClient,
    store: FirestoreStore,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Migrate Notion pages and Firestore state from v2 to v1 Todoist IDs.

    The Todoist API v2->v1 migration changed all task/project IDs from numeric
    to alphanumeric. This function:
    1. Fetches all v1 tasks with capsync label
    2. Queries all existing Notion task pages
    3. Matches by title (exact match) since IDs changed
    4. Updates Notion pages with new v1 Todoist Task IDs
    5. Archives duplicate pages (created during first v1 reconciliation)
    6. Rebuilds Firestore state with new IDs

    Args:
        todoist: Todoist API client
        notion: Notion API client
        store: Firestore store
        dry_run: If True, only report what would change

    Returns:
        Migration summary dict
    """
    # Step 1: Fetch all v1 tasks with capsync label
    logger.info("Migration: Fetching all v1 tasks with capsync label")
    v1_tasks = await todoist.get_active_tasks_with_label("capsync")
    logger.info(f"Migration: Found {len(v1_tasks)} v1 tasks")

    # Build lookup: title -> list of v1 tasks
    v1_by_title: Dict[str, list] = {}
    for task in v1_tasks:
        title = task.content.strip()
        if title not in v1_by_title:
            v1_by_title[title] = []
        v1_by_title[title].append(task)

    # Step 2: Fetch all v1 projects
    logger.info("Migration: Fetching all v1 projects")
    v1_projects = await todoist.get_projects()
    v1_projects_by_name: Dict[str, Any] = {}
    for proj in v1_projects:
        v1_projects_by_name[proj.name.strip()] = proj

    # Step 3: Fetch all existing Notion task pages
    logger.info("Migration: Fetching all Notion task pages")
    notion_pages = await notion.get_all_task_pages()
    logger.info(f"Migration: Found {len(notion_pages)} Notion task pages")

    # Step 4: Fetch all existing Notion project pages
    logger.info("Migration: Fetching all Notion project pages")
    notion_project_pages = await notion.get_all_project_pages()
    logger.info(f"Migration: Found {len(notion_project_pages)} Notion project pages")

    # Categorize task pages
    old_id_pages: List[Dict[str, Any]] = []
    new_id_pages: List[Dict[str, Any]] = []
    no_id_pages: List[Dict[str, Any]] = []

    for page in notion_pages:
        todoist_id = _get_text_prop(page, "Todoist Task ID")
        title = _get_text_prop(page, "Name")

        if not todoist_id:
            no_id_pages.append({"page": page, "title": title})
        elif _is_v1_id(todoist_id):
            new_id_pages.append({"page": page, "title": title, "todoist_id": todoist_id})
        else:
            old_id_pages.append({"page": page, "title": title, "todoist_id": todoist_id})

    logger.info(
        "Migration: Page categorization",
        extra={
            "old_id_pages": len(old_id_pages),
            "new_id_pages": len(new_id_pages),
            "no_id_pages": len(no_id_pages),
        },
    )

    # Match old-ID pages to v1 tasks by title
    matched_tasks, unmatched_old_pages, duplicate_new_pages_to_archive = _match_tasks(
        old_id_pages, new_id_pages, v1_by_title
    )

    # Identify genuinely new pages (v1 tasks that had no old-ID page)
    matched_new_ids = {m["new_id"] for m in matched_tasks}
    dup_page_ids = {d["page_id"] for d in duplicate_new_pages_to_archive}
    genuinely_new_pages = [
        entry
        for entry in new_id_pages
        if entry["todoist_id"] not in matched_new_ids
        and entry["page"]["id"] not in dup_page_ids
    ]

    # Match project pages
    matched_projects = _match_projects(notion_project_pages, v1_projects_by_name)

    summary: Dict[str, Any] = {
        "status": "dry_run" if dry_run else "executed",
        "v1_tasks_count": len(v1_tasks),
        "notion_task_pages": len(notion_pages),
        "notion_project_pages": len(notion_project_pages),
        "categorization": {
            "old_id_pages": len(old_id_pages),
            "new_id_pages": len(new_id_pages),
            "no_id_pages": len(no_id_pages),
        },
        "tasks": {
            "matched": len(matched_tasks),
            "ambiguous": len([m for m in matched_tasks if m.get("ambiguous")]),
            "unmatched_old": len(unmatched_old_pages),
            "duplicates_to_archive": len(duplicate_new_pages_to_archive),
            "genuinely_new": len(genuinely_new_pages),
        },
        "projects": {"matched": len(matched_projects)},
    }

    if dry_run:
        summary["matched_tasks_sample"] = matched_tasks[:15]
        summary["unmatched_old_sample"] = unmatched_old_pages[:15]
        summary["duplicates_sample"] = duplicate_new_pages_to_archive[:15]
        summary["genuinely_new_sample"] = [
            {"title": e["title"], "todoist_id": e["todoist_id"]}
            for e in genuinely_new_pages[:15]
        ]
        summary["matched_projects_sample"] = matched_projects[:15]
        summary["note"] = "POST with ?dry_run=false to execute migration"
        return summary

    # === EXECUTE MIGRATION ===
    logger.info("Migration: EXECUTING (not dry run)")

    execution = await _execute_migration(
        notion=notion,
        store=store,
        v1_tasks=v1_tasks,
        v1_projects=v1_projects,
        matched_tasks=matched_tasks,
        matched_projects=matched_projects,
        duplicate_new_pages_to_archive=duplicate_new_pages_to_archive,
        genuinely_new_pages=genuinely_new_pages,
    )

    summary["execution"] = execution
    logger.info("Migration: COMPLETED", extra=execution)
    return summary


def _match_tasks(
    old_id_pages: List[Dict[str, Any]],
    new_id_pages: List[Dict[str, Any]],
    v1_by_title: Dict[str, list],
) -> tuple:
    """Match old-ID Notion pages to v1 tasks by title and find duplicates."""
    matched_tasks: List[Dict[str, Any]] = []
    unmatched_old_pages: List[Dict[str, Any]] = []
    duplicate_new_pages_to_archive: List[Dict[str, Any]] = []

    # Index new-ID pages by title for duplicate detection
    new_id_titles: Dict[str, list] = {}
    for entry in new_id_pages:
        title = entry["title"].strip()
        if title not in new_id_titles:
            new_id_titles[title] = []
        new_id_titles[title].append(entry)

    for entry in old_id_pages:
        title = entry["title"].strip()
        page = entry["page"]
        old_id = entry["todoist_id"]

        candidates = v1_by_title.get(title, [])

        if len(candidates) >= 1:
            v1_task = candidates[0]
            match_entry: Dict[str, Any] = {
                "notion_page_id": page["id"],
                "title": title,
                "old_id": old_id,
                "new_id": v1_task.id,
                "project_id": v1_task.project_id,
            }
            if len(candidates) > 1:
                match_entry["ambiguous"] = True
                match_entry["candidate_count"] = len(candidates)

            matched_tasks.append(match_entry)

            # Flag duplicate new-ID pages for archival
            if title in new_id_titles:
                for dup_entry in new_id_titles[title]:
                    if dup_entry["todoist_id"] == v1_task.id:
                        duplicate_new_pages_to_archive.append(
                            {
                                "page_id": dup_entry["page"]["id"],
                                "title": title,
                                "todoist_id": dup_entry["todoist_id"],
                            }
                        )
        else:
            unmatched_old_pages.append(
                {
                    "notion_page_id": page["id"],
                    "title": title,
                    "old_id": old_id,
                }
            )

    return matched_tasks, unmatched_old_pages, duplicate_new_pages_to_archive


def _match_projects(
    notion_project_pages: List[Dict[str, Any]],
    v1_projects_by_name: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Match Notion project pages with old numeric IDs to v1 projects by name."""
    matched_projects: List[Dict[str, Any]] = []
    for proj_page in notion_project_pages:
        proj_todoist_id = _get_text_prop(proj_page, "Todoist Project ID")
        proj_name = _get_text_prop(proj_page, "Name")

        if proj_todoist_id and not _is_v1_id(proj_todoist_id):
            v1_proj = v1_projects_by_name.get(proj_name.strip())
            if v1_proj:
                matched_projects.append(
                    {
                        "notion_page_id": proj_page["id"],
                        "name": proj_name,
                        "old_id": proj_todoist_id,
                        "new_id": v1_proj.id,
                    }
                )
    return matched_projects


async def _execute_migration(
    notion: NotionClient,
    store: FirestoreStore,
    v1_tasks: list,
    v1_projects: list,
    matched_tasks: List[Dict[str, Any]],
    matched_projects: List[Dict[str, Any]],
    duplicate_new_pages_to_archive: List[Dict[str, Any]],
    genuinely_new_pages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute the actual migration: update Notion pages, archive dups, rebuild Firestore."""
    # Update old-ID task pages with new v1 IDs
    tasks_updated = 0
    tasks_failed = 0
    for match in matched_tasks:
        try:
            await notion.update_todoist_task_id(match["notion_page_id"], match["new_id"])
            await notion.client.pages.update(
                page_id=match["notion_page_id"],
                properties={"Todoist URL": {"url": build_todoist_task_url(match["new_id"])}},
            )
            tasks_updated += 1
        except Exception as e:
            logger.warning(f"Migration: Failed to update task {match['notion_page_id']}: {e}")
            tasks_failed += 1

    # Archive duplicate pages
    dups_archived = 0
    for dup in duplicate_new_pages_to_archive:
        try:
            await notion.archive_page(dup["page_id"])
            dups_archived += 1
        except Exception as e:
            logger.warning(f"Migration: Failed to archive duplicate {dup['page_id']}: {e}")

    # Update project pages
    projects_updated = 0
    for proj_match in matched_projects:
        try:
            await notion.update_todoist_project_id(
                proj_match["notion_page_id"], proj_match["new_id"]
            )
            await notion.client.pages.update(
                page_id=proj_match["notion_page_id"],
                properties={
                    "Todoist URL": {"url": build_todoist_project_url(proj_match["new_id"])}
                },
            )
            projects_updated += 1
        except Exception as e:
            logger.warning(
                f"Migration: Failed to update project {proj_match['notion_page_id']}: {e}"
            )

    # Rebuild Firestore state
    logger.info("Migration: Clearing old Firestore task states")
    cleared = await store.clear_all_task_states()

    v1_tasks_map = {t.id: t for t in v1_tasks}
    v1_projects_map = {p.id: p for p in v1_projects}

    # Save states for matched (migrated) tasks
    states_saved = 0
    for match in matched_tasks:
        try:
            v1_task = v1_tasks_map.get(match["new_id"])
            if v1_task:
                project = v1_projects_map.get(v1_task.project_id)
                if project:
                    todo = map_task_to_todo(v1_task, project, [], None)
                    state = TaskSyncState(
                        todoist_task_id=match["new_id"],
                        capacities_object_id=match["notion_page_id"],
                        payload_hash=compute_payload_hash(todo.model_dump()),
                        last_synced_at=datetime.now(timezone.utc),
                        sync_status=SyncStatus.OK,
                        sync_source="migration",
                    )
                    await store.save_task_state(state)
                    states_saved += 1
        except Exception as e:
            logger.warning(f"Migration: Failed to save state for {match['new_id']}: {e}")

    # Save states for genuinely new pages
    new_states_saved = 0
    for entry in genuinely_new_pages:
        try:
            v1_task = v1_tasks_map.get(entry["todoist_id"])
            if v1_task:
                project = v1_projects_map.get(v1_task.project_id)
                if project:
                    todo = map_task_to_todo(v1_task, project, [], None)
                    state = TaskSyncState(
                        todoist_task_id=entry["todoist_id"],
                        capacities_object_id=entry["page"]["id"],
                        payload_hash=compute_payload_hash(todo.model_dump()),
                        last_synced_at=datetime.now(timezone.utc),
                        sync_status=SyncStatus.OK,
                        sync_source="migration",
                    )
                    await store.save_task_state(state)
                    new_states_saved += 1
        except Exception as e:
            logger.warning(
                f"Migration: Failed to save new state for {entry['todoist_id']}: {e}"
            )

    # Save project states
    proj_states_saved = 0
    for proj_match in matched_projects:
        try:
            v1_proj = v1_projects_map.get(proj_match["new_id"])
            if v1_proj:
                notion_proj = map_project_to_notion(v1_proj)
                proj_state = ProjectSyncState(
                    todoist_project_id=proj_match["new_id"],
                    capacities_object_id=proj_match["notion_page_id"],
                    payload_hash=compute_payload_hash(notion_proj.model_dump()),
                    last_synced_at=datetime.now(timezone.utc),
                )
                await store.save_project_state(proj_state)
                proj_states_saved += 1
        except Exception as e:
            logger.warning(
                f"Migration: Failed to save project state for {proj_match['new_id']}: {e}"
            )

    return {
        "tasks_updated": tasks_updated,
        "tasks_failed": tasks_failed,
        "duplicates_archived": dups_archived,
        "projects_updated": projects_updated,
        "firestore_cleared": cleared,
        "task_states_saved": states_saved,
        "new_task_states_saved": new_states_saved,
        "project_states_saved": proj_states_saved,
    }
