#!/bin/bash
# Test webhook manually to verify it works

echo "🧪 Testing Webhook Endpoint..."
echo ""

# Simulate a Todoist webhook event
curl -X POST "https://todoist-notion-sync-769386743044.us-west1.run.app/todoist/webhook" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Todoist-Webhooks" \
  -H "X-Todoist-Hmac-SHA256: test" \
  -d '{
    "event_name": "item:added",
    "user_id": "12345",
    "event_data": {
      "id": "9625088106",
      "content": "Yet another test",
      "description": "",
      "project_id": "2005983004",
      "labels": ["capsync"],
      "priority": 1,
      "due": null,
      "added_at": "2025-10-10T02:30:46.369579Z"
    }
  }'

echo ""
echo ""
echo "✅ If you see a successful response above, the webhook endpoint is working!"
echo "🔍 Check Cloud Run logs: https://console.cloud.google.com/run/detail/us-west1/todoist-notion-sync/logs?project=notion-todoist-sync-464419"

