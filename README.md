# OLE Social Agent

AI-powered social media management agent for **Online Everywhere** (onlineeverywhere.com). Manages LinkedIn content creation, scheduling, publishing, and lead generation — all through a Telegram bot interface.

## Features

- **Content Pipeline** — Gemini 2.5 Flash drafts optimized for Barbados SMEs
- **Auto-Scheduling** — Daily posts at 14:00 UTC via APScheduler (local) or Cloud Scheduler (Cloud Run)
- **Preview & Approve** — Draft mode queues posts for review before publishing
- **Trends Integration** — Google Trends + Gemini for data-driven topic selection
- **Competitor Mirroring** — Analyze competitor posts, create counter-content
- **Image Generation** — Pollinations.ai free-tier visuals for posts
- **Lead Tracking** — SQLite-based CRM for LinkedIn outreach
- **Calendar Management** — Planned content calendar with rotation

## Commands

| Command | Description |
|---------|-------------|
| `/draft <topic>` | Generate a LinkedIn post draft |
| `/brainstorm <topic>` | 8 rapid-fire content ideas |
| `/planned` | Upcoming 7-day calendar |
| `/preview` | Preview pending draft |
| `/approve` | Publish pending draft |
| `/reject` | Skip pending draft |
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

# Configure environment
cp .env.template ~/.social-agent/.env  # edit with your tokens

# Run bot (polling mode)
python telegram_bot.py

# Or via Docker
docker compose up -d
```

## Deployment

### Local (Polling)
```bash
python telegram_bot.py
```

### Cloud Run (Webhook)
1. Store secrets in Secret Manager
2. Set `WEBHOOK_URL` env var pointing to your Cloud Run URL
3. Deploy: `gcloud builds submit`
4. Register webhook with Telegram API

See `deploy.sh` for the full deployment script.

## Project Structure

```
├── telegram_bot.py          # Main Telegram bot (conversational + scheduled)
├── mcp_servers/
│   ├── linkedin_server.py   # LinkedIn API (post, image, search)
│   ├── content_server.py    # Gemini 2.5 Flash content generation
│   ├── image_server.py      # Pollinations.ai image generation
│   ├── local_server.py      # SQLite (drafts, published, leads, calendar)
│   ├── research_server.py   # Google Trends + Gemini research
│   └── design_server.py     # HyperFrames/Seedance/Higgsfield motion graphics
├── templates/               # LinkedIn post templates, HyperFrames HTML
├── skills/                  # opencode agent skills
├── Dockerfile               # Cloud Run container
├── cloudbuild.yaml          # Cloud Build CI/CD
└── deploy.sh                # One-shot deployment script
```

## Environment Variables

| Variable | Source | Required |
|----------|--------|----------|
| `TELEGRAM_BOT_TOKEN` | @BotFather | Yes |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn OAuth | Yes |
| `LINKEDIN_ORG_ID` | LinkedIn company page | Yes (125564340) |
| `GOOGLE_API_KEY` | Google AI Studio | Yes (Gemini) |
| `WEBHOOK_URL` | Cloud Run URL | For webhook mode |
| `SCHEDULER_SECRET` | Your secret | For Cloud Scheduler |

## License

Online Everywhere — Data-Driven Marketing, Accelerated by AI
