#!/bin/bash
# Initial setup script for development environment

set -e

echo "🔧 Setting up Todoist-Capacities Sync development environment"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [[ $(echo -e "$python_version\n$required_version" | sort -V | head -n1) != "$required_version" ]]; then
    echo "❌ Python 3.11+ is required, but you have $python_version"
    echo "   Install Python 3.11 or higher and try again"
    exit 1
fi
echo "✅ Python $python_version"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo ""
    echo "📦 Poetry not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    
    echo ""
    echo "⚠️  Please add Poetry to your PATH and restart your shell:"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run this script again."
    exit 0
fi
echo "✅ Poetry $(poetry --version | awk '{print $3}')"

# Install dependencies
echo ""
echo "📦 Installing project dependencies..."
poetry install

# Check for .env file
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  .env file not found"
    echo "   A template .env file has been created with your API tokens"
    echo "   Edit .env and add your CAPACITIES_SPACE_ID"
    echo ""
    echo "   Get your Space ID from: Capacities → Settings → Space settings"
    exit 1
fi

# Check if CAPACITIES_SPACE_ID is set
if grep -q "YOUR_SPACE_ID_HERE" .env; then
    echo ""
    echo "⚠️  Please update CAPACITIES_SPACE_ID in .env file"
    echo "   Get it from: Capacities → Settings → Space settings"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Next steps:"
echo "1. Run the service locally:"
echo "   ./scripts/run_local.sh"
echo ""
echo "2. Test with sample webhook:"
echo "   curl -X POST http://localhost:8000/todoist/webhook \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d @scripts/sample_webhook.json"
echo ""
echo "3. Or create a real task in Todoist with @capsync label!"
echo ""
echo "📚 Read GETTING_STARTED.md for detailed instructions"

