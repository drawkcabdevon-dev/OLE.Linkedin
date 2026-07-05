#!/usr/bin/env bash
# Setup script for the Online Everywhere Social Media Agent
set -e

echo "=== Online Everywhere Social Agent Setup ==="
echo ""

# 1. Install Python deps
echo "[1/4] Installing Python dependencies..."
pip3 install -r ~/social-agent/requirements.txt 2>&1 | tail -2

# 2. Create env file
echo "[2/4] Setting up .env..."
ENV_FILE=~/.social-agent/.env
if [ ! -f "$ENV_FILE" ]; then
  cp ~/social-agent/.env.template "$ENV_FILE"
  echo "  Created $ENV_FILE — edit it with your API keys!"
else
  echo "  $ENV_FILE already exists, skipping"
fi

# 3. Init the database
echo "[3/4] Initializing database..."
python3 -c "import sys; sys.path.insert(0, '$HOME/social-agent/mcp_servers'); exec(open('$HOME/social-agent/mcp_servers/local_server.py').read().split('def main')[0])"
echo "  DB ready at ~/.social-agent/data.db"

# 4. Register MCP servers with OpenCode (if not already)
echo "[4/4] Registering with OpenCode..."
opencode mcp add "local-data" 2>/dev/null || echo "  local-data already registered"
opencode mcp add "linkedin" 2>/dev/null || echo "  linkedin already registered"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit ~/.social-agent/.env with your LinkedIn access token"
echo "  2. Run: opencode run --agent linkedin-coordinator 'Research AI marketing trends in Barbados and draft a post'"
echo "  3. Or use @linkedin-coordinator in any OpenCode session"
