#!/bin/bash
set -e

echo "=== Online Everywhere Agent Container ==="
echo "Starting Telegram bot..."

# The Telegram bot is the long-running process.
# MCP servers are called on-demand by the bot via direct Python imports.
exec python telegram_bot.py
