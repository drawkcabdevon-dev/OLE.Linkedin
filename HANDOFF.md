# Online Everywhere — LinkedIn Agent Handoff

This document hands off the complete LinkedIn agent system to you. Your job is to
integrate everything with the existing Telegram channel on this VM.

## What's Here

### Directory Layout
```
~/social-agent/
  mcp_servers/
    linkedin_server.py    — LinkedIn posting (text, image, multi-image, carousel)
    local_server.py       — SQLite DB (drafts, published, leads, calendar)
    content_server.py     — Google Gemini content generation
    image_server.py       — Pollinations.ai / NVIDIA image gen
    design_server.py      — HyperFrames / Seedance / Higgsfield design assets
  telegram_bot.py         — Telegram bot (standalone, not MCP)
  templates/              — Post templates, HyperFrames HTML
  data/                   — SQLite database directory
  assets/                 — Generated images and PDFs
  requirements.txt        — Python deps
  Dockerfile              — Container build
  docker-compose.yml      — Docker deployment
  deploy.sh               — SCP/everything to VM script
  HANDOFF.md              — This file (context for you)
```

### MCP Servers (registered in opencode.json)
The servers talk **stdin/stdout MCP protocol** to opencode. Each is a Python
script using `mcp.server.fastmcp`. Tools available per server:

| Server | Tools |
|--------|-------|
| **linkedin** | `create_post`, `post_image`, `post_multi_image`, `create_carousel_post` (sponsored only), `post_document` (gated), `images_to_pdf`, `whoami`, `get_profile`, `list_organizations`, `search_content` |
| **local-data** | `save_draft`, `list_drafts`, `log_published`, `list_published`, `schedule_content`, `get_calendar`, `add_lead`, `list_leads` |
| **research** | `trending_searches`, `interest_over_time`, `related_queries`, `content_opportunities`, `analyze_topic`, `daily_brief` |
| **content** | `draft_post`, `rewrite_post`, `generate_carousel_script`, `generate_batch_ideas` |
| **images** | `generate_image`, `generate_social_graphic`, `generate_carousel_images`, `list_generated_images` |
| **design** | `generate_hyperframes`, `generate_seedance_prompt`, `generate_higgsfield_script`, `render_hyperframes`, `list_design_assets` |

## What You Need to Do

### 1. Set up .env
Edit `~/social-agent/.env` with:
```
LINKEDIN_ACCESS_TOKEN=...    # From LinkedIn Developer App
LINKEDIN_ORG_ID=125564340    # Online Everywhere org
GOOGLE_API_KEY=...           # Google AI Studio key (Gemini 2.5 Flash)
TELEGRAM_BOT_TOKEN=...       # From @BotFather
OLE_DATA_DIR=/home/devon/social-agent
```

### 2. Register MCP Servers in opencode.json
Install into `~/.config/opencode/opencode.json`:
```json
{
  "mcpServers": {
    "local-data": {
      "command": "python3",
      "args": ["/home/devon/social-agent/mcp_servers/local_server.py"]
    },
    "linkedin": {
      "command": "python3",
      "args": ["/home/devon/social-agent/mcp_servers/linkedin_server.py"]
    },
    "content": {
      "command": "python3",
      "args": ["/home/devon/social-agent/mcp_servers/content_server.py"]
    },
    "images": {
      "command": "python3",
      "args": ["/home/devon/social-agent/mcp_servers/image_server.py"]
    },
    "design": {
      "command": "python3",
      "args": ["/home/devon/social-agent/mcp_servers/design_server.py"]
    },
    "research": {
      "command": "python3",
      "args": ["/home/devon/social-agent/mcp_servers/research_server.py"]
    }
  }
}
```

### 3. Integrate Telegram Channel
The `telegram_bot.py` is a standalone bot (not MCP). It imports and calls the
server functions directly (bypasses opencode). To run it:

```bash
cd ~/social-agent
pip install -r requirements.txt  # if not done
python3 telegram_bot.py
```

To keep it running 24/7 as a **systemd service**:
```bash
sudo tee /etc/systemd/system/ole-agent.service << EOF
[Unit]
Description=Online Everywhere LinkedIn Telegram Bot
After=network.target

[Service]
Type=simple
User=devon
WorkingDirectory=/home/devon/social-agent
ExecStart=/usr/bin/python3 /home/devon/social-agent/telegram_bot.py
Restart=always
EnvironmentFile=/home/devon/social-agent/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload && sudo systemctl enable --now ole-agent
```

**Bot commands** (once token is set and bot is running):
- `/authorize` — Authorize this chat
- `/draft <topic>` — Draft a LinkedIn post
- `/post <text>` — Post to LinkedIn
- `/post_image <text>` — Reply to an image with caption
- `/status` — Health check

### 4. Enable the linkedin-coordinator Agent
The `opencode.json` includes an agent config for a `linkedin-coordinator`. It
should be registered as a subagent. This agent:
- Generates content via Gemini
- Creates images via Pollinations
- Posts to Online Everywhere LinkedIn company page
- Posts multi-image as scrollable galleries (not carousel — gated for organic)

The agent prompt should instruct it to:
- Post as **organization** (DEFAULT_ORG_ID = 125564340)
- Use **`post_multi_image`** instead of `create_carousel_post` for multi-image
- Generate content mix: 50% educational + 30% lead magnet + 20% engagement
- Voice: confident, plain English, quantified hooks, zero jargon
- Target: Barbados SMEs with ghost sites

## Architecture Notes

### Key Constraints
- LinkedIn `/v2/me` deprecated — use OpenID `/v2/userinfo` (already handled)
- **Carousel posts** (`CAROUSEL` category) are **sponsored only** — use
  `post_multi_image` with `IMAGE` category for organic multi-image posts
- **Document posts** (PDF) return 403 — LinkedIn gated this feature
- **Pollinations.ai** is free (no key) — use for image generation
- **Gemini 2.5 Flash** — Google API key required for content generation
- **NVIDIA API key** exists but not wired — available for higher-quality images

### Portability
All servers respect the `OLE_DATA_DIR` env var. Set it to the data directory and
everything (DB, assets, config) resolves relative to it. Default: the
`social-agent` directory you're in.

## Quick Verification
After setup, run:
```bash
cd ~/social-agent
python3 -c "
import sys; sys.path.insert(0, 'mcp_servers')
from linkedin_server import whoami
import json; print(json.loads(whoami()))
"
```

Expected: `{"name": "Devon Clarke", "headline": ""}`

Then test the bot:
```bash
python3 telegram_bot.py  # Ctrl+C to stop, runs 24/7 via systemd
```
