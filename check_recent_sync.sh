#!/bin/bash

echo "🔍 Checking recent Notion tasks..."
echo ""

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep NOTION_API_KEY | xargs)
    export $(cat .env | grep NOTION_TASKS_DATABASE_ID | xargs)
fi

curl -s "https://api.notion.com/v1/databases/${NOTION_TASKS_DATABASE_ID}/query" \
  -H "Authorization: Bearer ${NOTION_API_KEY}" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"sorts": [{"timestamp": "created_time", "direction": "descending"}], "page_size": 5}' | \
  python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
results = data.get('results', [])

print(f'📊 {len(results)} most recent tasks in Notion:\n')
for i, r in enumerate(results, 1):
    title = r['properties']['Name']['title'][0]['text']['content'] if r['properties']['Name']['title'] else '(Untitled)'
    created = r['created_time']
    print(f'{i}. {title}')
    print(f'   Created: {created}')
    print()
"

echo ""
echo "💡 If your newest task ISN'T here, the webhook might not be working."
