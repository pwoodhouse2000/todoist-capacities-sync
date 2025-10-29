#!/usr/bin/env python3
"""
Test script to diagnose the Notion API client issue.

This script tests various ways to call the Notion API to understand
why databases.query() is failing with AttributeError.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import AsyncClient, Client
from app.settings import settings


async def test_async_client():
    """Test AsyncClient to see what methods are available."""
    print("\n" + "="*70)
    print("Testing AsyncClient")
    print("="*70)
    
    client = AsyncClient(auth=settings.notion_api_key)
    
    print(f"\n1. AsyncClient type: {type(client)}")
    print(f"2. AsyncClient attributes: {dir(client)}")
    
    # Check if databases attribute exists
    if hasattr(client, 'databases'):
        print(f"\n3. ✅ client.databases exists")
        print(f"   Type: {type(client.databases)}")
        print(f"   Attributes: {dir(client.databases)}")
        
        # Check if query method exists
        if hasattr(client.databases, 'query'):
            print(f"\n4. ✅ client.databases.query exists")
            print(f"   Type: {type(client.databases.query)}")
        else:
            print(f"\n4. ❌ client.databases.query DOES NOT EXIST")
            print(f"   Available methods on databases:")
            for attr in dir(client.databases):
                if not attr.startswith('_'):
                    print(f"      - {attr}")
    else:
        print(f"\n3. ❌ client.databases DOES NOT EXIST")
    
    # Try to actually query a database
    print(f"\n5. Testing actual database query...")
    try:
        result = await client.databases.query(
            database_id=settings.notion_tasks_database_id,
            page_size=1
        )
        print(f"   ✅ Query succeeded!")
        print(f"   Result type: {type(result)}")
        print(f"   Has results: {len(result.get('results', []))} items")
    except AttributeError as e:
        print(f"   ❌ AttributeError: {e}")
    except Exception as e:
        print(f"   ❌ Other error: {type(e).__name__}: {e}")


def test_sync_client():
    """Test sync Client to compare."""
    print("\n" + "="*70)
    print("Testing Sync Client (for comparison)")
    print("="*70)
    
    client = Client(auth=settings.notion_api_key)
    
    print(f"\n1. Client type: {type(client)}")
    
    # Check if databases attribute exists
    if hasattr(client, 'databases'):
        print(f"\n2. ✅ client.databases exists")
        print(f"   Type: {type(client.databases)}")
        
        # Check if query method exists
        if hasattr(client.databases, 'query'):
            print(f"\n3. ✅ client.databases.query exists")
            print(f"   Type: {type(client.databases.query)}")
            
            # Try to actually query
            print(f"\n4. Testing actual database query...")
            try:
                result = client.databases.query(
                    database_id=settings.notion_tasks_database_id,
                    page_size=1
                )
                print(f"   ✅ Query succeeded!")
                print(f"   Has results: {len(result.get('results', []))} items")
            except Exception as e:
                print(f"   ❌ Error: {type(e).__name__}: {e}")
        else:
            print(f"\n3. ❌ client.databases.query DOES NOT EXIST")
    else:
        print(f"\n2. ❌ client.databases DOES NOT EXIST")


async def test_direct_http():
    """Test direct HTTP request as fallback."""
    print("\n" + "="*70)
    print("Testing Direct HTTP API Call")
    print("="*70)
    
    import httpx
    
    url = f"https://api.notion.com/v1/databases/{settings.notion_tasks_database_id}/query"
    headers = {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    body = {"page_size": 1}
    
    print(f"\n1. URL: {url}")
    print(f"2. Making POST request...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body, timeout=30.0)
            print(f"   ✅ Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Query succeeded!")
                print(f"   Has results: {len(data.get('results', []))} items")
            else:
                print(f"   ❌ Error response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")


async def main():
    print("\n" + "="*70)
    print("NOTION API CLIENT DIAGNOSTIC TOOL")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Tasks DB: {settings.notion_tasks_database_id}")
    print(f"  Projects DB: {settings.notion_projects_database_id}")
    print(f"  Areas DB: {settings.notion_areas_database_id}")
    print(f"  API Key: {'*' * 20}{settings.notion_api_key[-10:]}")
    
    # Test async client
    await test_async_client()
    
    # Test sync client
    test_sync_client()
    
    # Test direct HTTP
    await test_direct_http()
    
    print("\n" + "="*70)
    print("DIAGNOSTIC COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())



