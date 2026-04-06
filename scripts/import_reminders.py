#!/usr/bin/env python3
"""Import tasks from Apple Reminders default list into Todoist.

Reads uncompleted reminders from the macOS default Reminders list,
creates corresponding Todoist tasks (leveraging Todoist's natural
language parsing for dates, projects, and labels), marks the
reminders as complete, and logs the import.

Requirements:
    - macOS (uses EventKit via pyobjc)
    - pip install pyobjc-framework-EventKit httpx
    - TODOIST_OAUTH_TOKEN set in environment or .env file

Usage:
    python scripts/import_reminders.py              # Import all pending reminders
    python scripts/import_reminders.py --dry-run     # Preview without importing
    python scripts/import_reminders.py --verbose      # Show detailed logging

Schedule with launchd or cron:
    */15 * * * * cd /path/to/repo && python scripts/import_reminders.py >> ~/logs/reminders-import.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Load .env if present (before any settings access)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

logger = logging.getLogger("import_reminders")

# ---------------------------------------------------------------------------
# State file for dedup — tracks which reminders have already been imported
# ---------------------------------------------------------------------------
STATE_FILE = Path.home() / ".todoist_reminders_state.json"


def load_state() -> dict[str, str]:
    """Load import state (reminder_id -> todoist_task_id)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict[str, str]) -> None:
    """Persist import state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Apple Reminders access via EventKit
# ---------------------------------------------------------------------------


def get_default_reminders() -> list[dict[str, str | None]]:
    """Fetch uncompleted reminders from the default Reminders list.

    Returns a list of dicts with keys: id, title, notes, due_date.
    """
    try:
        import EventKit  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "pyobjc-framework-EventKit not installed. "
            "Run: pip install pyobjc-framework-EventKit"
        )
        sys.exit(1)

    store = EventKit.EKEventStore.alloc().init()

    # Request access — on first run macOS will show a permission dialog
    granted = [False]
    error_ref = [None]

    def handler(g: bool, e: object) -> None:
        granted[0] = g
        error_ref[0] = e

    store.requestAccessToEntityType_completion_(
        EventKit.EKEntityTypeReminder, handler
    )

    # EventKit callback is async; give it a moment
    deadline = time.time() + 5
    while not granted[0] and error_ref[0] is None and time.time() < deadline:
        time.sleep(0.1)

    if not granted[0]:
        logger.error(
            "Reminders access not granted. Check System Settings > Privacy > Reminders. "
            "Error: %s",
            error_ref[0],
        )
        sys.exit(1)

    # Get the default reminder list
    default_calendar = store.defaultCalendarForNewReminders()
    if default_calendar is None:
        logger.error("No default Reminders list found.")
        sys.exit(1)

    logger.info("Reading from Reminders list: %s", default_calendar.title())

    # Fetch incomplete reminders
    predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, [default_calendar]
    )

    # fetchRemindersMatchingPredicate is async — use a semaphore
    results = [None]
    done = [False]

    def fetch_handler(reminders: list[object] | None) -> None:
        results[0] = reminders
        done[0] = True

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_handler)

    deadline = time.time() + 10
    while not done[0] and time.time() < deadline:
        time.sleep(0.1)

    if results[0] is None:
        logger.info("No incomplete reminders found.")
        return []

    reminders = []
    for r in results[0]:
        due_date = None
        if r.dueDateComponents() is not None:
            d = r.dueDateComponents()
            due_date = f"{d.year():04d}-{d.month():02d}-{d.day():02d}"

        reminders.append(
            {
                "id": r.calendarItemExternalIdentifier(),
                "title": r.title(),
                "notes": r.notes() if r.notes() else None,
                "due_date": due_date,
            }
        )

    return reminders


def complete_reminder(reminder_id: str) -> bool:
    """Mark a reminder as completed by its external identifier."""
    import EventKit  # type: ignore[import-untyped]

    store = EventKit.EKEventStore.alloc().init()

    # Re-request access (cheap if already granted)
    granted = [False]

    def handler(g: bool, _e: object) -> None:
        granted[0] = g

    store.requestAccessToEntityType_completion_(
        EventKit.EKEntityTypeReminder, handler
    )
    deadline = time.time() + 5
    while not granted[0] and time.time() < deadline:
        time.sleep(0.1)

    default_calendar = store.defaultCalendarForNewReminders()
    if default_calendar is None:
        return False

    # Fetch incomplete to find the one we want
    predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, [default_calendar]
    )
    results = [None]
    done = [False]

    def fetch_handler(reminders: list[object] | None) -> None:
        results[0] = reminders
        done[0] = True

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_handler)

    deadline = time.time() + 10
    while not done[0] and time.time() < deadline:
        time.sleep(0.1)

    if results[0] is None:
        return False

    for r in results[0]:
        if r.calendarItemExternalIdentifier() == reminder_id:
            r.setCompleted_(True)
            success, error = store.saveReminder_commit_error_(r, True, None)
            if not success:
                logger.error("Failed to complete reminder: %s", error)
                return False
            return True

    logger.warning("Reminder %s not found for completion", reminder_id)
    return False


# ---------------------------------------------------------------------------
# Todoist task creation
# ---------------------------------------------------------------------------


def create_todoist_task(
    title: str,
    todoist_token: str,
    notes: str | None = None,
    due_date: str | None = None,
) -> str | None:
    """Create a Todoist task using the REST API v2 (sync-friendly).

    The task content is the reminder title as-is, letting Todoist's
    natural language parser extract dates, projects, and labels.

    Returns the new task ID on success, None on failure.
    """
    import httpx

    # Use the Sync-friendly REST v2 endpoint which supports NLP
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {
        "Authorization": f"Bearer {todoist_token}",
        "Content-Type": "application/json",
    }

    payload: dict[str, str] = {"content": title}

    # If the reminder had a due date and the title doesn't seem to contain
    # a date expression, pass it explicitly
    if due_date and not _title_has_date_hint(title):
        payload["due_date"] = due_date

    if notes:
        payload["description"] = notes

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            task = resp.json()
            return task["id"]
    except httpx.HTTPStatusError as e:
        logger.error("Todoist API error: %s %s", e.response.status_code, e.response.text)
        return None
    except httpx.RequestError as e:
        logger.error("Todoist request failed: %s", e)
        return None


def _title_has_date_hint(title: str) -> bool:
    """Rough check if the title contains date-like words Todoist can parse."""
    date_words = [
        "today",
        "tomorrow",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "next week",
        "next month",
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]
    lower = title.lower()
    return any(w in lower for w in date_words)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Apple Reminders into Todoist"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview reminders without importing",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    todoist_token = os.environ.get("TODOIST_OAUTH_TOKEN", "")
    if not todoist_token and not args.dry_run:
        logger.error("TODOIST_OAUTH_TOKEN not set. Add it to .env or export it.")
        sys.exit(1)

    # Load previously imported reminder IDs
    state = load_state()

    # Fetch reminders
    reminders = get_default_reminders()
    if not reminders:
        logger.info("No reminders to import.")
        return

    new_reminders = [r for r in reminders if r["id"] not in state]
    if not new_reminders:
        logger.info(
            "All %d reminders already imported. Nothing to do.", len(reminders)
        )
        return

    logger.info(
        "Found %d new reminder(s) to import (of %d total).",
        len(new_reminders),
        len(reminders),
    )

    imported = 0
    for r in new_reminders:
        title = r["title"]
        if not title:
            logger.warning("Skipping reminder with empty title (id=%s)", r["id"])
            continue

        if args.dry_run:
            logger.info("[DRY RUN] Would import: %s (due: %s)", title, r["due_date"])
            continue

        logger.info("Importing: %s", title)
        task_id = create_todoist_task(
            title=title,
            todoist_token=todoist_token,
            notes=r["notes"],
            due_date=r["due_date"],
        )

        if task_id:
            # Mark as complete in Apple Reminders
            if complete_reminder(r["id"]):
                logger.info("  -> Todoist task %s created, reminder completed.", task_id)
            else:
                logger.warning(
                    "  -> Todoist task %s created, but failed to complete reminder.",
                    task_id,
                )

            state[r["id"]] = task_id
            save_state(state)
            imported += 1
        else:
            logger.error("  -> Failed to create Todoist task for: %s", title)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info("Done. Imported %d reminder(s) at %s.", imported, now)


if __name__ == "__main__":
    main()
