#!/bin/bash
# Test both Todoist and Capacities APIs

set -e

echo "🧪 Testing Todoist-Capacities Sync APIs"
echo ""

# Check if service is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Service is not running!"
    echo "   Start it with: ./run_simple.sh"
    exit 1
fi

echo "✅ Service is running"
echo ""

# Test service status
echo "📊 Service Status:"
curl -s http://localhost:8000/ | python -m json.tool
echo ""

# Test Todoist API
echo "📝 Testing Todoist API..."
TODOIST_RESULT=$(curl -s http://localhost:8000/test/todoist)
TODOIST_STATUS=$(echo "$TODOIST_RESULT" | python -c "import sys, json; print(json.load(sys.stdin)['status'])")

if [ "$TODOIST_STATUS" = "success" ]; then
    echo "✅ Todoist API connected successfully"
    echo "$TODOIST_RESULT" | python -m json.tool | head -15
else
    echo "❌ Todoist API failed"
    echo "$TODOIST_RESULT" | python -m json.tool
fi
echo ""

# Test Capacities API
echo "🗂️  Testing Capacities API..."
CAPACITIES_RESULT=$(curl -s http://localhost:8000/test/capacities)
CAPACITIES_STATUS=$(echo "$CAPACITIES_RESULT" | python -c "import sys, json; print(json.load(sys.stdin)['status'])")

if [ "$CAPACITIES_STATUS" = "success" ]; then
    echo "✅ Capacities API connected successfully"
    echo "$CAPACITIES_RESULT" | python -m json.tool
else
    echo "❌ Capacities API failed"
    echo "$CAPACITIES_RESULT" | python -m json.tool
fi
echo ""

echo "🎉 All tests complete!"

