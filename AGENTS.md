# Online Everywhere Social Agent

## Entrypoint & run

```bash
pip install -r requirements.txt
python telegram_bot.py          # polling mode (local dev)
# or with env:
TELEGRAM_BOT_TOKEN=xxx python telegram_bot.py
```

Makefile: `make install`, `make bot`, `make build`/`up`/`down`/`logs` (Docker Compose).

## Project structure

```
telegram_bot.py          ← single main entrypoint
gemini_client.py         ← Vertex AI Gemini client (ADC auth)
mcp_servers/             ← 6 MCP servers imported directly (not subprocess)
  content_server.py      ← Gemini 2.5 Flash content generation
  image_server.py        ← Pollinations.ai / Stitch images
  linkedin_server.py     ← LinkedIn API (post, image, search)
  local_server.py        ← SQLite (drafts, published, leads, calendar)
  research_server.py     ← Google Trends + Gemini research
  design_server.py       ← HyperFrames/Seedance/Higgsfield motion
adk_agent.py             ← Optional ADK agent (deployed via deploy_adk.py)
agent_engine_client.py   ← Optional Agent Engine client (env AGENT_ENGINE_RESOURCE)
```

## LinkedIn constraints (non-negotiable)

- **Always post as org**: `urn:li:organization:125564340` (Online Everywhere)
- **No organic carousel** — LinkedIn API rejects CAROUSEL. Use `post_multi_image()` for scrollable gallery UX.
- **No document posts** — DOCUMENT returns 403.
- LinkedIn tokens stored in Secret Manager: `telegram-bot-token`, `linkedin-access-token`, `stitch-api-key`.

## Bot behavior

- `/authorize` required once per chat (stored in `authorized_chats.json`)
- Schedule uses APScheduler locally, Cloud Scheduler on Cloud Run
- Two cron jobs: proactive ideas at 09:00 UTC, content pipeline at configurable time
- Mode `draft` = preview + approve; mode `auto` = post directly
- Preferences persist via `/remember key=value` → `preferences.json`

## Cloud Run deploy

```bash
./deploy.sh              # one-shot (project: linkedin-agent-501504, region: us-central1)
# or via Cloud Build:
gcloud builds submit --project=linkedin-agent-501504 \
  --substitutions=_WEBHOOK_URL=...,_SCHEDULER_SECRET=...,_AUTHORIZED_CHAT_ID=...,_SERVICE_ACCOUNT=...
```

- GCP project: `linkedin-agent-501504`, region: `us-central1`
- Service: `ole-telegram-bot`, min-instances=1, max-instances=1, concurrency=1, memory=1Gi
- Webhook auto-detected: if `WEBHOOK_URL` is set, runs FastAPI + Uvicorn (port 8080); else polling
- Entry: `python telegram_bot.py` (Dockerfile CMD)

## Data

- `data/data.db` — SQLite (drafts, published, leads, calendar)
- `assets/` — generated images, PDFs, HTML
- `templates/` — post templates, HyperFrames HTML
- `preferences.json`, `schedule_config.json`, `authorized_chats.json` — JSON config files

## No tests / no lint / no typecheck

No test suite, linter, or type checker configured. Validate by running the bot.

## Brand voice (OLE)

- Target: Barbados SMEs
- Tone: direct, data-driven, quantified hooks, zero jargon
- Colors: Primary `#4285F4`, Red `#EA4335`, Yellow `#FBBC05`, Green `#34A853`, Navy `#202124`

## Existing instruction files

- `CLAUDE.md` — full agent identity, tool reference, and constraints (carries more detail)
- `DESIGN.md` — brand design system (colors, typography, layout)
- `skills/linkedin_skill.md`, `skills/design_skill.md` — skill definitions
