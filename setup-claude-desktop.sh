#!/bin/bash
# Generate Claude Desktop config for Kinship Earth
# Usage: ./setup-claude-desktop.sh

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo "Kinship Earth — Claude Desktop Setup"
echo "====================================="
echo ""
echo "Repository: $REPO_DIR"
echo "Config file: $CONFIG_FILE"
echo ""

# Check prerequisites
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Install it with:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    exit 1
fi

# Sync dependencies
echo "Installing dependencies..."
cd "$REPO_DIR" && uv sync --quiet

# Generate the config snippet
cat <<EOF

Add this to your Claude Desktop config file:
  $CONFIG_FILE

--- COPY BELOW THIS LINE ---

{
  "mcpServers": {
    "kinship-earth": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "$REPO_DIR",
        "--package", "kinship-orchestrator",
        "python", "-m", "kinship_orchestrator.server"
      ]
    }
  }
}

--- COPY ABOVE THIS LINE ---

Then restart Claude Desktop and look for the hammer icon.

Try asking Claude:
  "What ecological data sources are available?"
  "What was the climate at latitude 45.82, longitude -121.95 on June 15, 2023?"
  "Search for dolphins near Woods Hole, Massachusetts"

EOF
