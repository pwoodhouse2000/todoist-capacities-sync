#!/usr/bin/env python3
"""
Cleanup script to consolidate duplicate PARA area entries in Notion AREAS database.

This script:
1. Fetches all pages from the AREAS database
2. Groups them by Name (the 7 PARA areas)
3. For each area with duplicates:
   - Keeps the oldest entry as canonical
   - Migrates all relations (Todoist Projects, Todoist Tasks) to canonical
   - Deletes duplicate entries
4. Provides dry-run mode to preview changes before applying

Usage:
    # Dry run (preview only):
    python scripts/cleanup_duplicate_areas.py --dry-run
    
    # Actually perform cleanup:
    python scripts/cleanup_duplicate_areas.py
    
    # Cleanup specific area only:
    python scripts/cleanup_duplicate_areas.py --area "HOME" --dry-run
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from collections import defaultdict

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import AsyncClient
from app.settings import settings
from app.logging_setup import get_logger

logger = get_logger(__name__)


class AreaDuplicateCleaner:
    """Clean up duplicate PARA area entries in Notion."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.client = AsyncClient(auth=settings.notion_api_key)
        self.areas_db_id = settings.notion_areas_database_id
        self.tasks_db_id = settings.notion_tasks_database_id
        self.projects_db_id = settings.notion_projects_database_id
        
        if not self.areas_db_id:
            raise ValueError("NOTION_AREAS_DATABASE_ID not configured in environment")
    
    async def fetch_all_areas(self) -> List[Dict]:
        """Fetch all pages from AREAS database with pagination."""
        all_pages = []
        has_more = True
        start_cursor = None
        
        print(f"📖 Fetching all pages from AREAS database...")
        
        while has_more:
            query_params = {
                "database_id": self.areas_db_id,
                "page_size": 100,
            }
            if start_cursor:
                query_params["start_cursor"] = start_cursor
            
            try:
                # Direct API call using requests-like interface
                response = await self.client.databases.query(**query_params)
                results = response.get("results", [])
                all_pages.extend(results)
                
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                
                print(f"  Fetched {len(results)} pages (total: {len(all_pages)})")
            except AttributeError as e:
                # If databases.query doesn't work, fall back to direct HTTP
                print(f"⚠️  databases.query() not available, trying direct HTTP...")
                response = await self._query_database_direct(query_params)
                results = response.get("results", [])
                all_pages.extend(results)
                
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                
                print(f"  Fetched {len(results)} pages via direct HTTP (total: {len(all_pages)})")
        
        print(f"✅ Total pages fetched: {len(all_pages)}\n")
        return all_pages
    
    async def _query_database_direct(self, query_params: Dict) -> Dict:
        """Fallback: Query database using direct HTTP request."""
        import httpx
        
        url = f"https://api.notion.com/v1/databases/{query_params['database_id']}/query"
        headers = {
            "Authorization": f"Bearer {settings.notion_api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        
        body = {}
        if "start_cursor" in query_params:
            body["start_cursor"] = query_params["start_cursor"]
        if "page_size" in query_params:
            body["page_size"] = query_params["page_size"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body, timeout=30.0)
            response.raise_for_status()
            return response.json()
    
    def extract_area_name(self, page: Dict) -> Optional[str]:
        """Extract area name from page properties."""
        try:
            title_prop = page.get("properties", {}).get("Name", {})
            if "title" in title_prop and title_prop["title"]:
                return title_prop["title"][0]["text"]["content"]
        except (KeyError, IndexError, TypeError):
            pass
        return None
    
    def group_by_area(self, pages: List[Dict]) -> Dict[str, List[Dict]]:
        """Group pages by area name."""
        grouped = defaultdict(list)
        
        for page in pages:
            area_name = self.extract_area_name(page)
            if area_name:
                grouped[area_name].append(page)
        
        return dict(grouped)
    
    async def get_related_items(self, page_id: str, database_id: str, relation_property: str) -> List[str]:
        """Get all items in a database that relate to this page."""
        related_ids = []
        has_more = True
        start_cursor = None
        
        while has_more:
            query_params = {
                "database_id": database_id,
                "filter": {
                    "property": relation_property,
                    "relation": {"contains": page_id}
                },
                "page_size": 100,
            }
            if start_cursor:
                query_params["start_cursor"] = start_cursor
            
            try:
                response = await self.client.databases.query(**query_params)
            except AttributeError:
                response = await self._query_database_direct(query_params)
            
            for item in response.get("results", []):
                related_ids.append(item["id"])
            
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")
        
        return related_ids
    
    async def update_relation(self, item_id: str, property_name: str, new_relation_ids: List[str]):
        """Update a relation property on a page."""
        if self.dry_run:
            return
        
        properties = {
            property_name: {
                "relation": [{"id": rel_id} for rel_id in new_relation_ids]
            }
        }
        
        await self.client.pages.update(page_id=item_id, properties=properties)
    
    async def delete_page(self, page_id: str):
        """Archive (delete) a page."""
        if self.dry_run:
            return
        
        await self.client.pages.update(page_id=page_id, archived=True)
    
    async def consolidate_area(self, area_name: str, pages: List[Dict]):
        """Consolidate duplicate area pages into one canonical page."""
        if len(pages) <= 1:
            print(f"✅ {area_name}: No duplicates (1 entry)")
            return
        
        print(f"\n🔍 {area_name}: Found {len(pages)} entries (consolidating...)")
        
        # Sort by created_time to keep the oldest as canonical
        sorted_pages = sorted(pages, key=lambda p: p.get("created_time", ""))
        canonical = sorted_pages[0]
        duplicates = sorted_pages[1:]
        
        canonical_id = canonical["id"]
        print(f"  📌 Canonical: {canonical_id[:8]}... (created: {canonical.get('created_time', 'unknown')})")
        
        # For each duplicate, migrate relations and delete
        for dup in duplicates:
            dup_id = dup["id"]
            print(f"  🗑️  Duplicate: {dup_id[:8]}... (created: {dup.get('created_time', 'unknown')})")
            
            # Find all tasks relating to this duplicate
            related_tasks = await self.get_related_items(dup_id, self.tasks_db_id, "AREAS")
            if related_tasks:
                print(f"     → Migrating {len(related_tasks)} tasks to canonical")
                for task_id in related_tasks:
                    # Update task to point to canonical instead
                    await self.update_relation(task_id, "AREAS", [canonical_id])
            
            # Find all projects relating to this duplicate
            related_projects = await self.get_related_items(dup_id, self.projects_db_id, "AREAS")
            if related_projects:
                print(f"     → Migrating {len(related_projects)} projects to canonical")
                for project_id in related_projects:
                    # Update project to point to canonical instead
                    await self.update_relation(project_id, "AREAS", [canonical_id])
            
            # Delete the duplicate
            if self.dry_run:
                print(f"     → [DRY RUN] Would delete duplicate {dup_id[:8]}...")
            else:
                await self.delete_page(dup_id)
                print(f"     → ✅ Deleted duplicate {dup_id[:8]}...")
        
        print(f"  ✅ {area_name}: Consolidated {len(duplicates)} duplicates into canonical")
    
    async def cleanup(self, specific_area: Optional[str] = None):
        """Run the cleanup process."""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        print(f"\n{'='*70}")
        print(f"  AREAS Database Duplicate Cleanup - {mode} MODE")
        print(f"{'='*70}\n")
        
        if self.dry_run:
            print("⚠️  DRY RUN MODE: No changes will be made to Notion")
            print("    Remove --dry-run flag to perform actual cleanup\n")
        
        # Fetch all area pages
        all_pages = await self.fetch_all_areas()
        
        # Group by area name
        grouped = self.group_by_area(all_pages)
        
        # Summary
        print(f"📊 Summary:")
        total_duplicates = 0
        for area_name, pages in sorted(grouped.items()):
            dups = len(pages) - 1 if len(pages) > 1 else 0
            total_duplicates += dups
            status = "✅" if dups == 0 else f"⚠️  {dups} duplicates"
            print(f"  {area_name}: {len(pages)} entries ({status})")
        
        print(f"\n📈 Total duplicate entries to clean up: {total_duplicates}\n")
        
        if total_duplicates == 0:
            print("✅ No duplicates found! Database is clean.")
            return
        
        # Consolidate each area
        print(f"\n{'='*70}")
        print(f"  Starting Consolidation")
        print(f"{'='*70}")
        
        for area_name in sorted(grouped.keys()):
            if specific_area and area_name != specific_area:
                continue
            
            pages = grouped[area_name]
            await self.consolidate_area(area_name, pages)
        
        print(f"\n{'='*70}")
        if self.dry_run:
            print(f"  ✅ DRY RUN COMPLETE - No changes made")
            print(f"     Run without --dry-run to perform actual cleanup")
        else:
            print(f"  ✅ CLEANUP COMPLETE")
        print(f"{'='*70}\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Cleanup duplicate PARA area entries in Notion AREAS database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them (recommended first run)"
    )
    parser.add_argument(
        "--area",
        type=str,
        help="Only cleanup a specific area (e.g., 'HOME', 'PROSPER')"
    )
    
    args = parser.parse_args()
    
    cleaner = AreaDuplicateCleaner(dry_run=args.dry_run)
    await cleaner.cleanup(specific_area=args.area)


if __name__ == "__main__":
    asyncio.run(main())

