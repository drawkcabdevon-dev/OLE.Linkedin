"""
Telegram Bot for Online Everywhere LinkedIn Agent.
Full scheduling: auto-generate + post content on cron schedule.

Commands:
  /start              — Welcome
  /help               — All commands
  /authorize          — Authorize this chat
  /draft <topic>      — Draft a LinkedIn post
  /trends             — Today's trending searches
  /research <topic>   — Deep research + content ideas
  /post <text>        — Post to LinkedIn
  /post_image <text>  — Reply to image to post it
  /schedule           — Set schedule (see subcommands below)
  /schedule on        — Enable auto-posting
  /schedule off       — Disable auto-posting
  /schedule status    — Show current schedule
  /schedule time HH:MM — Set posting time (UTC)
  /schedule days M,W,F — Set days (daily, M,W,F, Mon,Wed,Fri, etc.)
  /schedule mode auto|draft — Auto-post or save as draft for review
  /schedule topics t1,t2,t3 — Topics to rotate through
  /post_now           — Run the content pipeline immediately
  /status             — System health check

Run:
  TELEGRAM_BOT_TOKEN=xxx python telegram_bot.py
"""

import os
import sys
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("telegram-bot")

# ── Gemini rate limiter ─────────────────────────────────────────────

class RateLimiter:
    """Simple token-bucket rate limiter."""
    def __init__(self, calls_per_minute: int = 4):
        self.min_interval = 60.0 / calls_per_minute
        self.last_call = 0.0

    def wait_time(self) -> float:
        elapsed = time.time() - self.last_call
        return max(0.0, self.min_interval - elapsed)

    def can_call(self) -> bool:
        return self.wait_time() == 0.0

    def record_call(self):
        self.last_call = time.time()

_gemini_limiter = RateLimiter(calls_per_minute=4)
_gemini_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 300  # 5 minutes

