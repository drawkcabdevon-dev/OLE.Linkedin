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
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("telegram-bot")

BASE = Path.home() / "social-agent"
AUTHORIZED_CHATS_FILE = BASE / "authorized_chats.json"
SCHEDULE_CONFIG_FILE = BASE / "schedule_config.json"
NOTIFY_CHAT_ID = None  # Set when /authorize runs
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")  # For direct HTTP notify

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
    "days": "M,W,F",
    "mode": "draft",       # "auto" = post directly, "draft" = save for review
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
from local_server import save_draft, log_published

def post_to_linkedin(text: str, image_path: str | None = None) -> dict:
    if image_path:
        p = Path(image_path)
        if p.suffix.lower() in (".pdf",):
            return {"status": "error", "detail": "PDF not supported via Telegram"}
        return json.loads(post_image(text, str(p)))
    return json.loads(create_post(text))

def draft_content(topic: str) -> dict:
    return json.loads(draft_post(topic))

def research_trends_data() -> dict:
    try:
        return json.loads(trending_searches())
    except Exception as e:
        return {"status": "error", "detail": str(e)}

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

    post_text = draft_result.get("post", "")
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
        # Draft mode — save as draft for review
        try:
            draft_saved = json.loads(save_draft("linkedin", post_text))
            _notify(app_instance,
                f"Draft saved for review (ID: {draft_saved.get('id', '?')})\n"
                f"Topic: {topic}\n"
                f"Reply to review: make/edit post\n\n{post_text[:500]}")
            logger.info(f"Pipeline: draft saved for topic '{topic}'")
        except Exception as e:
            logger.error(f"Pipeline: save draft failed: {e}")

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

    def reschedule_job():
        """Remove old job and add new one based on current config."""
        scheduler.remove_all_jobs()
        cfg = load_schedule()
        if not cfg.get("enabled"):
            logger.info("Scheduler: disabled, no jobs added")
            return
        try:
            hour, minute = cfg["time"].split(":")
            day_cron = days_to_cron(cfg.get("days", "M,W,F"))
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
            logger.info(f"Scheduler: job set for {cfg['time']} on {cfg['days']}")
        except Exception as e:
            logger.error(f"Scheduler setup failed: {e}")

    # ── Command handlers ─────────────────────────────────────────

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "Online Everywhere LinkedIn Agent\n\n"
            "I manage LinkedIn content for Online Everywhere.\n"
            "Authenticate with /authorize first, then set up scheduling.\n\n"
            "Commands:\n"
            "/draft <topic>   - Draft a post\n"
            "/trends          - Trending searches right now\n"
            "/research <topic>- Deep research\n"
            "/schedule        - Set up auto-posting\n"
            "/post_now        - Run pipeline now\n"
            "/post <text>     - Post to LinkedIn\n"
            "/status          - Health check\n"
            "/help            - Full command list"
        )
        await update.message.reply_text(text)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "/authorize          - Authorize this chat\n"
            "/draft <topic>      - Draft a LinkedIn post\n"
            "/trends             - Today's trending searches\n"
            "/research <topic>   - Deep research + content ideas\n"
            "/post <text>        - Post to LinkedIn\n"
            "/post_image <text>  - Reply to image to post\n"
            "/schedule           - Show schedule help\n"
            "/schedule on        - Enable auto-posting\n"
            "/schedule off       - Disable auto-posting\n"
            "/schedule status    - Show current schedule\n"
            "/schedule time HH:MM - Set posting time (UTC)\n"
            "/schedule days M,W,F - Set days\n"
            "/schedule mode auto|draft - Post directly or save draft\n"
            "/schedule topics t1,t2,t3 - Topics to rotate\n"
            "/post_now           - Run pipeline immediately\n"
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
                await update.message.reply_text(f"Draft:\n\n{result.get('post', '')[:3000]}")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error drafting: {e}")

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

    async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context): return
        await update.message.reply_text("Running content pipeline now...")
        try:
            run_content_pipeline(app)
            await update.message.reply_text("Pipeline finished. Check status above.")
        except Exception as e:
            await update.message.reply_text(f"Pipeline error: {e}")

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
    app.add_handler(CommandHandler("post_now", post_now))
    app.add_handler(CommandHandler("status", status_cmd))

    # ── Start scheduler ──────────────────────────────────────────

    scheduler.start()
    reschedule_job()

    logger.info("Bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
