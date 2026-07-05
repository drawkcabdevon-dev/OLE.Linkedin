# OLE Social Agent

AI-powered social media management agent for **Online Everywhere** (onlineeverywhere.com). Manages LinkedIn content creation, scheduling, publishing, and lead generation — all through a Telegram bot interface.

## Features

- **Content Pipeline** — Gemini 2.5 Flash drafts optimized for Barbados SMEs
- **Auto-Scheduling** — Daily posts via APScheduler (local) or Cloud Scheduler (Cloud Run)
- **Preview, Edit & Approve** — Draft mode queues posts for review; edit with feedback before publishing
- **Content Memory** — Saved preferences (tone, length, style) persist across sessions and influence all drafts
- **Trends Integration** — Google Trends + Gemini for data-driven topic selection
- **Competitor Mirroring** — Analyze competitor posts, create counter-content
- **Image Generation** — Pollinations.ai free-tier visuals; preview images in chat before posting
- **Premium Reference System** — Save liked photos as style references for future drafts
- **Lead Tracking** — SQLite-based CRM for LinkedIn outreach
- **Calendar Management** — Planned content calendar with topic rotation
- **Cloud Run Deployment** — Fully containerized, webhook-based, CI/CD via Cloud Build

## Commands

| Command | Description |
|---------|-------------|
| `/authorize` | Link this chat (required once) |
| `/draft <topic>` | Generate a LinkedIn post draft |
| `/brainstorm <topic>` | 8 rapid-fire content ideas |
| `/planned` | Upcoming 7-day calendar |
| `/preview` | Preview pending draft (text + image) |
| `/preview_image` | Preview just the generated image |
| `/approve` | Publish pending draft |
| `/reject` | Skip pending draft |
| `/edit <feedback>` | Revise the pending draft with your feedback |
| `/remember <key>=<value>` | Save a preference (e.g. `tone=more casual`) |
| `/preferences` | View all saved content preferences |
| `/forget <key>` | Remove a saved preference |
| `/hot` | Google Trends top topic → instant draft |
| `/mirror <topic>` | Competitor analysis + counter-content |
| `/history` | Last 10 published posts |
| `/post <text>` | Post directly to LinkedIn |
| `/post_image` | Post with image to LinkedIn |
| `/schedule` | Manage auto-schedule (on/off/time/mode/topics) |
| `/post_now` | Run pipeline immediately |
| `/status` | System health check |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run bot (polling mode)
python telegram_bot.py
```

## Cloud Run Deployment

```bash
# One-shot deploy
./deploy.sh

# Or via Cloud Build
gcloud builds submit --project=YOUR_PROJECT \
  --substitutions=_WEBHOOK_URL=https://your-service-uc.a.run.app,\
_SCHEDULER_SECRET=your-secret,\
_AUTHORIZED_CHAT_ID=your-telegram-chat-id,\
_SERVICE_ACCOUNT=your-sa@project.iam.gserviceaccount.com
```

The bot auto-detects `WEBHOOK_URL` — if set, it runs in webhook mode (FastAPI + Uvicorn on port 8080). Otherwise it uses long-polling.

## Memory System

Preferences are stored in `preferences.json` and injected into every draft:

```
/remember tone=conversational and warm
/remember length=short, 2-3 paragraphs
/remember style=lead with a statistic
/remember topics=prefer AI and automation angles
```

Use `/preferences` to view and `/forget <key>` to remove.

## Project Structure

```
├── telegram_bot.py          # Main Telegram bot (conversational + scheduled)
├── gemini_client.py         # Shared Vertex AI Gemini client (ADC auth)
├── mcp_servers/
│   ├── linkedin_server.py   # LinkedIn API (post, image, search)
│   ├── content_server.py    # Gemini 2.5 Flash content generation
│   ├── image_server.py      # Pollinations.ai / Stitch image generation
│   ├── local_server.py      # SQLite (drafts, published, leads, calendar)
│   ├── research_server.py   # Google Trends + Gemini research
│   └── design_server.py     # HyperFrames/Seedance/Higgsfield motion graphics
├── templates/               # LinkedIn post templates, HyperFrames HTML
├── authorized_chats.json    # Authorized Telegram chat IDs
├── schedule_config.json     # Schedule config (topics, days, mode)
├── Dockerfile               # Cloud Run container
├── cloudbuild.yaml          # Cloud Build CI/CD
└── deploy.sh                # One-shot deployment script
```

## Environment Variables

| Variable | Source | Required |
|----------|--------|----------|
| `TELEGRAM_BOT_TOKEN` | @BotFather (Secret Manager) | Yes |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn OAuth (Secret Manager) | Yes |
| `LINKEDIN_ORG_ID` | LinkedIn company page | Yes (125564340) |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `WEBHOOK_URL` | Cloud Run URL | For webhook mode |
| `SCHEDULER_SECRET` | Your secret | For Cloud Scheduler |
| `AUTHORIZED_CHAT_ID` | Your Telegram chat ID | For first-time auth |
| `OLE_DATA_DIR` | Data directory | Defaults to `/app/data` |

## Secrets (Secret Manager)

| Secret Name | Env Var |
|-------------|---------|
| `telegram-bot-token` | `TELEGRAM_BOT_TOKEN` |
| `linkedin-access-token` | `LINKEDIN_ACCESS_TOKEN` |
| `stitch-api-key` | `STITCH_API_KEY` |

## License

Online Everywhere — Data-Driven Marketing, Accelerated by AI