def gemini_chat(user_text: str, system_prompt: str) -> str | None:
    """Call Gemini with rate limiting + caching. Returns text or None if rate limited."""
    cache_key = f"{hash(user_text)}"
    if cache_key in _gemini_cache:
        text, ts = _gemini_cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return text

    if not _gemini_limiter.can_call():
        return None

    try:
        import httpx
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
        GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 512},
        }
        _gemini_limiter.record_call()
        r = httpx.post(f"{GEMINI_URL}?key={GOOGLE_API_KEY}", json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if candidates:
            text = candidates[0]["content"]["parts"][0]["text"]
            _gemini_cache[cache_key] = (text, time.time())
            return text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("Gemini 429 — rate limited")
        else:
            logger.warning(f"Gemini error: {e}")
    except Exception as e:
        logger.warning(f"Gemini error: {e}")
    return None

def detect_intent(text: str) -> str:
    """Simple intent matching to avoid Gemini calls for common queries."""
    t = text.lower().strip()
    if t in ("hi", "hello", "hey", "sup", "yo", "what's up", "good morning", "good evening"):
        return "greeting"
    if any(w in t for w in ("what can you do", "help", "commands", "capabilities", "what do you do")):
        return "help"
    if any(w in t for w in ("schedule", "posting time", "when do you post", "post daily", "how often")):
        return "schedule_query"
    if any(w in t for w in ("thanks", "thank you", "thx", "appreciate", "good", "great", "perfect", "nice")):
        return "thanks"
    if any(w in t for w in ("who are you", "who is this", "what is this", "explain yourself")):
        return "whoami"
    if any(w in t for w in ("trending", "what's hot", "whats hot", "hot topic", "trend", "what people talking about")):
        return "trends"
    if any(w in t for w in ("brainstorm", "ideas", "give me ideas", "think of", "come up with", "what should we post")):
        return "brainstorm"
    if any(w in t for w in ("what's planned", "whats planned", "upcoming", "what's coming", "calendar", "what's next", "planned posts")):
        return "planned"
    if any(w in t for w in ("history", "what was posted", "previous posts", "past posts", "what did we post", "recent posts")):
        return "history"
    if any(w in t for w in ("approve", "post it", "publish it", "yes post", "go ahead", "looks good")):
        return "approve"
    if any(w in t for w in ("reject", "skip", "no", "don't post", "not that", "discard")):
        return "reject"
    return "unknown"

INTENT_RESPONSES = {
    "greeting": "Hey! I'm your LinkedIn coordinator. Need ideas? A post drafted? A competitor countered? Just say the word.\n\nTry: /brainstorm, /draft, /hot, /mirror, or just tell me what you're thinking.",
    "help": "I handle your LinkedIn content so you don't have to:\n\n• /draft <topic> — Create a post\n• /hot — Instant post from trending topics\n• /mirror <topic> — Counter a competitor\n• /post <text> — Post immediately\n• /schedule — Manage daily auto-posting\n\nOr just talk to me — I'll figure out what you need.",
    "schedule_query": "Your daily post runs at **14:00 UTC** with an image. Every morning at **9:00 UTC** I send you 3 post ideas to review. Use /schedule to tweak the time, switch to draft mode for review, or change topics.",
    "thanks": "Always. Holler if you need a post or want to check what's trending.",
    "whoami": "I'm your LinkedIn coordinator for Online Everywhere. I draft posts, check trends, mirror competitors, and keep your daily content flowing. Think of me as your in-house social media strategist who never sleeps.",
    "trends": "Use /hot to check what's trending right now and get an instant post draft. Or /trends to just see the list.",
    "brainstorm": "Use /brainstorm <topic> and I'll throw out 8 rapid-fire post ideas. Or just tell me what you want to brainstorm about and I'll run with it.",
    "planned": "Use /planned to see your upcoming content schedule — what's posting when, topic rotation, and next few days at a glance.",
    "history": "Use /history to see what's already been posted. I keep a log so we don't repeat ourselves.",
    "approve": "Use /approve to publish the last previewed post. If there's nothing pending, try /preview first.",
    "reject": "Use /reject to skip the pending draft. I'll move to the next topic.",
}

FALLBACK_REPLY = "Got it. Use /draft to create a post, /hot for trending topics, or /mirror to counter something a competitor posted. Or just keep chatting — I'll help however I can."

RATE_LIMITED_REPLY = "I'm catching up on requests — hit the free tier rate limit. Give me about 30 seconds and try again, or ask me something simple and I'll handle it without the heavy AI."

BASE = Path.home() / "social-agent"
AUTHORIZED_CHATS_FILE = BASE / "authorized_chats.json"
SCHEDULE_CONFIG_FILE = BASE / "schedule_config.json"
PENDING_DRAFT_FILE = BASE / "pending_draft.json"
NOTIFY_CHAT_ID = None  # Set when /authorize runs
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")  # For direct HTTP notify

# ── Pending draft queue (preview → approve flow) ────────────────────

def save_pending_draft(topic: str, content: str, image_path: str | None = None):
    """Save a generated post for preview/approval."""
    data = {"topic": topic, "content": content, "image_path": image_path, "created_at": datetime.now(timezone.utc).isoformat()}
    PENDING_DRAFT_FILE.write_text(json.dumps(data, indent=2))
    logger.info(f"Pending draft saved: {topic}")

def load_pending_draft() -> dict | None:
    if PENDING_DRAFT_FILE.exists():
        return json.loads(PENDING_DRAFT_FILE.read_text())
    return None

def clear_pending_draft():
    if PENDING_DRAFT_FILE.exists():
        PENDING_DRAFT_FILE.unlink()

# ── Authorized chat management ──────────────────────────────────────

def load_authorized_chats() -> set[int]:
    if AUTHORIZED_CHATS_FILE.exists():
        return set(json.loads(AUTHORIZED_CHATS_FILE.read_text()))
    return set()

def save_authorized_chats(chats: set[int]):
    AUTHORIZED_CHATS_FILE.write_text(json.dumps(list(chats)))

def is_authorized(chat_id: int) -> bool:
    return chat_id in load_authorized_chats()

# ── Schedule config ─────────────────────────────────────────────────

DEFAULT_SCHEDULE = {
    "enabled": False,
    "time": "12:00",
    "days": "daily",
    "mode": "draft",       # "draft" = preview + approve, "auto" = post directly
    "topics": [
        "Barbados digital marketing",
        "Barbados SME website optimization",
        "Barbados small business growth",
        "Barbados SEO tips",
        "Barbados social media marketing",
        "Barbados AI for business",
    ],
    "topic_index": 0,
}

def load_schedule() -> dict:
    if SCHEDULE_CONFIG_FILE.exists():
        cfg = json.loads(SCHEDULE_CONFIG_FILE.read_text())
        for k, v in DEFAULT_SCHEDULE.items():
            cfg.setdefault(k, v)
        return cfg
    return dict(DEFAULT_SCHEDULE)

def save_schedule(cfg: dict):
    SCHEDULE_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

def days_to_cron(days_str: str) -> str:
    """Convert 'M,W,F' or 'Mon,Wed,Fri' or 'daily' to cron day-of-week (0=Sun)."""
    mapping = {
        "m": "1", "t": "2", "w": "3", "th": "4", "f": "5", "sa": "6", "su": "0",
        "mon": "1", "tue": "2", "wed": "3", "thu": "4", "fri": "5", "sat": "6", "sun": "0",
        "monday": "1", "tuesday": "2", "wednesday": "3", "thursday": "4",
        "friday": "5", "saturday": "6", "sunday": "0",
        "weekdays": "1-5", "weekends": "0,6",
    }
    s = days_str.strip().lower().replace(" ", "")
    if s == "daily":
        return "*"
    parts = s.split(",")
    mapped = []
    for p in parts:
        p = p.strip()
        if p in mapping:
            mapped.append(mapping[p])
        elif p.isdigit():
            mapped.append(p)
    return ",".join(mapped) if mapped else "*"

# ── LinkedIn posting ────────────────────────────────────────────────

SERVER_DIR = str(Path.home() / "social-agent" / "mcp_servers")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from linkedin_server import create_post, post_image, post_multi_image
from content_server import draft_post, generate_carousel_script
from image_server import generate_social_graphic, generate_carousel_images
from research_server import trending_searches, daily_brief
from local_server import save_draft, log_published, list_published

def post_to_linkedin(text: str, image_path: str | None = None) -> dict:
    if image_path:
        p = Path(image_path)
        if p.suffix.lower() in (".pdf",):
            return {"status": "error", "detail": "PDF not supported via Telegram"}
        return json.loads(post_image(text, str(p)))
    return json.loads(create_post(text))

def is_rate_limited(result: dict) -> bool:
    detail = result.get("detail", "") or str(result)
    return "429" in detail or "Too Many Requests" in detail or "rate limit" in detail.lower()

def friendly_error(result: dict) -> str:
    if is_rate_limited(result):
        return RATE_LIMITED_REPLY
    return f"Error: {result.get('detail', str(result))[:500]}"

def draft_content(topic: str) -> dict:
    return json.loads(draft_post(topic))

def research_trends_data() -> dict:
    try:
        return json.loads(trending_searches())
    except Exception as e:
        return {"status": "error", "detail": str(e)}

def mirror_competitor(competitor_topic: str, competitor_angle: str = "") -> dict:
    """Analyze a competitor's approach or topic and create a counter-post in OLE voice."""
    import httpx
    prompt = competitor_topic
    if competitor_angle:
        prompt += f"\n\nCompetitor's angle: {competitor_angle}\n\nCreate a post that counters or improves on this. Use data and OLE's unique value."
    else:
        prompt += "\n\nCreate an Online Everywhere post that offers a better approach or counters common bad advice in this space."
    return draft_content(prompt)

def generate_daily_ideas(count: int = 3) -> list[dict]:
    """Generate a batch of post ideas for proactive suggestions."""
    try:
        from content_server import generate_batch_ideas
        result = json.loads(generate_batch_ideas(count=count))
        content = result.get("ideas", "")
        # Parse into structured ideas
        ideas = []
        current = {"title": "", "body": ""}
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("IDEA") or line.startswith("**IDEA"):
                if current["title"]:
                    ideas.append(current)
                current = {"title": line, "body": ""}
            elif line:
                current["body"] += line + "\n"
        if current["title"]:
            ideas.append(current)
        return ideas[:count]
    except Exception as e:
        logger.warning(f"generate_daily_ideas failed: {e}")
        return []

def generate_image_for_post(topic: str) -> str | None:
    """Generate a social graphic and return the path, or None."""
    try:
        result = json.loads(generate_social_graphic(topic, "modern"))
        return result.get("output_path")
    except Exception:
        return None

# ── Auto-content pipeline ──────────────────────────────────────────

def run_content_pipeline(app_instance=None):
    """Generate content and post or save as draft. Called by APScheduler."""
    cfg = load_schedule()
    if not cfg.get("enabled"):
        return

    logger.info("Running scheduled content pipeline...")

    # 1. Pick topic (rotate through list)
    topics = cfg.get("topics", DEFAULT_SCHEDULE["topics"])
    idx = cfg.get("topic_index", 0) % len(topics)
    topic = topics[idx]
    cfg["topic_index"] = idx + 1
    save_schedule(cfg)

    # 2. Get trends to find a timely angle
    trend_text = ""
    try:
        brief = json.loads(daily_brief())
        if brief.get("status") == "ok":
            trend_text = brief.get("content_brief", "")
    except Exception:
        pass

    # 3. Draft the post (pass trends as context)
    prompt = topic
    if trend_text:
        prompt = f"{topic}. Use this trending context if relevant: {trend_text[:500]}"
    draft_result = draft_content(prompt)

    if draft_result.get("status") != "drafted":
        logger.error(f"Pipeline: draft failed: {draft_result}")
        _notify(app_instance, f"Pipeline failed at draft stage for topic '{topic}'.")
        return

    post_text = draft_result.get("content") or draft_result.get("post", "")
    if not post_text:
        logger.error("Pipeline: empty draft")
        return

    # 4. Generate an image
    img_path = generate_image_for_post(topic)

    # 5. Post or save as draft
    mode = cfg.get("mode", "draft")
    if mode == "auto":
        try:
            if img_path:
                result = json.loads(post_multi_image(post_text, [img_path]))
            else:
                result = json.loads(create_post(post_text))

            if result.get("status") == "posted":
                log_published("linkedin", result.get("id", ""), post_text)
                _notify(app_instance,
                    f"Auto-posted: {result.get('id', '')}\n"
                    f"Topic: {topic}\n{post_text[:200]}...")
                logger.info(f"Pipeline: auto-posted {result.get('id')}")
            else:
                _notify(app_instance, f"Auto-post failed: {result.get('detail', '')}")
        except Exception as e:
            _notify(app_instance, f"Auto-post error: {e}")
    else:
        # Draft mode — save for review with full preview
        save_pending_draft(topic, post_text, img_path)
        try:
            preview = f"**Draft Ready for Review — {topic}**\n\n{post_text[:1500]}"
            if img_path:
                preview += f"\n\nImage generated at: {img_path}"
            preview += "\n\n---\nSend /approve to publish now, or /reject to skip."
            _notify(app_instance, preview)
            logger.info(f"Pipeline: draft saved for topic '{topic}', awaiting approval")
        except Exception as e:
            logger.error(f"Pipeline: notify draft failed: {e}")

def _notify(app_instance, text: str):
    """Send a notification via Telegram HTTP API (no async needed)."""
    global NOTIFY_CHAT_ID, TELEGRAM_TOKEN
    if NOTIFY_CHAT_ID is None:
        logger.info(f"Notify (no chat): {text[:100]}")
        return
    try:
        import httpx
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        httpx.post(url, json={"chat_id": NOTIFY_CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        logger.warning(f"Notify failed: {e}")

# ── Bot ─────────────────────────────────────────────────────────────

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Set it in .env")
        sys.exit(1)

    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    allowed_users = set()
    app = Application.builder().token(TOKEN).build()

    def get_app():
        return app

    async def require_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        chat_id = update.effective_chat.id if update.effective_chat else 0
        user = update.effective_user
        username = user.username if user else "unknown"

        if is_authorized(chat_id) or chat_id in allowed_users:
            return True

        await update.message.reply_text(
            f"Unauthorized. This bot is private.\n"
            f"Chat ID: {chat_id} | User: @{username}\n"
            "An admin needs to run /authorize from this chat."
        )
        return False

    def schedule_pipeline():
        """Wrapper to call run_content_pipeline with the app instance."""
        run_content_pipeline(app)

    def send_proactive_ideas():
        """Generate and send 3 post ideas to the authorized chat."""
        global NOTIFY_CHAT_ID
        if NOTIFY_CHAT_ID is None:
            logger.info("Proactive ideas: no authorized chat yet")
            return
        ideas = generate_daily_ideas(3)
        if not ideas:
            logger.info("Proactive ideas: none generated")
            return
        msg = "**Good morning! Here are 3 post ideas for today:**\n\n"
        for i, idea in enumerate(ideas, 1):
            title = idea.get("title", f"Idea {i}")
            body = idea.get("body", "")
            msg += f"*{i}. {title}*\n{body[:300].strip()}\n\n"
        msg += "Use /draft to flesh out any of these, or /post to publish."
        _notify(app, msg)
        logger.info("Proactive ideas sent")

    def reschedule_job():
        """Remove old jobs and add new ones based on current config."""
        scheduler.remove_all_jobs()
        cfg = load_schedule()
        if not cfg.get("enabled"):
            logger.info("Scheduler: disabled, no jobs added")
            return
        try:
            # Daily proactive ideas at 9:00 UTC
            scheduler.add_job(
                send_proactive_ideas,
                "cron",
                hour=9,
                minute=0,
                id="proactive_ideas",
                replace_existing=True,
                misfire_grace_time=600,
            )
            # Main content pipeline
            hour, minute = cfg["time"].split(":")
            day_cron = days_to_cron(cfg.get("days", "daily"))
            scheduler.add_job(
                schedule_pipeline,
                "cron",
                day_of_week=day_cron,
                hour=int(hour),
                minute=int(minute),
                id="content_pipeline",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info(f"Scheduler: ideas at 9:00, post at {cfg['time']} on {cfg['days']}")
        except Exception as e:
            logger.error(f"Scheduler setup failed: {e}")

    # ── Command handlers ─────────────────────────────────────────

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "Online Everywhere LinkedIn Agent\n\n"
            "I'm your LinkedIn coordinator. I handle daily posting, "
            "hot topic reactions, and competitor mirroring.\n\n"
            "Start: /authorize to link this chat\n"
            "Then try:\n"
            "/brainstorm  - Rapid-fire post ideas on any topic\n"
            "/hot         - Trending topics, instant post\n"
            "/mirror      - Counter a competitor's move\n"
            "/draft       - Generate a post on any topic\n"
            "/schedule    - Set up daily auto-posting\n"
            "/help      - Full command list"
        )
        await update.message.reply_text(text)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "/authorize          - Link this chat (required once)\n"
            "/brainstorm <topic> - Rapid-fire 8 post ideas\n"
            "/planned            - Calendar + preview next post\n"
            "/preview            - Preview the next post\n"
            "/approve            - Publish the previewed post\n"
            "/reject             - Skip the previewed post\n"
            "/history            - See what's already been posted\n"
            "/hot                - Check trends, draft an instant post\n"
            "/mirror <topic>     - Counter a competitor's move or topic\n"
            "/draft <topic>      - Create a post draft\n"
            "/trends             - Trending searches right now\n"
            "/research <topic>   - Deep research + content ideas\n"
            "/post <text>        - Post to LinkedIn\n"
            "/post_image <text>  - Reply to image to post\n"
            "/schedule           - Schedule management\n"
            "/schedule on        - Enable daily auto-posting\n"
            "/schedule off       - Disable\n"
            "/schedule status    - Current config\n"
            "/schedule time HH:MM - Set time (UTC)\n"
            "/schedule days ...  - daily, M,W,F, etc\n"
            "/schedule mode auto|draft - Auto-post or review\n"
            "/schedule topics ... - Comma-separated topics\n"
            "/post_now           - Run pipeline now\n"
            "/status             - Health check\n"
            "/help               - This message"
        )
        await update.message.reply_text(text)

    async def authorize(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global NOTIFY_CHAT_ID
        chat_id = update.effective_chat.id
        user = update.effective_user
        username = user.username if user else "unknown"

        chats = load_authorized_chats()
        chats.add(chat_id)
        save_authorized_chats(chats)
        allowed_users.add(chat_id)
        NOTIFY_CHAT_ID = chat_id

        await update.message.reply_text(
            f"Chat authorized. @{username} (ID: {chat_id}) can now use the agent."
        )
        logger.info(f"Authorized chat {chat_id} (@{username})")

    async def draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        topic = " ".join(context.args) if context.args else "digital marketing for Barbados SMEs"
        await update.message.reply_text(f"Drafting post about: {topic}...")
        try:
            result = draft_content(topic)
            if result.get("status") == "drafted":
                await update.message.reply_text(f"Draft:\n\n{(result.get('content') or result.get('post', ''))[:3000]}")
            else:
                await update.message.reply_text(friendly_error(result))
        except Exception as e:
            await update.message.reply_text(friendly_error({"detail": str(e)}))

    async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        text = " ".join(context.args) if context.args else ""
        if not text:
            await update.message.reply_text("Usage: /post <text>")
            return
        await update.message.reply_text("Posting to LinkedIn...")
        try:
            result = post_to_linkedin(text)
            if result.get("status") == "posted":
                pid = result.get("id", "")
                log_published("linkedin", pid, text)
                await update.message.reply_text(f"Posted: https://linkedin.com/feed/update/{pid}")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def post_image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        caption = " ".join(context.args) if context.args else "Check this out!"
        if not update.message.reply_to_message or not update.message.reply_to_message.photo:
            await update.message.reply_text("Reply to an image with /post_image <caption>")
            return
        photos = update.message.reply_to_message.photo
        file = await photos[-1].get_file()
        img_path = f"/tmp/telegram_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        await file.download_to_drive(img_path)

        await update.message.reply_text("Posting image to LinkedIn...")
        try:
            result = post_to_linkedin(caption, img_path)
            if result.get("status") == "posted":
                pid = result.get("id", "")
                log_published("linkedin", pid, caption)
                await update.message.reply_text(f"Posted: https://linkedin.com/feed/update/{pid}")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def trends_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        await update.message.reply_text("Fetching trending searches...")
        try:
            result = research_trends_data()
            if result.get("status") == "ok":
                trends = result.get("trends", [])
                if trends:
                    lines = ["**Trending Searches Now:**\n"]
                    for i, t in enumerate(trends[:10], 1):
                        lines.append(f"{i}. {t}")
                    await update.message.reply_text("\n".join(lines))
                else:
                    await update.message.reply_text("No trends found.")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        topic = " ".join(context.args) if context.args else ""
        if not topic:
            await update.message.reply_text("Usage: /research <topic>")
            return
        await update.message.reply_text(f"Researching: {topic}...")
        try:
            sys.path.insert(0, SERVER_DIR)
            from research_server import analyze_topic
            result = json.loads(analyze_topic(topic))
            if result.get("status") == "ok":
                msg = f"**Research: {topic}**\n\n"
                msg += f"Interest Score: {result.get('interest_score', 'N/A')}/100\n"
                msg += f"Peak Interest: {result.get('peak_interest', 'N/A')}\n\n"
                top = result.get("top_related", [])
                if top:
                    msg += "**Related:**\n" + "\n".join(f"- {q}" for q in top[:8]) + "\n\n"
                ideas = result.get("post_ideas", "")
                if ideas:
                    msg += f"**Content Ideas:**\n{ideas[:2000]}"
                await update.message.reply_text(msg[:4000])
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def brainstorm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Brainstorm mode: generates rapid-fire post ideas."""
        if not await require_auth(update, context): return
        topic = " ".join(context.args) if context.args else "digital marketing for Barbados SMEs"
        await update.message.reply_chat_action("typing")
        await update.message.reply_text(f"Brainstorming ideas around: **{topic}**\nGive me a sec...")

        try:
            from content_server import generate_batch_ideas
            result = json.loads(generate_batch_ideas(count=8, theme=topic))
            content = result.get("ideas", "")

            # Parse or use raw
            lines = content.split("\n")
            msg = f"**Brainstorm: {topic}**\n\n"
            idea_count = 0
            for line in lines:
                line = line.strip()
                if line.startswith("IDEA") or line.startswith("**IDEA"):
                    idea_count += 1
                    msg += f"\n{line}\n"
                elif line and idea_count > 0:
                    msg += f"{line}\n"

                if len(msg) > 3500:
                    msg += "\n...more ideas available."
                    break

            if idea_count == 0:
                msg += content[:2000]

            msg += "\n\n---\nLike one? Use /draft with the topic, or /post to publish immediately."
            await update.message.reply_text(msg[:4000])
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                await update.message.reply_text(RATE_LIMITED_REPLY)
            else:
                await update.message.reply_text(f"Brainstorm hit a snag: {error_msg[:200]}")

        # Follow up with a second wave if they want to continue
        await update.message.reply_text(
            "Want me to keep brainstorming on a different angle? Just say the topic "
            "or use /brainstorm again. Or pick one and I'll draft it."
        )

    def next_scheduled_posts(days_to_show: int = 7) -> list[dict]:
        """Calculate upcoming posts based on schedule config."""
        cfg = load_schedule()
        if not cfg.get("enabled") or not cfg.get("topics"):
            return []
        topics = cfg["topics"]
        day_map = {"M": 0, "T": 1, "W": 2, "TH": 3, "F": 4, "SA": 5, "SU": 6}
        day_str = cfg.get("days", "daily").strip().lower()
        if day_str == "daily":
            active_days = set(range(7))
        elif day_str == "weekdays":
            active_days = set(range(1, 6))
        elif day_str == "weekends":
            active_days = {0, 6}
        else:
            active_days = set()
            for d in day_str.split(","):
                d = d.strip().upper()
                if d in day_map:
                    active_days.add(day_map[d])
        start = datetime.now(timezone.utc)
        idx = cfg.get("topic_index", 0)
        from datetime import timedelta
        upcoming = []
        for offset in range(21):
            d = start + timedelta(days=offset)
            if d.weekday() in active_days and d.date() >= start.date():
                topic = topics[idx % len(topics)]
                t = cfg["time"]
                upcoming.append({"date": d.strftime("%a %b %d"), "topic": topic, "time": t})
                idx += 1
                if len(upcoming) >= days_to_show:
                    break
        return upcoming

    async def planned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show upcoming schedule with full preview of the next post."""
        if not await require_auth(update, context): return
        cfg = load_schedule()
        if not cfg.get("enabled"):
            await update.message.reply_text("Schedule is disabled. Enable it with /schedule on")
            return
        upcoming = next_scheduled_posts(7)
        if not upcoming:
            await update.message.reply_text("No upcoming posts scheduled.")
            return

        msg = f"**Upcoming Content Calendar**\n\n"
        msg += f"Schedule: {cfg['time']} UTC daily | Mode: {cfg['mode']}\n\n"
        for entry in upcoming:
            marker = "→ " if entry == upcoming[0] else "  "
            msg += f"{marker}{entry['date']} — {entry['topic']}\n"

        # Generate full preview of the next post
        await update.message.reply_text(msg)
        await update.message.reply_text("Generating preview of the next post...")

        try:
            topic = upcoming[0]["topic"]
            brief = json.loads(daily_brief())
            trend_text = brief.get("content_brief", "") if brief.get("status") == "ok" else ""
            prompt = topic
            if trend_text:
                prompt = f"{topic}. Use this trending context if relevant: {trend_text[:500]}"

            draft_result = draft_content(prompt)
            if draft_result.get("status") != "drafted":
                await update.message.reply_text(f"Preview failed: {draft_result.get('detail', '?')}")
                return
            post_text = draft_result.get("content") or draft_result.get("post", "")
            if not post_text:
                await update.message.reply_text("Preview generated empty content.")
                return

            img_path = generate_image_for_post(topic)
            save_pending_draft(topic, post_text, img_path)

            preview = f"**Preview — {topic}**\n\n{post_text[:2000]}"
            if img_path:
                preview += f"\n\n_(Image generated)_"
            preview += "\n\nSend /approve to publish now, /reject to skip, or /draft to edit."
            await update.message.reply_text(preview[:4000])
        except Exception as e:
            await update.message.reply_text(f"Preview error: {e}")

    async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent posting history."""
        if not await require_auth(update, context): return
        try:
            result = json.loads(list_published(platform="linkedin", limit=10))
            posts = result if isinstance(result, list) else []
            if not posts:
                await update.message.reply_text("No posts published yet. Use /post or enable /schedule to get started.")
                return
            msg = f"**Recent Posts — Last {len(posts)}**\n\n"
            for p in posts:
                date = p.get("created_at", "")[:10] if p.get("created_at") else ""
                content = p.get("content", "")[:120].replace("\n", " ")
                post_id = p.get("external_id", "")[:20]
                msg += f"• {date} — {content}...\n"
            msg += "\nUse /planned to see upcoming content."
            await update.message.reply_text(msg[:4000])
        except Exception as e:
            await update.message.reply_text(f"Error loading history: {e}")

    async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Preview the next scheduled post without publishing."""
        if not await require_auth(update, context): return
        # Check if there's already a pending draft
        pending = load_pending_draft()
        if pending:
            msg = f"**Pending Draft (awaiting approval)**\n\nTopic: {pending['topic']}\n\n{pending['content'][:1500]}"
            if pending.get("image_path"):
                msg += f"\n\nImage: {pending['image_path']}"
            msg += "\n\nSend /approve to publish or /reject to discard."
            await update.message.reply_text(msg[:4000])
            return

        # Generate preview from next scheduled topic
        cfg = load_schedule()
        if not cfg.get("enabled"):
            await update.message.reply_text("Schedule is disabled. Nothing to preview.")
            return
        topics = cfg.get("topics", [])
        idx = cfg.get("topic_index", 0) % len(topics)
        topic = topics[idx]
        await update.message.reply_text(f"Generating preview for: **{topic}**...")

        # Run pipeline in preview mode (generate but don't post)
        try:
            brief = json.loads(daily_brief())
            trend_text = brief.get("content_brief", "") if brief.get("status") == "ok" else ""
        except Exception:
            trend_text = ""
        prompt = topic
        if trend_text:
            prompt = f"{topic}. Use this trending context if relevant: {trend_text[:500]}"
        draft_result = draft_content(prompt)
        if draft_result.get("status") != "drafted":
            await update.message.reply_text(f"Preview failed: {draft_result.get('detail', '?')}")
            return
        post_text = draft_result.get("content") or draft_result.get("post", "")
        if not post_text:
            await update.message.reply_text("Preview generated empty content.")
            return

        img_path = generate_image_for_post(topic)

        # Save as pending draft
        save_pending_draft(topic, post_text, img_path)

        msg = f"**Preview — Next Scheduled Post**\n\nTopic: {topic}\n\n---\n\n{post_text[:2000]}"
        if img_path:
            msg += f"\n\nImage generated ✓"
        msg += "\n\nSend /approve to publish or /reject to discard. Use /draft to edit the text."
        await update.message.reply_text(msg[:4000])

    async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Publish the pending draft."""
        if not await require_auth(update, context): return
        pending = load_pending_draft()
        if not pending:
            await update.message.reply_text("No pending draft to approve. Use /preview to generate one first.")
            return
        await update.message.reply_text("Publishing approved post...")
        try:
            post_text = pending["content"]
            img_path = pending.get("image_path")
            if img_path and Path(img_path).exists():
                result = json.loads(post_multi_image(post_text, [img_path]))
            else:
                result = json.loads(create_post(post_text))
            if result.get("status") == "posted":
                pid = result.get("id", "")
                log_published("linkedin", pid, post_text)
                # Advance topic index so we don't regenerate the same topic
                cfg = load_schedule()
                cfg["topic_index"] = cfg.get("topic_index", 0) + 1
                save_schedule(cfg)
                clear_pending_draft()
                await update.message.reply_text(f"Posted: https://linkedin.com/feed/update/{pid}")
            else:
                await update.message.reply_text(f"Post failed: {result.get('detail', '?')}")
        except Exception as e:
            await update.message.reply_text(f"Error posting: {e}")

    async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject the pending draft."""
        if not await require_auth(update, context): return
        pending = load_pending_draft()
        if not pending:
            await update.message.reply_text("No pending draft to reject.")
            return
        clear_pending_draft()
        # Advance topic index so we move to next topic
        cfg = load_schedule()
        cfg["topic_index"] = cfg.get("topic_index", 0) + 1
        save_schedule(cfg)
        await update.message.reply_text("Draft rejected and skipped. Use /preview to generate the next one.")

    async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        cfg = load_schedule()
        args = context.args
        if not args:
            text = (
                "**Schedule Management**\n\n"
                f"Status: {'Enabled' if cfg.get('enabled') else 'Disabled'}\n"
                f"Time: {cfg.get('time')} UTC on {cfg.get('days')}\n"
                f"Mode: {cfg.get('mode')}\n\n"
                "Subcommands:\n"
                "/schedule on        - Enable\n"
                "/schedule off       - Disable\n"
                "/schedule time 12:00 - Set time (UTC)\n"
                "/schedule days M,W,F - Set days\n"
                "/schedule mode auto|draft - Post or review\n"
                "/schedule topics ... - Set topics\n"
                "/schedule status    - Full status"
            )
            await update.message.reply_text(text)
            return

        sub = args[0].lower()

        if sub == "on":
            cfg["enabled"] = True
            save_schedule(cfg)
            reschedule_job()
            await update.message.reply_text("Auto-posting enabled.")
            logger.info("Schedule enabled")

        elif sub == "off":
            cfg["enabled"] = False
            save_schedule(cfg)
            reschedule_job()
            await update.message.reply_text("Auto-posting disabled.")
            logger.info("Schedule disabled")

        elif sub == "status":
            text = (
                f"**Schedule Status**\n\n"
                f"Enabled: {cfg.get('enabled')}\n"
                f"Time: {cfg.get('time')} UTC\n"
                f"Days: {cfg.get('days')}\n"
                f"Mode: {cfg.get('mode')}\n"
                f"Topics: {', '.join(cfg.get('topics', []))}\n"
                f"Next topic index: {cfg.get('topic_index', 0)}"
            )
            await update.message.reply_text(text)

        elif sub == "time":
            if len(args) < 2:
                await update.message.reply_text("Usage: /schedule time HH:MM (UTC)")
                return
            cfg["time"] = args[1]
            save_schedule(cfg)
            if cfg.get("enabled"):
                reschedule_job()
            await update.message.reply_text(f"Posting time set to {args[1]} UTC.")

        elif sub == "days":
            if len(args) < 2:
                await update.message.reply_text("Usage: /schedule days M,W,F or daily")
                return
            cfg["days"] = args[1]
            save_schedule(cfg)
            if cfg.get("enabled"):
                reschedule_job()
            await update.message.reply_text(f"Posting days set to {args[1]}.")

        elif sub == "mode":
            if len(args) < 2 or args[1] not in ("auto", "draft"):
                await update.message.reply_text("Usage: /schedule mode auto|draft")
                return
            cfg["mode"] = args[1]
            save_schedule(cfg)
            await update.message.reply_text(f"Mode set to {args[1]}.")
            if args[1] == "auto":
                await update.message.reply_text(
                    "Auto mode: posts directly to LinkedIn. "
                    "Use 'draft' mode if you want to review first."
                )

        elif sub == "topics":
            if len(args) < 2:
                await update.message.reply_text("Usage: /schedule topics SME,SEO,AI,marketing")
                return
            topics = [t.strip() for t in " ".join(args[1:]).split(",") if t.strip()]
            if len(topics) < 1:
                await update.message.reply_text("At least 1 topic required.")
                return
            cfg["topics"] = topics
            cfg["topic_index"] = 0
            save_schedule(cfg)
            await update.message.reply_text(f"Topics set: {', '.join(topics)}")

        else:
            await update.message.reply_text(f"Unknown subcommand: {sub}. See /help")

    async def hot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check trending topics and offer to post about one."""
        if not await require_auth(update, context): return
        await update.message.reply_text("Checking trending topics...")
        try:
            from research_server import daily_brief, trending_searches
            brief = json.loads(daily_brief())
            us = brief.get("us_trends", [])
            bb = brief.get("barbados_trends", [])
            all_trends = us[:3] + bb[:3]
            # Dedupe
            seen = set()
            unique = []
            for t in all_trends:
                key = t.lower().strip()
                if key not in seen:
                    seen.add(key)
                    unique.append(t)

            msg = "**Today's Hot Topics**\n\n"
            msg += "US Trends:\n" + "\n".join(f"- {t}" for t in us[:5]) + "\n\n"
            msg += f"Barbados: {', '.join(bb[:5])}\n\n"

            # Draft a post about the #1 trend
            top_topic = unique[0] if unique else "digital marketing trends"
            draft = draft_content(f"hot topic: {top_topic}")
            if draft.get("status") == "drafted":
                post = draft.get("content", "")
                msg += f"**Instant Post Draft** (about '{top_topic}'):\n\n{post[:1000]}"
                msg += "\n\n---\nSend /post_now to publish this or /draft <topic> for something else."
            else:
                msg += f"No draft generated: {draft.get('detail', '?')}"

            await update.message.reply_text(msg[:4000])
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def mirror_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mirror a competitor's post or topic with an OLE counter-angle."""
        if not await require_auth(update, context): return
        args = context.args
        if not args:
            await update.message.reply_text(
                "Usage: /mirror <competitor topic or post description>\n\n"
                "Example: /mirror \"Vend close more deals with AI\"\n\n"
                "I'll analyze their angle and create a counter-post in OLE voice."
            )
            return
        topic = " ".join(args)
        await update.message.reply_text(f"Analyzing competitor angle: {topic}...")
        try:
            result = mirror_competitor(topic)
            if result.get("status") == "drafted":
                post = result.get("content", "")
                msg = f"**Competitor Mirror** (counter-post):\n\n{post[:2000]}"
                msg += "\n\n---\nReply with /post to publish this."
                await update.message.reply_text(msg[:4000])
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        await update.message.reply_text("Checking system health...")
        try:
            from linkedin_server import whoami
            profile = json.loads(whoami())
            linkedin = "ok" if "name" in profile else "error"
            cfg = load_schedule()
            sched_status = "enabled" if cfg.get("enabled") else "disabled"
            text = (
                f"LinkedIn: {linkedin}\n"
                f"Schedule: {sched_status}\n"
                f"Time: {cfg.get('time')} on {cfg.get('days')}\n"
                f"Mode: {cfg.get('mode')}\n"
                f"Topics: {len(cfg.get('topics', []))} loaded\n"
            )
            await update.message.reply_text(text)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        await update.message.reply_text("Running content pipeline now...")
        try:
            run_content_pipeline(app)
            await update.message.reply_text("Pipeline finished. Check status above.")
        except Exception as e:
            await update.message.reply_text(f"Pipeline error: {e}")

    async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Conversational handler for non-command messages."""
        if not update.message or not update.message.text:
            return
        if not await require_auth(update, context):
            return
        user_text = update.message.text.strip()
        await update.message.reply_chat_action("typing")

        # 1. Try intent-based response (no Gemini call)
        intent = detect_intent(user_text)
        if intent != "unknown":
            reply = INTENT_RESPONSES.get(intent, FALLBACK_REPLY)
            await update.message.reply_text(reply)
            return

        # 2. Try Gemini with rate limiting
        try:
            from content_server import OLE_SYSTEM_PROMPT
            # Include recent posting history as context
            recent_history = ""
            try:
                hist = json.loads(list_published(platform="linkedin", limit=5))
                if isinstance(hist, list) and hist:
                    recent_history = "\n\nRecent posts we've already published:\n"
                    for h in hist:
                        date = (h.get("created_at") or "")[:10]
                        content = (h.get("content") or "")[:150].replace("\n", " ")
                        recent_history += f"- {date}: {content}\n"
            except Exception:
                pass

            # Include upcoming schedule
            schedule_context = ""
            try:
                upc = next_scheduled_posts(3)
                if upc:
                    schedule_context = "\n\nUpcoming scheduled posts:\n"
                    for e in upc:
                        schedule_context += f"- {e['date']}: {e['topic']}\n"
            except Exception:
                pass

            system_prompt = OLE_SYSTEM_PROMPT + recent_history + schedule_context + """

You are the LinkedIn coordinator for Online Everywhere. You chat with the business owner. Be conversational, direct, and helpful."""

            reply = gemini_chat(user_text, system_prompt)
            if reply:
                await update.message.reply_text(reply[:3000])
                return
        except Exception:
            pass

        # 3. Fallback when Gemini is rate limited or unavailable
        await update.message.reply_text(FALLBACK_REPLY)

    # ── Register handlers ───────────────────────────────────────

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("authorize", authorize))
    app.add_handler(CommandHandler("draft", draft))
    app.add_handler(CommandHandler("trends", trends_cmd))
    app.add_handler(CommandHandler("research", research_cmd))
    app.add_handler(CommandHandler("post", post_cmd))
    app.add_handler(CommandHandler("post_image", post_image_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CommandHandler("brainstorm", brainstorm_cmd))
    app.add_handler(CommandHandler("planned", planned_cmd))
    app.add_handler(CommandHandler("calendar", planned_cmd))
    app.add_handler(CommandHandler("preview", preview_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("hot", hot_cmd))
    app.add_handler(CommandHandler("mirror", mirror_cmd))
    app.add_handler(CommandHandler("post_now", post_now))
    app.add_handler(CommandHandler("status", status_cmd))

    # Catch-all for conversational messages (must be last)
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    # ── Start scheduler ──────────────────────────────────────────

    scheduler.start()
    reschedule_job()

    logger.info("Bot initialized, starting web server...")

    # Determine mode: webhook (Cloud Run) or polling (local)
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    PORT = int(os.getenv("PORT", "8080"))

    if WEBHOOK_URL:
        # ── Webhook mode (Cloud Run) ────────────────────────────────
        from fastapi import FastAPI, Request
        import uvicorn

        api = FastAPI(title="OLE LinkedIn Coordinator")

        @api.on_event("startup")
        async def startup():
            await app.initialize()
            await app.start()
            hook = f"{WEBHOOK_URL}/webhook"
            await app.bot.set_webhook(url=hook)
            logger.info(f"Webhook set: {hook}")

        @api.on_event("shutdown")
        async def shutdown():
            await app.stop()
            scheduler.shutdown(wait=False)

        @api.post("/webhook")
        async def webhook(request: Request):
            data = await request.json()
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
            return {"ok": True}

        @api.get("/health")
        async def health():
            sched = "running" if scheduler.running else "stopped"
            return {"status": "ok", "scheduler": sched}

        @api.post("/scheduler")
        async def scheduler_endpoint(request: Request):
            """Triggered by Cloud Scheduler for daily posts."""
            body = await request.json()
            secret = body.get("secret", "")
            if secret != os.getenv("SCHEDULER_SECRET", ""):
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            run_content_pipeline(app)
            return {"status": "ok"}

        uvicorn.run(api, host="0.0.0.0", port=PORT, log_level="info")
    else:
        # ── Polling mode (local dev) ─────────────────────────────
        logger.info("Bot started, polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
