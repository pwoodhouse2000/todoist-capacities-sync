#!/bin/bash

# Test webhook with a simulated Todoist event
# This simulates what Todoist sends when a task is created

SERVICE_URL="https://todoist-notion-sync-769386743044.us-west1.run.app"

echo "🧪 Testing webhook with simulated Todoist event..."
echo ""

# Simulate an item:added event
curl -X POST "$SERVICE_URL/todoist/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "item:added",
    "user_id": "2415995",
    "version": "9",
    "event_data": {
      "id": "9999999999",
      "content": "Webhook test task",
      "description": "This is a test from the webhook",
      "project_id": "2005983004",
      "labels": ["capsync"],
      "priority": 1,
      "due": null,
      "parent_id": null,
      "is_completed": false
    }
  }' | jq

echo ""
echo "✅ Webhook test sent!"
echo "Check the logs to see if it was received:"
echo ""
echo "  gcloud run services logs tail todoist-notion-sync --region=us-west1 --project=notion-todoist-sync-464419"

