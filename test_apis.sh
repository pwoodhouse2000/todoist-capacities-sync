#!/bin/bash

echo "🧪 Testing Todoist-Notion Sync APIs"
echo ""

# Check if service is running
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ Service is running"
else
    echo "❌ Service is not running. Please start it with ./run_simple.sh"
    exit 1
fi

echo ""
echo "📊 Service Status:"
curl -s http://localhost:8000/ | python3 -m json.tool
echo ""

echo "📝 Testing Todoist API..."
TODOIST_TEST_RESPONSE=$(curl -s "http://localhost:8000/test/todoist?show_tasks=true")
if echo "$TODOIST_TEST_RESPONSE" | grep -q "\"status\": \"success\""; then
    echo "✅ Todoist API connected successfully"
    echo "$TODOIST_TEST_RESPONSE" | python3 -m json.tool
else
    echo "❌ Todoist API test failed"
    echo "$TODOIST_TEST_RESPONSE" | python3 -m json.tool
fi
echo ""

echo "🗂️  Testing Notion API..."
NOTION_TEST_RESPONSE=$(curl -s http://localhost:8000/test/notion)
if echo "$NOTION_TEST_RESPONSE" | grep -q "\"status\": \"success\""; then
    echo "✅ Notion API connected successfully"
    echo "$NOTION_TEST_RESPONSE" | python3 -m json.tool
else
    echo "❌ Notion API test failed"
    echo "$NOTION_TEST_RESPONSE" | python3 -m json.tool
fi
echo ""

echo "🎉 All tests complete!"
